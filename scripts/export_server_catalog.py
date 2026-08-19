from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.fitting_catalog_sync import (
    DEFAULT_BUNDLE_ROOT,
    bundle_output_dir,
    normalize_text,
    normalize_source_url,
    sha256_bytes,
    sha256_file,
    slugify_bundle_name,
    uploads_path_from_logo_url,
)


FORMAT_VERSION = 2
DEFAULT_DATABASE_NAME = "furniture_platform.db"
MEDIA_ROOT_NAME = "media"
LOGO_MEDIA_DIRS = {
    "suppliers": "supplier-logos",
    "fitting_manufacturers": "fitting-manufacturer-logos",
}
ENTITY_SYNC_POLICY = {
    "suppliers": "authoritative_full",
    "fitting_manufacturers": "authoritative_full",
    "fitting_series": "authoritative_full",
    "fitting_categories": "authoritative_full",
    "fitting_products": "authoritative_full",
    "fittings": "authoritative_full",
    "fitting_images": "child_of_authoritative_parent",
    "fitting_supplier_offers": "child_of_authoritative_parent",
    "fitting_hole_templates": "referenced_upsert",
    "fitting_hole_points": "referenced_upsert",
    "fitting_hole_service_rules": "referenced_upsert",
    "service_catalog_items": "referenced_upsert",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the global fitting catalog bundle.")
    parser.add_argument(
        "--database",
        default=DEFAULT_DATABASE_NAME,
        help="Path to furniture_platform.db.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output bundle directory. Defaults to dist/server-catalog-sync/<timestamp>.",
    )
    return parser.parse_args()


def _open_readonly(database_path: Path) -> sqlite3.Connection:
    uri = f"file:{database_path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _rows(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    cursor = connection.execute(query, parameters)
    return [dict(row) for row in cursor.fetchall()]


def _row_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()]


def _copy_logo_media(
    *,
    row: dict[str, Any],
    bundle_root: Path,
    entity_dir: str,
) -> dict[str, Any]:
    media_path = uploads_path_from_logo_url(row.get("logo_url"))
    exported_path = None
    missing = None
    if media_path is not None and media_path.exists():
        relative_path = Path(MEDIA_ROOT_NAME) / entity_dir / media_path.name
        target_path = bundle_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(media_path, target_path)
        exported_path = relative_path.as_posix()
    elif media_path is not None:
        missing = media_path.as_posix()
    row["media_path"] = exported_path
    row["missing_media_path"] = missing
    return row


def _fitting_image_media_path(content_type: str | None, sha256_value: str) -> str:
    suffix = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }.get((content_type or "").strip().lower(), "bin")
    return f"{MEDIA_ROOT_NAME}/fitting-images/{sha256_value}.{suffix}"


def _export_service_catalog_items(
    connection: sqlite3.Connection,
    fitting_hole_service_rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    referenced_ids = {
        normalize_text(row.get("service_catalog_item_id"))
        for row in fitting_hole_service_rules
    }
    referenced_ids = {item_id for item_id in referenced_ids if item_id}
    if not referenced_ids:
        return []
    placeholders = ", ".join("?" for _ in referenced_ids)
    query = f"""
        SELECT *
        FROM service_catalog_items
        WHERE id IN ({placeholders})
        ORDER BY source, external_code, id
    """
    return _rows(connection, query, tuple(sorted(referenced_ids)))


def export_bundle(database_path: Path, output_dir: Path) -> dict[str, Any]:
    connection = _open_readonly(database_path)
    try:
        entities: dict[str, list[dict[str, Any]]] = {}
        missing_media: list[dict[str, Any]] = []

        if _table_exists(connection, "suppliers"):
            suppliers = _rows(
                connection,
                """
                SELECT id, code, name, logo_url, owner_user_id, is_system, is_active, created_at, updated_at
                FROM suppliers
                WHERE COALESCE(is_system, 1) = 1 AND owner_user_id IS NULL
                ORDER BY code, id
                """,
            )
            entities["suppliers"] = []
            for row in suppliers:
                exported = _copy_logo_media(
                    row=row,
                    bundle_root=output_dir,
                    entity_dir=LOGO_MEDIA_DIRS["suppliers"],
                )
                if exported["missing_media_path"]:
                    missing_media.append(
                        {
                            "entity": "suppliers",
                            "id": exported["id"],
                            "code": exported["code"],
                            "missing_media_path": exported["missing_media_path"],
                        }
                    )
                entities["suppliers"].append(exported)

        if _table_exists(connection, "fitting_manufacturers"):
            manufacturers = _rows(
                connection,
                """
                SELECT id, code, name, description, website_url, logo_url, country_code, is_active, sort_order, created_at, updated_at
                FROM fitting_manufacturers
                ORDER BY code, id
                """,
            )
            entities["fitting_manufacturers"] = []
            for row in manufacturers:
                exported = _copy_logo_media(
                    row=row,
                    bundle_root=output_dir,
                    entity_dir=LOGO_MEDIA_DIRS["fitting_manufacturers"],
                )
                if exported["missing_media_path"]:
                    missing_media.append(
                        {
                            "entity": "fitting_manufacturers",
                            "id": exported["id"],
                            "code": exported["code"],
                            "missing_media_path": exported["missing_media_path"],
                        }
                    )
                entities["fitting_manufacturers"].append(exported)

        for table_name in ("fitting_series", "fitting_categories", "fitting_products"):
            if _table_exists(connection, table_name):
                entities[table_name] = _rows(connection, f"SELECT * FROM {table_name} ORDER BY id")

        if _table_exists(connection, "fittings"):
            entities["fittings"] = _rows(
                connection,
                """
                SELECT *
                FROM fittings
                WHERE COALESCE(is_system, 1) = 1 AND owner_user_id IS NULL
                ORDER BY article, id
                """,
            )
        else:
            entities["fittings"] = []

        if _table_exists(connection, "fitting_hole_templates"):
            fitting_ids = [row["id"] for row in entities["fittings"]]
            if fitting_ids:
                placeholders = ", ".join("?" for _ in fitting_ids)
                entities["fitting_hole_templates"] = _rows(
                    connection,
                    f"SELECT * FROM fitting_hole_templates WHERE fitting_id IN ({placeholders}) ORDER BY fitting_id, id",
                    tuple(fitting_ids),
                )
            else:
                entities["fitting_hole_templates"] = []
        else:
            entities["fitting_hole_templates"] = []

        if _table_exists(connection, "fitting_hole_points"):
            template_ids = [row["id"] for row in entities["fitting_hole_templates"]]
            if template_ids:
                placeholders = ", ".join("?" for _ in template_ids)
                entities["fitting_hole_points"] = _rows(
                    connection,
                    f"SELECT * FROM fitting_hole_points WHERE template_id IN ({placeholders}) ORDER BY template_id, order_index, id",
                    tuple(template_ids),
                )
            else:
                entities["fitting_hole_points"] = []
        else:
            entities["fitting_hole_points"] = []

        if _table_exists(connection, "fitting_images"):
            fitting_ids = [row["id"] for row in entities["fittings"]]
            if fitting_ids:
                placeholders = ", ".join("?" for _ in fitting_ids)
                image_rows = _rows(
                    connection,
                    f"""
                    SELECT *
                    FROM fitting_images
                    WHERE fitting_id IN ({placeholders})
                    ORDER BY fitting_id, sort_order, id
                    """,
                    tuple(fitting_ids),
                )
            else:
                image_rows = []
            entities["fitting_images"] = []
            for row in image_rows:
                content = row.pop("image_cached_bytes", None)
                content_type = normalize_text(row.get("image_cached_content_type"))
                sha256_value = normalize_text(row.get("image_sha256")) or (
                    sha256_bytes(content) if isinstance(content, (bytes, bytearray)) else None
                )
                if not sha256_value:
                    continue
                media_path = _fitting_image_media_path(content_type, sha256_value)
                target_path = output_dir / media_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, (bytes, bytearray)):
                    target_path.write_bytes(bytes(content))
                    row["bytes_length"] = len(content)
                else:
                    row["bytes_length"] = None
                row["media_path"] = media_path
                row["image_cached_content_type"] = content_type
                row["image_sha256"] = sha256_value
                entities["fitting_images"].append(row)
        else:
            entities["fitting_images"] = []

        if _table_exists(connection, "fitting_supplier_offers"):
            fitting_ids = {row["id"] for row in entities["fittings"]}
            supplier_codes = {row["code"] for row in entities["suppliers"]}
            fitting_id_by_article = {normalize_text(row.get("article")): row["id"] for row in entities["fittings"]}
            supplier_id_by_code = {row["code"]: row["id"] for row in entities["suppliers"]}
            offer_rows = _rows(connection, "SELECT * FROM fitting_supplier_offers ORDER BY fitting_id, supplier_id, id")
            exported_offers: list[dict[str, Any]] = []
            for row in offer_rows:
                if row["fitting_id"] not in fitting_ids or row["supplier_id"] not in supplier_id_by_code.values():
                    continue
                exported_offers.append(row)
            entities["fitting_supplier_offers"] = exported_offers
        else:
            entities["fitting_supplier_offers"] = []

        if _table_exists(connection, "fitting_hole_service_rules"):
            entities["fitting_hole_service_rules"] = _rows(
                connection,
                """
                SELECT *
                FROM fitting_hole_service_rules
                ORDER BY source, operation, priority, id
                """,
            )
        else:
            entities["fitting_hole_service_rules"] = []

        entities["service_catalog_items"] = _export_service_catalog_items(
            connection,
            entities["fitting_hole_service_rules"],
        )

        supplier_code_by_id = {
            row["id"]: row.get("code")
            for row in entities.get("suppliers", [])
        }
        manufacturer_code_by_id = {
            row["id"]: row.get("code")
            for row in entities.get("fitting_manufacturers", [])
        }
        series_row_by_id = {row["id"]: row for row in entities.get("fitting_series", [])}
        category_code_by_id = {
            row["id"]: row.get("code")
            for row in entities.get("fitting_categories", [])
        }
        product_article_by_id = {
            row["id"]: normalize_text(row.get("article"))
            for row in entities.get("fitting_products", [])
        }
        fitting_row_by_id = {row["id"]: row for row in entities.get("fittings", [])}
        fitting_article_by_id = {
            row["id"]: normalize_text(row.get("article"))
            for row in entities.get("fittings", [])
        }
        service_item_by_id = {row["id"]: row for row in entities.get("service_catalog_items", [])}

        for row in entities.get("fitting_products", []):
            row["manufacturer_code"] = manufacturer_code_by_id.get(row.get("manufacturer_id"))
            series_row = series_row_by_id.get(row.get("series_id"))
            if series_row is not None:
                row["series_code"] = series_row.get("code")
                row["series_manufacturer_code"] = manufacturer_code_by_id.get(series_row.get("manufacturer_id"))
            else:
                row["series_code"] = None
                row["series_manufacturer_code"] = None
            row["category_code"] = category_code_by_id.get(row.get("category_id"))

        for row in entities.get("fitting_series", []):
            row["manufacturer_code"] = manufacturer_code_by_id.get(row.get("manufacturer_id"))

        for row in entities.get("fittings", []):
            row["technical_product_article"] = product_article_by_id.get(row.get("technical_product_id"))
            row["source_site"] = normalize_text(row.get("source")) or None

        for row in entities.get("fitting_supplier_offers", []):
            row["fitting_article"] = fitting_article_by_id.get(row.get("fitting_id"))
            row["supplier_code"] = supplier_code_by_id.get(row.get("supplier_id"))

        for row in entities.get("fitting_images", []):
            row["fitting_article"] = fitting_article_by_id.get(row.get("fitting_id"))

        for row in entities.get("fitting_hole_templates", []):
            row["fitting_article"] = fitting_article_by_id.get(row.get("fitting_id"))

        template_article_by_id = {
            row["id"]: row.get("fitting_article")
            for row in entities.get("fitting_hole_templates", [])
        }
        for row in entities.get("fitting_hole_points", []):
            row["fitting_article"] = template_article_by_id.get(row.get("template_id"))
            template_row = next((item for item in entities.get("fitting_hole_templates", []) if item.get("id") == row.get("template_id")), None)
            row["template_bundle_key"] = template_row.get("bundle_key") if template_row else None
            row["template_type"] = template_row.get("template_type") if template_row else None
            row["side"] = template_row.get("side") if template_row else None

        for row in entities.get("fitting_hole_service_rules", []):
            service_row = service_item_by_id.get(row.get("service_catalog_item_id"))
            row["service_source"] = service_row.get("source") if service_row else None
            row["service_external_code"] = service_row.get("external_code") if service_row else None

        counts = {name: len(rows) for name, rows in entities.items()}
        export_payload = {
            "format_version": FORMAT_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_database": str(database_path.resolve()),
            "entity_counts": counts,
            "entity_sync_policy": ENTITY_SYNC_POLICY,
            "entities": entities,
            "missing_media": missing_media,
        }

        catalog_json = json.dumps(export_payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        catalog_path = output_dir / "catalog.json"
        catalog_path.write_text(catalog_json, encoding="utf-8")
        catalog_sha256 = sha256_file(catalog_path)

        media_entries = []
        for entity_name in ("suppliers", "fitting_manufacturers"):
            for row in entities.get(entity_name, []):
                media_path = row.get("media_path")
                if not media_path:
                    continue
                source_path = output_dir / Path(media_path)
                if source_path.exists():
                    media_entries.append(
                        {
                            "entity": entity_name,
                            "id": row["id"],
                            "path": media_path,
                            "sha256": sha256_file(source_path),
                            "size": source_path.stat().st_size,
                        }
                    )

        for row in entities.get("fitting_images", []):
            media_path = row.get("media_path")
            if not media_path:
                continue
            source_path = output_dir / Path(media_path)
            media_entries.append(
                {
                    "entity": "fitting_images",
                    "id": row["id"],
                    "path": media_path,
                    "sha256": sha256_file(source_path),
                    "size": source_path.stat().st_size,
                }
            )

        manifest = {
            "format_version": FORMAT_VERSION,
            "generated_at": export_payload["generated_at"],
            "source_database": export_payload["source_database"],
            "catalog_sha256": catalog_sha256,
            "entity_counts": counts,
            "entity_sync_policy": ENTITY_SYNC_POLICY,
            "media_files": media_entries,
            "missing_media": missing_media,
            "missing_media_count": len(missing_media),
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        return {
            "bundle_path": output_dir,
            "counts": counts,
            "missing_media": missing_media,
            "manifest": manifest,
            "catalog": export_payload,
        }
    finally:
        connection.close()


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).expanduser().resolve()
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    if args.output:
        output_dir = Path(args.output).expanduser().resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = bundle_output_dir(timestamp)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / MEDIA_ROOT_NAME).mkdir(parents=True, exist_ok=True)

    result = export_bundle(database_path, output_dir)
    counts = result["counts"]
    print(f"Bundle: {output_dir}")
    print("Counts: " + ", ".join(f"{name}={count}" for name, count in sorted(counts.items())))
    print("Missing media: " + (str(len(result["missing_media"])) if result["missing_media"] else "0"))
    if result["missing_media"]:
        for item in result["missing_media"]:
            print(
                "  - "
                f"entity={item['entity']} "
                f"id={item['id']} "
                f"code={item.get('code') or ''} "
                f"missing={item['missing_media_path']}"
            )


if __name__ == "__main__":
    main()
