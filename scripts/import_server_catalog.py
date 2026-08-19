from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.fitting_catalog_sync import normalize_text, sha256_file


FORMAT_VERSION = 2
DEFAULT_DATABASE_NAME = "furniture_platform.db"
MEDIA_ROOT_NAME = "media"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a server catalog bundle into SQLite.")
    parser.add_argument(
        "--database",
        default=DEFAULT_DATABASE_NAME,
        help="Path to furniture_platform.db.",
    )
    parser.add_argument(
        "--bundle",
        required=True,
        help="Path to the export bundle directory.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag the script only prints a dry-run plan.",
    )
    return parser.parse_args()


def _open_sqlite(database_path: Path, *, readonly: bool) -> sqlite3.Connection:
    mode = "ro" if readonly else "rw"
    uri = f"file:{database_path.as_posix()}?mode={mode}"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


_TABLE_COLUMN_CACHE: dict[str, set[str]] = {}


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    cache_key = table_name
    if cache_key not in _TABLE_COLUMN_CACHE:
        _TABLE_COLUMN_CACHE[cache_key] = {
            str(row[1]) for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
    return _TABLE_COLUMN_CACHE[cache_key]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_bundle(bundle_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _read_json(bundle_path / "manifest.json")
    catalog = _read_json(bundle_path / "catalog.json")
    if manifest.get("format_version") != FORMAT_VERSION or catalog.get("format_version") != FORMAT_VERSION:
        raise SystemExit("Unsupported catalog bundle format.")
    entity_sync_policy = manifest.get("entity_sync_policy")
    if not isinstance(entity_sync_policy, dict) or not entity_sync_policy:
        raise SystemExit("Bundle is missing explicit entity sync policy metadata.")
    if catalog.get("entity_sync_policy") != entity_sync_policy:
        raise SystemExit("catalog.json entity sync policy mismatch.")
    catalog_entities = catalog.get("entities")
    if not isinstance(catalog_entities, dict):
        raise SystemExit("catalog.json entities payload is invalid.")
    if not set(catalog_entities.keys()).issubset(set(entity_sync_policy.keys())):
        raise SystemExit("Bundle entity sync policy does not cover the exported entities.")
    catalog_sha256 = hashlib.sha256((bundle_path / "catalog.json").read_bytes()).hexdigest()
    if catalog_sha256 != manifest.get("catalog_sha256"):
        raise SystemExit("catalog.json checksum mismatch.")
    for media_entry in manifest.get("media_files", []):
        media_path = bundle_path / str(media_entry["path"])
        if not media_path.exists():
            raise SystemExit(f"Missing media file: {media_entry['path']}")
        if sha256_file(media_path) != media_entry["sha256"]:
            raise SystemExit(f"Media checksum mismatch: {media_entry['path']}")
    if manifest.get("missing_media_count"):
        missing = manifest.get("missing_media", [])
        details = ", ".join(str(item.get("missing_media_path")) for item in missing[:5])
        raise SystemExit(f"Bundle has missing referenced media: {details}")
    return manifest, catalog


def _integrity_check(connection: sqlite3.Connection) -> None:
    row = connection.execute("PRAGMA integrity_check").fetchone()
    if not row or str(row[0]).lower() != "ok":
        raise SystemExit(f"Integrity check failed: {row[0] if row else 'unknown'}")


def _count_table(connection: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(connection, table_name):
        return 0
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _existing_row(connection: sqlite3.Connection, table_name: str, where_sql: str, params: tuple[Any, ...]) -> sqlite3.Row | None:
    return connection.execute(f"SELECT * FROM {table_name} WHERE {where_sql} LIMIT 1", params).fetchone()


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    for key, value in row.items():
        if key in {"created_at", "updated_at", "media_path", "missing_media_path", "bytes_length"}:
            continue
        normalized[key] = value
    return normalized


def _copy_logo_media(bundle_path: Path, row: dict[str, Any], target_dir: Path) -> str | None:
    media_path = normalize_text(row.get("media_path"))
    if not media_path:
        return None
    source_path = bundle_path / media_path
    if not source_path.exists():
        raise SystemExit(f"Missing bundle media file: {media_path}")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source_path.name
    if target_path.exists():
        if sha256_file(target_path) != sha256_file(source_path):
            raise SystemExit(f"Target media path already exists with different content: {target_path}")
    else:
        shutil.copy2(source_path, target_path)
    return f"/uploads/{target_dir.name}/{source_path.name}"


def _same_content(existing_row: sqlite3.Row | None, desired: dict[str, Any], compare_keys: list[str]) -> bool:
    if existing_row is None:
        return False
    for key in compare_keys:
        if key in {"created_at", "updated_at"}:
            continue
        if existing_row[key] != desired.get(key):
            return False
    return True


def _upsert_row(
    connection: sqlite3.Connection,
    table_name: str,
    desired: dict[str, Any],
    *,
    key_columns: list[str],
    compare_columns: list[str] | None = None,
    ownership_column: str | None = None,
) -> str:
    table_columns = _table_columns(connection, table_name)
    desired = {key: value for key, value in desired.items() if key in table_columns or key in key_columns}
    compare_columns = compare_columns or [
        key
        for key in desired.keys()
        if key not in {"created_at", "updated_at", "id"}
    ]
    where_sql = " AND ".join(f"{column} = ?" if desired.get(column) is not None else f"{column} IS NULL" for column in key_columns)
    params = tuple(desired.get(column) for column in key_columns if desired.get(column) is not None)
    existing = _existing_row(connection, table_name, where_sql, params)
    if existing is not None and ownership_column and normalize_text(existing[ownership_column]):
        raise SystemExit(
            f"Conflict: {table_name} row {tuple(desired.get(column) for column in key_columns)} is user-owned."
        )

    if _same_content(existing, desired, compare_columns):
        return "unchanged"

    if existing is None:
        columns = [
            key
            for key in desired.keys()
            if key in table_columns
            and key != "id"
            and (desired.get(key) is not None or key in {"owner_user_id", "logo_url"})
        ]
        if table_name == "service_catalog_items" and desired.get("id") is not None and "id" in table_columns:
            columns = ["id", *columns]
        placeholders = ", ".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})",
            [desired.get(column) for column in columns],
        )
        return "inserted"

    assignments = ", ".join(
        f"{key} = ?"
        for key in desired.keys()
        if key in table_columns and key not in key_columns and key not in {"created_at", "updated_at", "id"}
    )
    update_values = [
        desired[key]
        for key in desired.keys()
        if key in table_columns and key not in key_columns and key not in {"created_at", "updated_at", "id"}
    ]
    connection.execute(
        f"UPDATE {table_name} SET {assignments} WHERE {where_sql}",
        [*update_values, *params],
    )
    return "updated"


def _service_item_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        normalize_text(_row_field_value(row, "source")) or "",
        normalize_text(_row_field_value(row, "external_code")) or "",
    )


def _row_field_value(row: dict[str, Any] | sqlite3.Row, key: str) -> Any:
    if isinstance(row, sqlite3.Row):
        return row[key] if key in row.keys() else None
    return row.get(key)


def _service_rule_key(
    row: dict[str, Any] | sqlite3.Row,
    connection: sqlite3.Connection | None = None,
) -> tuple[Any, ...]:
    source = normalize_text(_row_field_value(row, "source"))
    operation = normalize_text(_row_field_value(row, "operation"))
    service_source = _row_field_value(row, "service_source")
    service_external_code = _row_field_value(row, "service_external_code")
    if (service_source is None and service_external_code is None) and connection is not None:
        service_item_id = _row_field_value(row, "service_catalog_item_id")
        if service_item_id is not None:
            service_row = connection.execute(
                "SELECT source, external_code FROM service_catalog_items WHERE id = ?",
                (service_item_id,),
            ).fetchone()
            if service_row is not None:
                service_source = service_row["source"]
                service_external_code = service_row["external_code"]
    return (
        source or "",
        operation or "",
        _row_field_value(row, "diameter_min_mm"),
        _row_field_value(row, "diameter_max_mm"),
        _row_field_value(row, "depth_min_mm"),
        _row_field_value(row, "depth_max_mm"),
        normalize_text(service_source) or "",
        normalize_text(service_external_code) or "",
        _row_field_value(row, "priority"),
        normalize_text(_row_field_value(row, "city")) or "",
    )


def _fitting_image_key(fitting_id: Any, image_sha256: Any) -> tuple[Any, str]:
    return fitting_id, normalize_text(image_sha256) or ""


def _fitting_image_row_signature(row: dict[str, Any] | sqlite3.Row) -> tuple[Any, ...]:
    return (
        row["sort_order"],
        1 if row["is_primary"] in (True, 1) else 0,
        row["source_url"],
        row["image_cached_content_type"],
        row["image_sha256"],
        row["image_cached_bytes"],
    )


def _merge_fitting_image_rows(
    base_row: dict[str, Any],
    incoming_row: dict[str, Any],
    *,
    conflicts: list[str],
    bundle_key: tuple[Any, str],
) -> dict[str, Any]:
    merged = dict(base_row)
    merged["is_primary"] = 1 if base_row.get("is_primary") in (True, 1) or incoming_row.get("is_primary") in (True, 1) else 0

    base_sort_order = merged.get("sort_order")
    incoming_sort_order = incoming_row.get("sort_order")
    if base_sort_order is None:
        merged["sort_order"] = incoming_sort_order
    elif incoming_sort_order is not None and int(incoming_sort_order) < int(base_sort_order):
        merged["sort_order"] = incoming_sort_order

    for field in ("source_url", "image_cached_content_type"):
        base_value = normalize_text(merged.get(field))
        incoming_value = normalize_text(incoming_row.get(field))
        if not base_value and incoming_value:
            merged[field] = incoming_row.get(field)
        elif base_value and incoming_value and base_value != incoming_value:
            conflicts.append(
                f"fitting_images duplicate key {bundle_key}: conflicting {field} values; kept {base_value!r}, saw {incoming_value!r}"
            )

    if merged.get("image_cached_bytes") != incoming_row.get("image_cached_bytes"):
        conflicts.append(f"fitting_images duplicate key {bundle_key}: conflicting image bytes; kept first row")

    return merged


def _group_fitting_image_rows(
    entities: dict[str, list[dict[str, Any]]],
    bundle_path: Path,
    current_maps: dict[str, dict[Any, Any]],
    *,
    skipped: list[str],
    conflicts: list[str],
) -> list[dict[str, Any]]:
    grouped_rows: dict[tuple[Any, str], dict[str, Any]] = {}
    for index, row in enumerate(entities.get("fitting_images", [])):
        fitting_id = current_maps["fitting_id_by_article"].get(normalize_text(row.get("fitting_article")))
        if fitting_id is None:
            skipped.append(f"fitting_images:{row.get('fitting_article')}")
            continue
        fitting_meta = current_maps["fitting_meta_by_id"].get(fitting_id, {})
        if normalize_text(fitting_meta.get("owner_user_id")):
            skipped.append(f"fitting_images:user-owned:{row.get('fitting_article')}")
            continue
        media_path = normalize_text(row.get("media_path"))
        if not media_path:
            skipped.append(f"fitting_images:missing-media:{row.get('fitting_article')}")
            continue
        image_bytes = (bundle_path / media_path).read_bytes()
        desired = {
            "fitting_id": fitting_id,
            "sort_order": row.get("sort_order"),
            "is_primary": 1 if row.get("is_primary") in (True, 1) else 0,
            "source_url": row.get("source_url"),
            "image_cached_bytes": image_bytes,
            "image_cached_content_type": row.get("image_cached_content_type"),
            "image_sha256": row.get("image_sha256") or hashlib.sha256(image_bytes).hexdigest(),
            "_bundle_index": index,
        }
        key = _fitting_image_key(fitting_id, desired["image_sha256"])
        if key not in grouped_rows:
            grouped_rows[key] = desired
            continue
        grouped_rows[key] = _merge_fitting_image_rows(grouped_rows[key], desired, conflicts=conflicts, bundle_key=key)
    grouped_by_fitting_id: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in grouped_rows.values():
        grouped_by_fitting_id[row["fitting_id"]].append(row)
    return grouped_by_fitting_id


def _sync_fitting_images_for_fitting(
    connection: sqlite3.Connection,
    fitting_id: int,
    desired_rows: list[dict[str, Any]],
    *,
    current_maps: dict[str, dict[Any, Any]],
    skipped: list[str],
) -> tuple[int, int, int]:
    fitting_meta = current_maps["fitting_meta_by_id"].get(fitting_id, {})
    if normalize_text(fitting_meta.get("owner_user_id")):
        skipped.append(f"fitting_images:user-owned:{current_maps['fitting_article_by_id'].get(fitting_id, fitting_id)}")
        return 0, 0, 0

    current_rows = connection.execute(
        """
        SELECT id, fitting_id, sort_order, is_primary, source_url, image_cached_bytes,
               image_cached_content_type, image_sha256
        FROM fitting_images
        WHERE fitting_id = ?
        ORDER BY sort_order, id
        """,
        (fitting_id,),
    ).fetchall()
    if not desired_rows:
        return 0, 0, 0

    def _sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
        sort_order = row.get("sort_order")
        return (
            1 if sort_order is None else 0,
            int(sort_order or 0),
            normalize_text(row.get("image_sha256")) or "",
        )

    normalized_desired_rows = []
    seen_shas: dict[str, dict[str, Any]] = {}
    for row in sorted(desired_rows, key=_sort_key):
        desired = dict(row)
        desired["is_primary"] = 1 if desired.get("is_primary") in (True, 1) else 0
        desired["sort_order"] = int(desired.get("sort_order") or 0)
        image_sha256 = normalize_text(desired.get("image_sha256")) or hashlib.sha256(desired["image_cached_bytes"]).hexdigest()
        desired["image_sha256"] = image_sha256
        key = _fitting_image_key(fitting_id, image_sha256)
        if key in seen_shas:
            existing = seen_shas[key]
            existing["is_primary"] = 1 if existing.get("is_primary") or desired["is_primary"] else 0
            if desired["sort_order"] < existing["sort_order"]:
                existing["sort_order"] = desired["sort_order"]
            for field in ("source_url", "image_cached_content_type"):
                if not normalize_text(existing.get(field)) and desired.get(field) is not None:
                    existing[field] = desired[field]
            continue
        seen_shas[key] = desired
        normalized_desired_rows.append(desired)

    if not normalized_desired_rows:
        return 0, 0, 0

    desired_by_sha = {
        normalize_text(row["image_sha256"]): row for row in normalized_desired_rows
    }
    current_by_sha = {
        normalize_text(row["image_sha256"]): row for row in current_rows
    }

    primary_sha = next(
        (
            normalize_text(row["image_sha256"])
            for row in normalized_desired_rows
            if row.get("is_primary") in (True, 1)
        ),
        normalize_text(normalized_desired_rows[0]["image_sha256"]),
    )
    for row in normalized_desired_rows:
        row["is_primary"] = 1 if normalize_text(row["image_sha256"]) == primary_sha else 0

    desired_sha_set = set(desired_by_sha.keys())
    extras = [
        row
        for row in current_rows
        if normalize_text(row["image_sha256"]) not in desired_sha_set
    ]
    extras.sort(key=lambda row: (int(row["sort_order"] or 0), int(row["id"])))

    final_rows: list[dict[str, Any]] = []
    for row in normalized_desired_rows:
        existing_row = current_by_sha.get(normalize_text(row["image_sha256"]))
        final_rows.append(
            {
                "id": existing_row["id"] if existing_row is not None else None,
                "fitting_id": fitting_id,
                "sort_order": row["sort_order"],
                "is_primary": row["is_primary"],
                "source_url": row.get("source_url"),
                "image_cached_bytes": row["image_cached_bytes"],
                "image_cached_content_type": row.get("image_cached_content_type"),
                "image_sha256": row["image_sha256"],
                "kind": "desired",
            }
        )

    bundle_max_sort_order = max((row["sort_order"] for row in normalized_desired_rows), default=-1)
    for index, row in enumerate(extras):
        final_rows.append(
            {
                "id": row["id"],
                "fitting_id": fitting_id,
                "sort_order": bundle_max_sort_order + index + 1,
                "is_primary": 0,
                "source_url": row["source_url"],
                "image_cached_bytes": row["image_cached_bytes"],
                "image_cached_content_type": row["image_cached_content_type"],
                "image_sha256": row["image_sha256"],
                "kind": "extra",
            }
        )

    current_signature = sorted(
        (_fitting_image_row_signature(row) for row in current_rows),
        key=lambda item: (item[0], item[4]),
    )
    final_signature = sorted(
        (_fitting_image_row_signature(row) for row in final_rows),
        key=lambda item: (item[0], item[4]),
    )
    if current_signature == final_signature:
        return 0, 0, len(final_rows)

    temp_base = max(
        [int(row["sort_order"] or 0) for row in current_rows] + [int(row["sort_order"] or 0) for row in final_rows],
        default=-1,
    ) + 1000
    for index, row in enumerate(current_rows):
        connection.execute(
            "UPDATE fitting_images SET sort_order = ? WHERE id = ?",
            (temp_base + index, row["id"]),
        )

    inserted = 0
    updated = 0
    unchanged = 0
    for row in final_rows:
        existing = current_by_sha.get(normalize_text(row["image_sha256"]))
        if existing is None:
            connection.execute(
                """
                INSERT INTO fitting_images (
                    fitting_id,
                    sort_order,
                    is_primary,
                    source_url,
                    image_cached_bytes,
                    image_cached_content_type,
                    image_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["fitting_id"],
                    row["sort_order"],
                    row["is_primary"],
                    row["source_url"],
                    row["image_cached_bytes"],
                    row["image_cached_content_type"],
                    row["image_sha256"],
                ),
            )
            inserted += 1
            continue
        if _fitting_image_row_signature(existing) == _fitting_image_row_signature(row):
            unchanged += 1
        else:
            updated += 1
        connection.execute(
            """
            UPDATE fitting_images
            SET sort_order = ?,
                is_primary = ?,
                source_url = ?,
                image_cached_bytes = ?,
                image_cached_content_type = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                row["sort_order"],
                row["is_primary"],
                row["source_url"],
                row["image_cached_bytes"],
                row["image_cached_content_type"],
                existing["id"],
            ),
        )

    return inserted, updated, unchanged


def _load_foreign_key_references(connection: sqlite3.Connection) -> dict[str, list[tuple[str, str, str]]]:
    references: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    tables = [row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()]
    for table_name in tables:
        for fk in connection.execute(f"PRAGMA foreign_key_list({table_name})").fetchall():
            references[str(fk["table"])].append((table_name, str(fk["from"]), str(fk["on_delete"]).upper()))
    return references


def _row_is_sync_managed(table_name: str, row: sqlite3.Row) -> bool:
    if "owner_user_id" in row.keys() and normalize_text(row["owner_user_id"]):
        return False
    if "is_system" in row.keys() and row["is_system"] in (0, False):
        return False
    return True


def _bundle_key_sets(entities: dict[str, list[dict[str, Any]]]) -> dict[str, set[Any]]:
    return {
        "suppliers": {normalize_text(row.get("code")) for row in entities.get("suppliers", []) if normalize_text(row.get("code"))},
        "fitting_manufacturers": {normalize_text(row.get("code")) for row in entities.get("fitting_manufacturers", []) if normalize_text(row.get("code"))},
        "fitting_categories": {normalize_text(row.get("code")) for row in entities.get("fitting_categories", []) if normalize_text(row.get("code"))},
        "fitting_series": {
            (normalize_text(row.get("manufacturer_code")), normalize_text(row.get("code")))
            for row in entities.get("fitting_series", [])
            if normalize_text(row.get("manufacturer_code")) and normalize_text(row.get("code"))
        },
        "fitting_products": {normalize_text(row.get("article")) for row in entities.get("fitting_products", []) if normalize_text(row.get("article"))},
        "fittings": {normalize_text(row.get("article")) for row in entities.get("fittings", []) if normalize_text(row.get("article"))},
        "fitting_hole_templates": {
            (
                normalize_text(row.get("fitting_article")),
                normalize_text(row.get("bundle_key")),
                normalize_text(row.get("template_type")),
                normalize_text(row.get("side")),
            )
            for row in entities.get("fitting_hole_templates", [])
            if normalize_text(row.get("fitting_article"))
        },
        "fitting_hole_points": {
            (
                normalize_text(row.get("fitting_article")),
                normalize_text(row.get("template_bundle_key")),
                normalize_text(row.get("template_type")),
                normalize_text(row.get("side")),
                int(row.get("order_index") or 0),
                normalize_text(row.get("label")),
            )
            for row in entities.get("fitting_hole_points", [])
            if normalize_text(row.get("fitting_article"))
        },
        "fitting_supplier_offers": {
            (
                normalize_text(row.get("supplier_code")),
                normalize_text(row.get("fitting_article")),
                normalize_text(row.get("external_product_id")),
            )
            for row in entities.get("fitting_supplier_offers", [])
            if normalize_text(row.get("supplier_code")) and normalize_text(row.get("fitting_article"))
        },
        "fitting_hole_service_rules": {
            _service_rule_key(row)
            for row in entities.get("fitting_hole_service_rules", [])
            if _service_rule_key(row) != ("", "", None, None, None, None, "", "", None, "")
        },
        "service_catalog_items": {
            _service_item_key(row)
            for row in entities.get("service_catalog_items", [])
            if _service_item_key(row) != ("", "")
        },
    }


def _delete_if_unblocked(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    row: sqlite3.Row,
    natural_key: Any,
    bundle_keys: dict[str, set[Any]],
    foreign_key_references: dict[str, list[tuple[str, str, str]]],
    planned_deletes: list[dict[str, Any]],
    blocked_deletes: list[dict[str, Any]],
    apply: bool,
) -> bool:
    row_id = row["id"]
    blockers = _collect_delete_blockers(
        connection,
        table_name=table_name,
        row=row,
        foreign_key_references=foreign_key_references,
    )

    if blockers:
        blocked_deletes.append(
            {
                "entity": table_name,
                "natural_key": natural_key,
                "id": row_id,
                "blockers": blockers,
            }
        )
        return False

    planned_deletes.append(
        {
            "entity": table_name,
            "natural_key": natural_key,
            "id": row_id,
        }
    )
    connection.execute(f"DELETE FROM {table_name} WHERE id = ?", (row_id,))
    return True


def _collect_delete_blockers(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    row: sqlite3.Row,
    foreign_key_references: dict[str, list[tuple[str, str, str]]],
    ignore_dependent_tables: set[str] | None = None,
) -> list[dict[str, Any]]:
    row_id = row["id"]
    ignore_dependent_tables = ignore_dependent_tables or set()
    blockers: list[dict[str, Any]] = []

    for dependent_table, dependent_column, on_delete in foreign_key_references.get(table_name, []):
        if on_delete == "CASCADE" or dependent_table in ignore_dependent_tables:
            continue
        dependent_rows = connection.execute(
            f"SELECT id FROM {dependent_table} WHERE {dependent_column} = ?",
            (row_id,),
        ).fetchall()
        if dependent_rows:
            blockers.append(
                {
                    "dependent_table": dependent_table,
                    "dependent_ids": [dep_row["id"] for dep_row in dependent_rows],
                }
            )

    if table_name == "fitting_products":
        dependent_rows = connection.execute(
            "SELECT id FROM fittings WHERE technical_product_id = ?",
            (row_id,),
        ).fetchall()
        if dependent_rows:
            blockers.append(
                {
                    "dependent_table": "fittings",
                    "dependent_ids": [dep_row["id"] for dep_row in dependent_rows],
                }
            )
    elif table_name == "fitting_series":
        dependent_rows = connection.execute(
            "SELECT id FROM fitting_products WHERE series_id = ?",
            (row_id,),
        ).fetchall()
        if dependent_rows:
            blockers.append(
                {
                    "dependent_table": "fitting_products",
                    "dependent_ids": [dep_row["id"] for dep_row in dependent_rows],
                }
            )
    elif table_name == "fitting_categories":
        dependent_rows = connection.execute(
            "SELECT id FROM fitting_products WHERE category_id = ?",
            (row_id,),
        ).fetchall()
        if dependent_rows:
            blockers.append(
                {
                    "dependent_table": "fitting_products",
                    "dependent_ids": [dep_row["id"] for dep_row in dependent_rows],
                }
            )
    elif table_name == "fitting_manufacturers":
        series_rows = connection.execute(
            "SELECT id FROM fitting_series WHERE manufacturer_id = ?",
            (row_id,),
        ).fetchall()
        product_rows = connection.execute(
            "SELECT id FROM fitting_products WHERE manufacturer_id = ?",
            (row_id,),
        ).fetchall()
        if series_rows:
            blockers.append(
                {
                    "dependent_table": "fitting_series",
                    "dependent_ids": [dep_row["id"] for dep_row in series_rows],
                }
            )
        if product_rows:
            blockers.append(
                {
                    "dependent_table": "fitting_products",
                    "dependent_ids": [dep_row["id"] for dep_row in product_rows],
                }
            )
    elif table_name == "suppliers":
        dependent_rows = connection.execute(
            "SELECT id FROM fitting_supplier_offers WHERE supplier_id = ?",
            (row_id,),
        ).fetchall()
        if dependent_rows:
            blockers.append(
                {
                    "dependent_table": "fitting_supplier_offers",
                    "dependent_ids": [dep_row["id"] for dep_row in dependent_rows],
                }
            )
    elif table_name == "service_catalog_items":
        dependent_rows = connection.execute(
            "SELECT id FROM fitting_hole_service_rules WHERE service_catalog_item_id = ?",
            (row_id,),
        ).fetchall()
        if dependent_rows:
            blockers.append(
                {
                    "dependent_table": "fitting_hole_service_rules",
                    "dependent_ids": [dep_row["id"] for dep_row in dependent_rows],
                }
            )
    elif table_name == "fittings":
        if _table_exists(connection, "mounting_node_items"):
            dependent_rows = connection.execute(
                "SELECT id FROM mounting_node_items WHERE fitting_id = ?",
                (row_id,),
            ).fetchall()
            if dependent_rows:
                blockers.append(
                    {
                        "dependent_table": "mounting_node_items",
                        "dependent_ids": [dep_row["id"] for dep_row in dependent_rows],
                    }
                )

    return blockers


def _delete_stale_fitting_with_children(
    connection: sqlite3.Connection,
    *,
    row: sqlite3.Row,
    foreign_key_references: dict[str, list[tuple[str, str, str]]],
    planned_deletes: list[dict[str, Any]],
    blocked_deletes: list[dict[str, Any]],
    technical_child_cascades: list[dict[str, Any]],
) -> bool:
    fitting_id = row["id"]
    fitting_article = normalize_text(row["article"])
    parent_blockers = _collect_delete_blockers(
        connection,
        table_name="fittings",
        row=row,
        foreign_key_references=foreign_key_references,
    )

    technical_children: dict[str, list[int]] = {
        "fitting_images": [],
        "fitting_supplier_offers": [],
        "fitting_hole_templates": [],
        "fitting_hole_points": [],
    }

    image_rows = connection.execute(
        "SELECT * FROM fitting_images WHERE fitting_id = ? ORDER BY sort_order, id",
        (fitting_id,),
    ).fetchall()
    offer_rows = connection.execute(
        "SELECT * FROM fitting_supplier_offers WHERE fitting_id = ? ORDER BY id",
        (fitting_id,),
    ).fetchall()
    template_rows = connection.execute(
        "SELECT * FROM fitting_hole_templates WHERE fitting_id = ? ORDER BY id",
        (fitting_id,),
    ).fetchall()

    template_points: dict[int, list[sqlite3.Row]] = {}
    for template_row in template_rows:
        template_points[template_row["id"]] = connection.execute(
            "SELECT * FROM fitting_hole_points WHERE template_id = ? ORDER BY order_index, id",
            (template_row["id"],),
        ).fetchall()

    template_blockers: list[dict[str, Any]] = []
    point_blockers: list[dict[str, Any]] = []
    for template_row in template_rows:
        template_blockers.extend(
            _collect_delete_blockers(
                connection,
                table_name="fitting_hole_templates",
                row=template_row,
                foreign_key_references=foreign_key_references,
                ignore_dependent_tables={"fitting_hole_points"},
            )
        )
        for point_row in template_points.get(template_row["id"], []):
            point_blockers.extend(
                _collect_delete_blockers(
                    connection,
                    table_name="fitting_hole_points",
                    row=point_row,
                    foreign_key_references=foreign_key_references,
                )
            )

    if parent_blockers or template_blockers or point_blockers:
        blocked_deletes.append(
            {
                "entity": "fittings",
                "natural_key": fitting_article,
                "id": fitting_id,
                "blockers": parent_blockers,
                "technical_child_blockers": {
                    "fitting_hole_templates": template_blockers,
                    "fitting_hole_points": point_blockers,
                },
            }
        )
        return False

    for image_row in image_rows:
        planned_deletes.append(
            {
                "entity": "fitting_images",
                "natural_key": (
                    fitting_article,
                    image_row["sort_order"],
                    image_row["image_sha256"],
                ),
                "id": image_row["id"],
                "parent_entity": "fittings",
                "parent_id": fitting_id,
            }
        )
        connection.execute("DELETE FROM fitting_images WHERE id = ?", (image_row["id"],))
        technical_children["fitting_images"].append(image_row["id"])

    for offer_row in offer_rows:
        planned_deletes.append(
            {
                "entity": "fitting_supplier_offers",
                "natural_key": (
                    fitting_id,
                    offer_row["supplier_id"],
                    offer_row["external_product_id"],
                ),
                "id": offer_row["id"],
                "parent_entity": "fittings",
                "parent_id": fitting_id,
            }
        )
        connection.execute("DELETE FROM fitting_supplier_offers WHERE id = ?", (offer_row["id"],))
        technical_children["fitting_supplier_offers"].append(offer_row["id"])

    for template_row in template_rows:
        for point_row in template_points.get(template_row["id"], []):
            planned_deletes.append(
                {
                    "entity": "fitting_hole_points",
                    "natural_key": (
                        fitting_article,
                        template_row["bundle_key"],
                        template_row["template_type"],
                        template_row["side"],
                        int(point_row["order_index"] or 0),
                        normalize_text(point_row["label"]),
                    ),
                    "id": point_row["id"],
                    "parent_entity": "fittings",
                    "parent_id": fitting_id,
                }
            )
            connection.execute("DELETE FROM fitting_hole_points WHERE id = ?", (point_row["id"],))
            technical_children["fitting_hole_points"].append(point_row["id"])

        planned_deletes.append(
            {
                "entity": "fitting_hole_templates",
                "natural_key": (
                    fitting_article,
                    normalize_text(template_row["bundle_key"]),
                    normalize_text(template_row["template_type"]),
                    normalize_text(template_row["side"]),
                ),
                "id": template_row["id"],
                "parent_entity": "fittings",
                "parent_id": fitting_id,
            }
        )
        connection.execute("DELETE FROM fitting_hole_templates WHERE id = ?", (template_row["id"],))
        technical_children["fitting_hole_templates"].append(template_row["id"])

    planned_deletes.append(
        {
            "entity": "fittings",
            "natural_key": fitting_article,
            "id": fitting_id,
        }
    )
    connection.execute("DELETE FROM fittings WHERE id = ?", (fitting_id,))
    technical_child_cascades.append(
        {
            "fitting_id": fitting_id,
            "natural_key": fitting_article,
            "technical_children": technical_children,
        }
    )
    return True


def _sync_stale_system_catalog(
    connection: sqlite3.Connection,
    entities: dict[str, list[dict[str, Any]]],
    *,
    sync_policy: dict[str, str],
    apply: bool,
) -> dict[str, Any]:
    bundle_keys = _bundle_key_sets(entities)
    foreign_key_references = _load_foreign_key_references(connection)
    stale_system: dict[str, int] = defaultdict(int)
    planned_deletes: list[dict[str, Any]] = []
    blocked_deletes: list[dict[str, Any]] = []
    technical_child_cascades: list[dict[str, Any]] = []
    deleted = 0

    def _record_skip(table_name: str, row: sqlite3.Row) -> None:
        if table_name == "suppliers":
            natural_key = row["code"]
        elif table_name == "fitting_manufacturers":
            natural_key = row["code"]
        elif table_name == "fitting_categories":
            natural_key = row["code"]
        elif table_name == "fitting_series":
            manufacturer_code = connection.execute(
                "SELECT code FROM fitting_manufacturers WHERE id = ?",
                (row["manufacturer_id"],),
            ).fetchone()
            natural_key = (
                manufacturer_code[0] if manufacturer_code else None,
                row["code"],
            )
        elif table_name == "fitting_products":
            natural_key = row["article"]
        elif table_name == "fittings":
            natural_key = row["article"]
        elif table_name == "fitting_hole_templates":
            natural_key = (
                row["fitting_id"],
                row["bundle_key"],
                row["template_type"],
                row["side"],
            )
        elif table_name == "fitting_hole_points":
            natural_key = (
                row["template_id"],
                row["order_index"],
                row["label"],
            )
        elif table_name == "fitting_supplier_offers":
            natural_key = (
                row["fitting_id"],
                row["supplier_id"],
                row["external_product_id"],
            )
        elif table_name == "fitting_hole_service_rules":
            natural_key = _service_rule_key(row, connection)
        elif table_name == "service_catalog_items":
            natural_key = _service_item_key(row)
        else:
            natural_key = row["id"]
        blocked_deletes.append(
            {
                "entity": table_name,
                "natural_key": natural_key,
                "id": row["id"],
                "reason": "user-owned-or-non-system",
            }
        )

    delete_order = [
        "fitting_hole_points",
        "fitting_hole_templates",
        "fittings",
        "fitting_products",
        "fitting_series",
        "fitting_categories",
        "fitting_manufacturers",
        "suppliers",
    ]
    delete_order = [table_name for table_name in delete_order if sync_policy.get(table_name) == "authoritative_full"]

    for table_name in delete_order:
        if not _table_exists(connection, table_name):
            continue
        rows = connection.execute(f"SELECT * FROM {table_name}").fetchall()
        bundle_keys_for_table = bundle_keys.get(table_name, set())
        for row in rows:
            if not _row_is_sync_managed(table_name, row):
                _record_skip(table_name, row)
                continue
            if table_name == "fitting_series":
                manufacturer_code = connection.execute(
                    "SELECT code FROM fitting_manufacturers WHERE id = ?",
                    (row["manufacturer_id"],),
                ).fetchone()
                natural_key = (
                    normalize_text(manufacturer_code[0]) if manufacturer_code else None,
                    normalize_text(row["code"]),
                )
            elif table_name == "fitting_products":
                natural_key = normalize_text(row["article"])
            elif table_name == "fittings":
                natural_key = normalize_text(row["article"])
            elif table_name == "fitting_hole_templates":
                fitting_article = connection.execute(
                    "SELECT article FROM fittings WHERE id = ?",
                    (row["fitting_id"],),
                ).fetchone()
                natural_key = (
                    normalize_text(fitting_article[0]) if fitting_article else None,
                    normalize_text(row["bundle_key"]),
                    normalize_text(row["template_type"]),
                    normalize_text(row["side"]),
                )
            elif table_name == "fitting_hole_points":
                template_row = connection.execute(
                    """
                    SELECT fittings.article, fitting_hole_templates.bundle_key, fitting_hole_templates.template_type, fitting_hole_templates.side
                    FROM fitting_hole_points
                    JOIN fitting_hole_templates ON fitting_hole_templates.id = fitting_hole_points.template_id
                    JOIN fittings ON fittings.id = fitting_hole_templates.fitting_id
                    WHERE fitting_hole_points.id = ?
                    """,
                    (row["id"],),
                ).fetchone()
                natural_key = (
                    normalize_text(template_row["article"]) if template_row else None,
                    normalize_text(template_row["bundle_key"]) if template_row else None,
                    normalize_text(template_row["template_type"]) if template_row else None,
                    normalize_text(template_row["side"]) if template_row else None,
                    int(row["order_index"] or 0),
                    normalize_text(row["label"]),
                )
            elif table_name == "fitting_supplier_offers":
                fitting_row = connection.execute(
                    "SELECT article FROM fittings WHERE id = ?",
                    (row["fitting_id"],),
                ).fetchone()
                supplier_row = connection.execute(
                    "SELECT code FROM suppliers WHERE id = ?",
                    (row["supplier_id"],),
                ).fetchone()
                natural_key = (
                    normalize_text(supplier_row[0]) if supplier_row else None,
                    normalize_text(fitting_row[0]) if fitting_row else None,
                    normalize_text(row["external_product_id"]),
                )
            elif table_name == "fitting_hole_service_rules":
                natural_key = _service_rule_key(row)
            elif table_name == "service_catalog_items":
                natural_key = _service_item_key(row)
            else:
                natural_key = row["id"]

            bundle_key_present = False
            if table_name == "suppliers":
                bundle_key_present = normalize_text(row["code"]) in bundle_keys_for_table
            elif table_name == "fitting_manufacturers":
                bundle_key_present = normalize_text(row["code"]) in bundle_keys_for_table
            elif table_name == "fitting_categories":
                bundle_key_present = normalize_text(row["code"]) in bundle_keys_for_table
            elif table_name == "fitting_series":
                manufacturer_code = connection.execute(
                    "SELECT code FROM fitting_manufacturers WHERE id = ?",
                    (row["manufacturer_id"],),
                ).fetchone()
                bundle_key_present = (
                    normalize_text(manufacturer_code[0]) if manufacturer_code else None,
                    normalize_text(row["code"]),
                ) in bundle_keys_for_table
            elif table_name == "fitting_products":
                bundle_key_present = normalize_text(row["article"]) in bundle_keys_for_table
            elif table_name == "fittings":
                bundle_key_present = normalize_text(row["article"]) in bundle_keys_for_table
            elif table_name == "fitting_hole_templates":
                fitting_article = connection.execute(
                    "SELECT article FROM fittings WHERE id = ?",
                    (row["fitting_id"],),
                ).fetchone()
                bundle_key_present = (
                    normalize_text(fitting_article[0]) if fitting_article else None,
                    normalize_text(row["bundle_key"]),
                    normalize_text(row["template_type"]),
                    normalize_text(row["side"]),
                ) in bundle_keys_for_table
            elif table_name == "fitting_hole_points":
                template_row = connection.execute(
                    """
                    SELECT fittings.article, fitting_hole_templates.bundle_key, fitting_hole_templates.template_type, fitting_hole_templates.side
                    FROM fitting_hole_points
                    JOIN fitting_hole_templates ON fitting_hole_templates.id = fitting_hole_points.template_id
                    JOIN fittings ON fittings.id = fitting_hole_templates.fitting_id
                    WHERE fitting_hole_points.id = ?
                    """,
                    (row["id"],),
                ).fetchone()
                bundle_key_present = (
                    normalize_text(template_row["article"]) if template_row else None,
                    normalize_text(template_row["bundle_key"]) if template_row else None,
                    normalize_text(template_row["template_type"]) if template_row else None,
                    normalize_text(template_row["side"]) if template_row else None,
                    int(row["order_index"] or 0),
                    normalize_text(row["label"]),
                ) in bundle_keys_for_table
            elif table_name == "fitting_supplier_offers":
                fitting_row = connection.execute(
                    "SELECT article FROM fittings WHERE id = ?",
                    (row["fitting_id"],),
                ).fetchone()
                supplier_row = connection.execute(
                    "SELECT code FROM suppliers WHERE id = ?",
                    (row["supplier_id"],),
                ).fetchone()
                bundle_key_present = (
                    normalize_text(supplier_row[0]) if supplier_row else None,
                    normalize_text(fitting_row[0]) if fitting_row else None,
                    normalize_text(row["external_product_id"]),
                ) in bundle_keys_for_table
            elif table_name == "fitting_hole_service_rules":
                bundle_key_present = _service_rule_key(row, connection) in bundle_keys_for_table
            elif table_name == "service_catalog_items":
                bundle_key_present = _service_item_key(row) in bundle_keys_for_table
            if bundle_key_present:
                continue

            stale_system[table_name] += 1
            if table_name == "fittings":
                if _delete_stale_fitting_with_children(
                    connection,
                    row=row,
                    foreign_key_references=foreign_key_references,
                    planned_deletes=planned_deletes,
                    blocked_deletes=blocked_deletes,
                    technical_child_cascades=technical_child_cascades,
                ):
                    deleted += 1
                    deleted += len(technical_child_cascades[-1]["technical_children"]["fitting_images"])
                    deleted += len(technical_child_cascades[-1]["technical_children"]["fitting_supplier_offers"])
                    deleted += len(technical_child_cascades[-1]["technical_children"]["fitting_hole_templates"])
                    deleted += len(technical_child_cascades[-1]["technical_children"]["fitting_hole_points"])
            else:
                if _delete_if_unblocked(
                    connection,
                    table_name=table_name,
                    row=row,
                    natural_key=natural_key,
                    bundle_keys=bundle_keys,
                    foreign_key_references=foreign_key_references,
                    planned_deletes=planned_deletes,
                    blocked_deletes=blocked_deletes,
                    apply=apply,
                ):
                    deleted += 1

    return {
        "deleted": deleted,
        "stale_system": dict(stale_system),
        "planned_deletes": planned_deletes,
        "blocked_deletes": blocked_deletes,
        "technical_child_cascades": technical_child_cascades,
    }


def _load_current_maps(connection: sqlite3.Connection) -> dict[str, dict[Any, Any]]:
    maps: dict[str, dict[Any, Any]] = defaultdict(dict)
    if _table_exists(connection, "suppliers"):
        for row in connection.execute("SELECT id, code FROM suppliers").fetchall():
            maps["supplier_id_by_code"][normalize_text(row["code"])] = row["id"]
    if _table_exists(connection, "fitting_manufacturers"):
        for row in connection.execute("SELECT id, code FROM fitting_manufacturers").fetchall():
            maps["manufacturer_id_by_code"][normalize_text(row["code"])] = row["id"]
    if _table_exists(connection, "fitting_series"):
        for row in connection.execute(
            """
            SELECT fitting_series.id, fitting_series.code, fitting_manufacturers.code AS manufacturer_code
            FROM fitting_series
            JOIN fitting_manufacturers ON fitting_manufacturers.id = fitting_series.manufacturer_id
            """
        ).fetchall():
            maps["series_id_by_key"][(normalize_text(row["manufacturer_code"]), normalize_text(row["code"]))] = row["id"]
    if _table_exists(connection, "fitting_categories"):
        for row in connection.execute("SELECT id, code FROM fitting_categories").fetchall():
            maps["category_id_by_code"][normalize_text(row["code"])] = row["id"]
    if _table_exists(connection, "fitting_products"):
        for row in connection.execute("SELECT id, article FROM fitting_products").fetchall():
            maps["product_id_by_article"][normalize_text(row["article"])] = row["id"]
    if _table_exists(connection, "fittings"):
        for row in connection.execute("SELECT id, article, owner_user_id, is_system FROM fittings").fetchall():
            maps["fitting_id_by_article"][normalize_text(row["article"])] = row["id"]
            maps["fitting_article_by_id"][row["id"]] = row["article"]
            maps["fitting_meta_by_id"][row["id"]] = {
                "owner_user_id": row["owner_user_id"],
                "is_system": row["is_system"],
            }
    if _table_exists(connection, "service_catalog_items"):
        for row in connection.execute("SELECT id, source, external_code FROM service_catalog_items").fetchall():
            maps["service_item_id_by_key"][_service_item_key(dict(row))] = row["id"]
    if _table_exists(connection, "fitting_hole_templates"):
        for row in connection.execute(
            """
            SELECT fitting_hole_templates.id, fittings.article, fitting_hole_templates.bundle_key, fitting_hole_templates.template_type, fitting_hole_templates.side
            FROM fitting_hole_templates
            JOIN fittings ON fittings.id = fitting_hole_templates.fitting_id
            """
        ).fetchall():
            maps["template_id_by_key"][
                (
                    normalize_text(row["article"]),
                    normalize_text(row["bundle_key"]),
                    normalize_text(row["template_type"]),
                    normalize_text(row["side"]),
                )
            ] = row["id"]
    return maps


def _maybe_backup(database_path: Path, apply: bool) -> Path | None:
    if not apply:
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    source = sqlite3.connect(database_path)
    target = sqlite3.connect(backup_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return backup_path


def import_bundle(database_path: Path, bundle_path: Path, apply: bool) -> dict[str, Any]:
    manifest, catalog = _validate_bundle(bundle_path)
    sync_policy = manifest["entity_sync_policy"]
    backup_path = _maybe_backup(database_path, apply)
    connection = _open_sqlite(database_path, readonly=False)
    summary = defaultdict(int)
    media_copy_count = 0
    conflicts: list[str] = []
    skipped: list[str] = []
    try:
        _integrity_check(connection)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")

        entities = catalog["entities"]
        current_maps = _load_current_maps(connection)
        counts_before = {table_name: _count_table(connection, table_name) for table_name in entities.keys()}

        # service_catalog_items first, because hole rules depend on them
        if _table_exists(connection, "service_catalog_items"):
            for row in entities.get("service_catalog_items", []):
                desired = dict(row)
                desired["owner_user_id"] = desired.get("owner_user_id") or None
                key = _service_item_key(desired)
                desired["source"] = key[0]
                desired["external_code"] = key[1]
                existing = _existing_row(
                    connection,
                    "service_catalog_items",
                    "source = ? AND external_code = ?",
                    key,
                )
                if existing is not None and normalize_text(existing["owner_user_id"]):
                    conflicts.append(f"service_catalog_items:{key}")
                    continue
                action = _upsert_row(
                    connection,
                    "service_catalog_items",
                    desired,
                    key_columns=["source", "external_code"],
                    ownership_column="owner_user_id",
                )
                summary[action] += 1
            current_maps = _load_current_maps(connection)

        if _table_exists(connection, "suppliers"):
            for row in entities.get("suppliers", []):
                desired = {
                    **row,
                    "owner_user_id": None,
                    "is_system": 1,
                    "is_active": 1 if row.get("is_active") in (None, True, 1) else 0,
                }
                media_url = _copy_logo_media(bundle_path, row, database_path.parent / "data" / "uploads" / "supplier-logos") if apply and row.get("media_path") else None
                if row.get("media_path") and media_url is None and not apply:
                    media_copy_count += 1
                if media_url:
                    desired["logo_url"] = media_url
                action = _upsert_row(
                    connection,
                    "suppliers",
                    desired,
                    key_columns=["code"],
                    ownership_column="owner_user_id",
                )
                summary[action] += 1
            current_maps = _load_current_maps(connection)

        if _table_exists(connection, "fitting_manufacturers"):
            for row in entities.get("fitting_manufacturers", []):
                desired = {
                    **row,
                    "is_active": 1 if row.get("is_active") in (None, True, 1) else 0,
                }
                media_url = _copy_logo_media(bundle_path, row, database_path.parent / "data" / "uploads" / "fitting-manufacturer-logos") if apply and row.get("media_path") else None
                if row.get("media_path") and media_url is None and not apply:
                    media_copy_count += 1
                if media_url:
                    desired["logo_url"] = media_url
                action = _upsert_row(
                    connection,
                    "fitting_manufacturers",
                    desired,
                    key_columns=["code"],
                )
                summary[action] += 1
            current_maps = _load_current_maps(connection)

        if _table_exists(connection, "fitting_series"):
            for row in entities.get("fitting_series", []):
                manufacturer_id = current_maps["manufacturer_id_by_code"].get(normalize_text(row.get("manufacturer_code")))
                if manufacturer_id is None:
                    skipped.append(f"fitting_series:{row.get('code')}")
                    continue
                desired = {**row, "manufacturer_id": manufacturer_id}
                action = _upsert_row(
                    connection,
                    "fitting_series",
                    desired,
                    key_columns=["manufacturer_id", "code"],
                )
                summary[action] += 1
            current_maps = _load_current_maps(connection)

        if _table_exists(connection, "fitting_categories"):
            for row in entities.get("fitting_categories", []):
                desired = dict(row)
                action = _upsert_row(
                    connection,
                    "fitting_categories",
                    desired,
                    key_columns=["code"],
                )
                summary[action] += 1
            current_maps = _load_current_maps(connection)

        if _table_exists(connection, "fitting_products"):
            for row in entities.get("fitting_products", []):
                desired = dict(row)
                desired["manufacturer_id"] = current_maps["manufacturer_id_by_code"].get(normalize_text(row.get("manufacturer_code")))
                desired["series_id"] = current_maps["series_id_by_key"].get(
                    (normalize_text(row.get("series_manufacturer_code")), normalize_text(row.get("series_code")))
                )
                desired["category_id"] = current_maps["category_id_by_code"].get(normalize_text(row.get("category_code")))
                action = _upsert_row(
                    connection,
                    "fitting_products",
                    desired,
                    key_columns=["article"],
                )
                summary[action] += 1
            current_maps = _load_current_maps(connection)

        if _table_exists(connection, "fittings"):
            for row in entities.get("fittings", []):
                desired = dict(row)
                desired["technical_product_id"] = current_maps["product_id_by_article"].get(normalize_text(row.get("technical_product_article")))
                desired["owner_user_id"] = None
                desired["is_system"] = 1 if row.get("is_system") in (None, True, 1) else 0
                desired["is_active"] = 1 if row.get("is_active") in (None, True, 1) else 0
                action = _upsert_row(
                    connection,
                    "fittings",
                    desired,
                    key_columns=["article"],
                    ownership_column="owner_user_id",
                )
                summary[action] += 1
            current_maps = _load_current_maps(connection)

        if _table_exists(connection, "fitting_hole_templates"):
            for row in entities.get("fitting_hole_templates", []):
                fitting_id = current_maps["fitting_id_by_article"].get(normalize_text(row.get("fitting_article")))
                if fitting_id is None:
                    skipped.append(f"fitting_hole_templates:{row.get('name')}")
                    continue
                desired = dict(row)
                desired["fitting_id"] = fitting_id
                action = _upsert_row(
                    connection,
                    "fitting_hole_templates",
                    desired,
                    key_columns=["fitting_id", "bundle_key", "template_type", "side"],
                )
                summary[action] += 1
            current_maps = _load_current_maps(connection)

        if _table_exists(connection, "fitting_hole_points"):
            for row in entities.get("fitting_hole_points", []):
                template_id = current_maps["template_id_by_key"].get(
                    (
                        normalize_text(row.get("fitting_article")),
                        normalize_text(row.get("template_bundle_key")),
                        normalize_text(row.get("template_type")),
                        normalize_text(row.get("side")),
                    )
                )
                if template_id is None:
                    continue
                desired = dict(row)
                desired["template_id"] = template_id
                action = _upsert_row(
                    connection,
                    "fitting_hole_points",
                    desired,
                    key_columns=["template_id", "order_index", "label"],
                )
                summary[action] += 1

        if _table_exists(connection, "fitting_images"):
            grouped_fitting_images = _group_fitting_image_rows(
                entities,
                bundle_path,
                current_maps,
                skipped=skipped,
                conflicts=conflicts,
            )
            for fitting_id, fitting_rows in grouped_fitting_images.items():
                inserted, updated, unchanged = _sync_fitting_images_for_fitting(
                    connection,
                    fitting_id,
                    fitting_rows,
                    current_maps=current_maps,
                    skipped=skipped,
                )
                summary["inserted"] += inserted
                summary["updated"] += updated
                summary["unchanged"] += unchanged

        if _table_exists(connection, "fitting_hole_service_rules"):
            for row in entities.get("fitting_hole_service_rules", []):
                key = (
                    normalize_text(row.get("source")),
                    normalize_text(row.get("operation")),
                    row.get("diameter_min_mm"),
                    row.get("diameter_max_mm"),
                    row.get("depth_min_mm"),
                    row.get("depth_max_mm"),
                    normalize_text(row.get("service_source")),
                    normalize_text(row.get("service_external_code")),
                    row.get("priority"),
                    normalize_text(row.get("city")),
                )
                service_id = current_maps["service_item_id_by_key"].get(
                    (normalize_text(row.get("service_source")), normalize_text(row.get("service_external_code")))
                )
                if service_id is None:
                    skipped.append(f"fitting_hole_service_rules:{key}")
                    continue
                desired = dict(row)
                desired["service_catalog_item_id"] = service_id
                existing = _existing_row(
                    connection,
                    "fitting_hole_service_rules",
                    "source = ? AND operation = ? AND COALESCE(diameter_min_mm, '') = COALESCE(?, '') AND COALESCE(diameter_max_mm, '') = COALESCE(?, '') AND COALESCE(depth_min_mm, '') = COALESCE(?, '') AND COALESCE(depth_max_mm, '') = COALESCE(?, '') AND service_catalog_item_id = ? AND COALESCE(priority, 0) = COALESCE(?, 0) AND COALESCE(city, '') = COALESCE(?, '')",
                    (
                        desired["source"],
                        desired["operation"],
                        desired["diameter_min_mm"],
                        desired["diameter_max_mm"],
                        desired["depth_min_mm"],
                        desired["depth_max_mm"],
                        desired["service_catalog_item_id"],
                        desired["priority"],
                        desired["city"],
                    ),
                )
                if existing is None:
                    connection.execute(
                        """
                        INSERT INTO fitting_hole_service_rules (
                            operation,
                            diameter_min_mm,
                            diameter_max_mm,
                            depth_min_mm,
                            depth_max_mm,
                            service_catalog_item_id,
                            source,
                            city,
                            is_active,
                            priority,
                            notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            desired["operation"],
                            desired["diameter_min_mm"],
                            desired["diameter_max_mm"],
                            desired["depth_min_mm"],
                            desired["depth_max_mm"],
                            desired["service_catalog_item_id"],
                            desired["source"],
                            desired["city"],
                            1 if desired.get("is_active") in (None, True, 1) else 0,
                            desired["priority"],
                            desired["notes"],
                        ),
                    )
                    summary["inserted"] += 1
                else:
                    summary["unchanged"] += 1

        if _table_exists(connection, "fitting_supplier_offers"):
            for row in entities.get("fitting_supplier_offers", []):
                fitting_id = current_maps["fitting_id_by_article"].get(normalize_text(row.get("fitting_article")))
                supplier_id = current_maps["supplier_id_by_code"].get(normalize_text(row.get("supplier_code")))
                if fitting_id is None or supplier_id is None:
                    skipped.append(f"fitting_supplier_offers:{row.get('id')}")
                    continue
                external_product_id = normalize_text(row.get("external_product_id"))
                if external_product_id:
                    existing = _existing_row(
                        connection,
                        "fitting_supplier_offers",
                        "fitting_id = ? AND supplier_id = ? AND external_product_id = ?",
                        (fitting_id, supplier_id, external_product_id),
                    )
                else:
                    existing = _existing_row(
                        connection,
                        "fitting_supplier_offers",
                        "fitting_id = ? AND supplier_id = ? AND external_product_id IS NULL",
                        (fitting_id, supplier_id),
                    )
                desired = dict(row)
                desired["fitting_id"] = fitting_id
                desired["supplier_id"] = supplier_id
                if existing is None:
                    connection.execute(
                        """
                        INSERT INTO fitting_supplier_offers (
                            fitting_id,
                            supplier_id,
                            article,
                            external_product_id,
                            source_url,
                            price,
                            currency,
                            unit,
                            stock,
                            is_active,
                            priority,
                            parsed_at,
                            price_updated_at,
                            source_payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            desired["fitting_id"],
                            desired["supplier_id"],
                            desired.get("article"),
                            desired.get("external_product_id"),
                            desired.get("source_url"),
                            desired.get("price"),
                            desired.get("currency"),
                            desired.get("unit"),
                            desired.get("stock"),
                            1 if desired.get("is_active") in (None, True, 1) else 0,
                            desired.get("priority") or 0,
                            desired.get("parsed_at"),
                            desired.get("price_updated_at"),
                            desired.get("source_payload_json"),
                        ),
                    )
                    summary["inserted"] += 1
                else:
                    summary["unchanged"] += 1

        stale_result = _sync_stale_system_catalog(
            connection,
            entities,
            sync_policy=sync_policy,
            apply=apply,
        )
        summary["deleted"] += stale_result["deleted"]

        if apply:
            connection.commit()
        else:
            connection.rollback()
        _integrity_check(connection)
        counts_after = {
            table_name: _count_table(connection, table_name)
            for table_name in (
                "service_catalog_items",
                "suppliers",
                "fitting_manufacturers",
                "fitting_series",
                "fitting_categories",
                "fitting_products",
                "fittings",
                "fitting_hole_templates",
                "fitting_hole_points",
                "fitting_images",
                "fitting_hole_service_rules",
                "fitting_supplier_offers",
            )
        }
        planned_delete_breakdown = dict(Counter(item["entity"] for item in stale_result["planned_deletes"]))
        blocked_delete_breakdown = dict(Counter(item["entity"] for item in stale_result["blocked_deletes"]))
        technical_child_cascade_breakdown = [
            {
                "fitting_id": item["fitting_id"],
                "natural_key": item["natural_key"],
                "technical_children": {name: list(ids) for name, ids in item["technical_children"].items()},
            }
            for item in stale_result["technical_child_cascades"]
        ]
        referenced_upsert_breakdown = {
            table_name: {
                "included": len(entities.get(table_name, [])),
                "untouched": max(counts_before.get(table_name, 0) - len(entities.get(table_name, [])), 0),
            }
            for table_name, policy in sync_policy.items()
            if policy == "referenced_upsert"
        }
        return {
            "apply": apply,
            "backup_path": backup_path,
            "summary": dict(summary),
            "media_copy_count": media_copy_count,
            "skipped": skipped,
            "conflicts": conflicts,
            "stale_system": stale_result["stale_system"],
            "planned_deletes": stale_result["planned_deletes"],
            "blocked_deletes": stale_result["blocked_deletes"],
            "planned_delete_breakdown": planned_delete_breakdown,
            "blocked_delete_breakdown": blocked_delete_breakdown,
            "technical_child_cascade_breakdown": technical_child_cascade_breakdown,
            "referenced_upsert_breakdown": referenced_upsert_breakdown,
            "counts_before": counts_before,
            "counts_after": counts_after,
            "sync_policy": sync_policy,
            "manifest": manifest,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).expanduser().resolve()
    bundle_path = Path(args.bundle).expanduser().resolve()
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")
    if not bundle_path.exists():
        raise SystemExit(f"Bundle does not exist: {bundle_path}")

    result = import_bundle(database_path, bundle_path, args.apply)
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    print(f"Bundle: {bundle_path}")
    if result.get("backup_path"):
        print(f"Backup: {result['backup_path']}")
    print("Summary: " + ", ".join(f"{k}={v}" for k, v in sorted(result["summary"].items())))
    print(f"Planned media copies: {result['media_copy_count']}")
    if result.get("planned_delete_breakdown"):
        print("Planned deletes:")
        for table_name, count in sorted(result["planned_delete_breakdown"].items()):
            print(f"  - {table_name}: {count}")
    if result.get("blocked_delete_breakdown"):
        print("Blocked deletes:")
        for table_name, count in sorted(result["blocked_delete_breakdown"].items()):
            print(f"  - {table_name}: {count}")
    if result.get("technical_child_cascade_breakdown"):
        print("Technical child cascades:")
        for item in result["technical_child_cascade_breakdown"]:
            print(f"  - fitting {item['natural_key']} ({item['fitting_id']}):")
            for table_name, ids in sorted(item["technical_children"].items()):
                print(f"      {table_name}: {ids}")
    if result.get("referenced_upsert_breakdown"):
        print("Referenced-upsert entities:")
        for table_name, counts in sorted(result["referenced_upsert_breakdown"].items()):
            print(f"  - {table_name}: {counts['included']} included / {counts['untouched']} untouched")
    print("Counts after: " + ", ".join(f"{k}={v}" for k, v in sorted(result["counts_after"].items())))
    if result["skipped"]:
        print("Skipped:")
        for item in result["skipped"][:20]:
            print(f"  - {item}")
    if result["conflicts"]:
        print("Conflicts:")
        for item in result["conflicts"][:20]:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
