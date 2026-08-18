from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.fitting_catalog_sync import normalize_text, sha256_file


FORMAT_VERSION = 1
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
    return normalize_text(row.get("source")) or "", normalize_text(row.get("external_code")) or ""


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
        for row in connection.execute("SELECT id, article FROM fittings").fetchall():
            maps["fitting_id_by_article"][normalize_text(row["article"])] = row["id"]
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
    backup_path = _maybe_backup(database_path, apply)
    connection = _open_sqlite(database_path, readonly=False)
    summary = defaultdict(int)
    media_copy_count = 0
    conflicts: list[str] = []
    skipped: list[str] = []
    try:
        _integrity_check(connection)
        if apply:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")

        entities = catalog["entities"]
        current_maps = _load_current_maps(connection)

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
            for row in entities.get("fitting_images", []):
                fitting_id = current_maps["fitting_id_by_article"].get(normalize_text(row.get("fitting_article")))
                if fitting_id is None:
                    continue
                media_path = normalize_text(row.get("media_path"))
                if not media_path:
                    continue
                image_bytes = (bundle_path / media_path).read_bytes()
                desired = {
                    "fitting_id": fitting_id,
                    "sort_order": row.get("sort_order"),
                    "is_primary": 1 if row.get("is_primary") in (True, 1) else 0,
                    "source_url": row.get("source_url"),
                    "image_cached_bytes": image_bytes,
                    "image_cached_content_type": row.get("image_cached_content_type"),
                    "image_sha256": row.get("image_sha256"),
                }
                existing = _existing_row(
                    connection,
                    "fitting_images",
                    "fitting_id = ? AND sort_order = ?",
                    (fitting_id, row.get("sort_order")),
                )
                if existing is not None and (
                    existing["image_sha256"] == desired["image_sha256"]
                    and existing["image_cached_content_type"] == desired["image_cached_content_type"]
                    and existing["source_url"] == desired["source_url"]
                ):
                    summary["unchanged"] += 1
                    continue
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
                            desired["fitting_id"],
                            desired["sort_order"],
                            desired["is_primary"],
                            desired["source_url"],
                            desired["image_cached_bytes"],
                            desired["image_cached_content_type"],
                            desired["image_sha256"],
                        ),
                    )
                    summary["inserted"] += 1
                else:
                    connection.execute(
                        """
                        UPDATE fitting_images
                        SET is_primary = ?,
                            source_url = ?,
                            image_cached_bytes = ?,
                            image_cached_content_type = ?,
                            image_sha256 = ?
                        WHERE fitting_id = ? AND sort_order = ?
                        """,
                        (
                            desired["is_primary"],
                            desired["source_url"],
                            desired["image_cached_bytes"],
                            desired["image_cached_content_type"],
                            desired["image_sha256"],
                            fitting_id,
                            row.get("sort_order"),
                        ),
                    )
                    summary["updated"] += 1

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
        return {
            "apply": apply,
            "backup_path": backup_path,
            "summary": dict(summary),
            "media_copy_count": media_copy_count,
            "skipped": skipped,
            "conflicts": conflicts,
            "counts_after": counts_after,
            "manifest": manifest,
        }
    except Exception:
        if apply:
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
    print(f"Media copies: {result['media_copy_count']}")
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
