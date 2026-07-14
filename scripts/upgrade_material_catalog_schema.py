"""Idempotently extend and backfill the material catalog schema."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.material_catalog_service import (
    detect_material_source_site,
    resolve_material_image_payload,
)


MATERIAL_COLUMNS = {
    "source": "TEXT",
    "product_type": "TEXT",
    "image_source_url": "TEXT",
    "image_cached_hash": "TEXT",
    "imported_at": "DATETIME",
    "static_updated_at": "DATETIME",
}

MATERIAL_EDGE_COLUMNS = {
    "source": "TEXT",
    "product_type": "TEXT",
    "image_source_url": "TEXT",
    "image_cached_hash": "TEXT",
    "imported_at": "DATETIME",
    "static_updated_at": "DATETIME",
}

MATERIAL_PRICE_PROMO_COLUMNS = {
    "old_price": "REAL",
    "is_promo": "BOOLEAN NOT NULL DEFAULT 0",
    "discount_percent": "REAL",
    "promo_label": "TEXT",
    "promo_valid_until": "DATE",
    "source_checked_at": "DATETIME",
}

MATERIAL_PRICE_COLUMNS = {
    **MATERIAL_PRICE_PROMO_COLUMNS,
    "currency": "TEXT",
    "availability": "TEXT",
}

MATERIAL_EDGE_PRICE_COLUMNS = {
    "currency": "TEXT",
    "availability": "TEXT",
}

TABLES = {
    "material_user_links": """
        CREATE TABLE IF NOT EXISTS material_user_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_article VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            source VARCHAR,
            product_type VARCHAR,
            source_url VARCHAR,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(material_article, user_id)
        )
    """,
}

INDEXES = {
    "ix_material_user_links_material_article": (
        "CREATE INDEX IF NOT EXISTS ix_material_user_links_material_article "
        "ON material_user_links (material_article)"
    ),
    "ix_material_user_links_user_id": (
        "CREATE INDEX IF NOT EXISTS ix_material_user_links_user_id "
        "ON material_user_links (user_id)"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extend and backfill the material catalog SQLite schema.",
    )
    parser.add_argument(
        "--database",
        default="furniture_platform.db",
        help="Path to furniture_platform.db.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag the script only prints a dry-run plan.",
    )
    parser.add_argument(
        "--material-price-promo-only",
        action="store_true",
        help="Only inspect or apply promo columns for material_prices.",
    )
    parser.add_argument(
        "--warm-images",
        action="store_true",
        help="Download and cache missing image BLOBs during apply.",
    )
    return parser.parse_args()


def ensure_safe_database(database_path: Path) -> None:
    if database_path.name == "mebli_calculator.db":
        raise SystemExit("Refusing to modify mebli_calculator.db.")
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone() is not None


def column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _sha256(image_bytes: bytes | None) -> str | None:
    if not image_bytes:
        return None
    return hashlib.sha256(image_bytes).hexdigest()


def build_plan(connection: sqlite3.Connection, *, promo_only: bool = False) -> dict[str, object]:
    if promo_only:
        missing_price_columns = [
            column_name
            for column_name in MATERIAL_PRICE_PROMO_COLUMNS
            if column_name not in column_names(connection, "material_prices")
        ] if table_exists(connection, "material_prices") else list(MATERIAL_PRICE_PROMO_COLUMNS)
        return {
            "promo_only": True,
            "missing_tables": [],
            "missing_indexes": [],
            "missing_material_columns": [],
            "missing_edge_columns": [],
            "missing_price_columns": missing_price_columns,
            "missing_edge_price_columns": [],
            "material_rows": [],
            "edge_rows": [],
        }

    missing_tables = [
        table_name
        for table_name in TABLES
        if not table_exists(connection, table_name)
    ]
    missing_indexes = [
        index_name
        for index_name in INDEXES
        if not index_exists(connection, index_name)
    ]
    missing_material_columns = [
        column_name
        for column_name in MATERIAL_COLUMNS
        if column_name not in column_names(connection, "materials")
    ] if table_exists(connection, "materials") else list(MATERIAL_COLUMNS)
    missing_edge_columns = [
        column_name
        for column_name in MATERIAL_EDGE_COLUMNS
        if column_name not in column_names(connection, "material_edge_options")
    ] if table_exists(connection, "material_edge_options") else list(MATERIAL_EDGE_COLUMNS)
    missing_price_columns = [
        column_name
        for column_name in MATERIAL_PRICE_COLUMNS
        if column_name not in column_names(connection, "material_prices")
    ] if table_exists(connection, "material_prices") else list(MATERIAL_PRICE_COLUMNS)
    missing_edge_price_columns = [
        column_name
        for column_name in MATERIAL_EDGE_PRICE_COLUMNS
        if column_name not in column_names(connection, "material_edge_prices")
    ] if table_exists(connection, "material_edge_prices") else list(MATERIAL_EDGE_PRICE_COLUMNS)

    material_rows = []
    edge_rows = []

    if table_exists(connection, "materials"):
        material_rows = connection.execute(
            "SELECT id FROM materials ORDER BY id"
        ).fetchall()

    if table_exists(connection, "material_edge_options"):
        edge_rows = connection.execute(
            "SELECT id FROM material_edge_options ORDER BY id"
        ).fetchall()

    return {
        "missing_tables": missing_tables,
        "missing_indexes": missing_indexes,
        "missing_material_columns": missing_material_columns,
        "missing_edge_columns": missing_edge_columns,
        "missing_price_columns": missing_price_columns,
        "missing_edge_price_columns": missing_edge_price_columns,
        "material_rows": material_rows,
        "edge_rows": edge_rows,
    }


def print_plan(database_path: Path, plan: dict[str, object], apply: bool, backup_path: Path | None) -> None:
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    print("Missing tables:", ", ".join(plan["missing_tables"]) or "none")
    print("Missing indexes:", ", ".join(plan["missing_indexes"]) or "none")
    print("Missing material columns:", ", ".join(plan["missing_material_columns"]) or "none")
    print("Missing edge columns:", ", ".join(plan["missing_edge_columns"]) or "none")
    print("Missing material price columns:", ", ".join(plan["missing_price_columns"]) or "none")
    print("Missing edge price columns:", ", ".join(plan["missing_edge_price_columns"]) or "none")
    print(f"Materials needing backfill: {len(plan['material_rows'])}")
    print(f"Edges needing backfill: {len(plan['edge_rows'])}")
    if plan.get("promo_only"):
        print("Backfill skipped: yes")
        print("Warming skipped: yes")
        print("Material edge prices excluded: yes")


def _add_missing_columns(connection: sqlite3.Connection, table_name: str, column_map: dict[str, str]) -> None:
    existing = column_names(connection, table_name)
    for column_name, column_type in column_map.items():
        if column_name in existing:
            continue
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _upsert_image_payload(
    *,
    row_id: int,
    table_name: str,
    source_url: str | None,
    image_value: str | None,
    article: str | None,
    city: str | None,
    cookie_override: str | None,
    connection: sqlite3.Connection,
) -> bool:
    image_payload = resolve_material_image_payload(
        article=article or "",
        stored_image=image_value,
        source_url=source_url,
        city=city,
        cookie_override=cookie_override,
    )

    if not image_payload or not image_payload.get("bytes"):
        return False

    if table_name == "materials":
        connection.execute(
            """
            UPDATE materials
            SET image_cached_bytes = ?,
                image_cached_content_type = ?,
                image_cached_hash = ?,
                image_source_url = COALESCE(image_source_url, ?)
            WHERE id = ?
            """,
            (
                image_payload["bytes"],
                image_payload.get("content_type"),
                _sha256(image_payload["bytes"]),
                image_payload.get("resolved_url") or image_value or source_url,
                row_id,
            ),
        )
    else:
        connection.execute(
            """
            UPDATE material_edge_options
            SET image_cached_bytes = ?,
                image_cached_content_type = ?,
                image_cached_hash = ?,
                image_source_url = COALESCE(image_source_url, ?)
            WHERE id = ?
            """,
            (
                image_payload["bytes"],
                image_payload.get("content_type"),
                _sha256(image_payload["bytes"]),
                image_payload.get("resolved_url") or image_value or source_url,
                row_id,
            ),
        )

    return True


def apply_plan(connection: sqlite3.Connection, plan: dict[str, object], warm_images: bool) -> dict[str, int]:
    if plan["missing_tables"]:
        for table_name in plan["missing_tables"]:
            connection.execute(TABLES[table_name])

    for index_name in plan["missing_indexes"]:
        connection.execute(INDEXES[index_name])

    if table_exists(connection, "materials"):
        _add_missing_columns(connection, "materials", MATERIAL_COLUMNS)
    if table_exists(connection, "material_edge_options"):
        _add_missing_columns(connection, "material_edge_options", MATERIAL_EDGE_COLUMNS)
    if table_exists(connection, "material_prices"):
        _add_missing_columns(connection, "material_prices", MATERIAL_PRICE_COLUMNS)
    if table_exists(connection, "material_edge_prices"):
        _add_missing_columns(connection, "material_edge_prices", MATERIAL_EDGE_PRICE_COLUMNS)

    material_rows_all = connection.execute(
        """
        SELECT id, article, category, image, source_url, image_cached_bytes,
               source, product_type, image_source_url, image_cached_hash,
               imported_at, static_updated_at
        FROM materials
        """
    ).fetchall()
    edge_rows_all = connection.execute(
        """
        SELECT id, material_article, edge_key, article, image, source_url,
               image_cached_bytes, source, product_type, image_source_url,
               image_cached_hash, imported_at, static_updated_at
        FROM material_edge_options
        """
    ).fetchall()

    now = datetime.now().isoformat(timespec="seconds")
    for row in material_rows_all:
        row_id, article, category, image_value, source_url, image_bytes, source, product_type, image_source_url, image_cached_hash, imported_at, static_updated_at = row
        updates = {}
        if not source:
            updates["source"] = detect_material_source_site(source_url)
        if not product_type:
            updates["product_type"] = category
        if not image_source_url:
            updates["image_source_url"] = image_value
        if image_bytes and not image_cached_hash:
            updates["image_cached_hash"] = _sha256(image_bytes)
        if not imported_at and static_updated_at:
            updates["imported_at"] = static_updated_at
        if not static_updated_at and imported_at:
            updates["static_updated_at"] = imported_at
        if not imported_at and not static_updated_at:
            updates["imported_at"] = now
        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            connection.execute(
                f"UPDATE materials SET {assignments} WHERE id = ?",
                (*updates.values(), row_id),
            )

    for row in edge_rows_all:
        row_id, material_article, edge_key, article, image_value, source_url, image_bytes, source, product_type, image_source_url, image_cached_hash, imported_at, static_updated_at = row
        updates = {}
        if not source:
            updates["source"] = detect_material_source_site(source_url)
        if not product_type:
            updates["product_type"] = edge_key
        if not image_source_url:
            updates["image_source_url"] = image_value
        if image_bytes and not image_cached_hash:
            updates["image_cached_hash"] = _sha256(image_bytes)
        if not imported_at and static_updated_at:
            updates["imported_at"] = static_updated_at
        if not static_updated_at and imported_at:
            updates["static_updated_at"] = imported_at
        if not imported_at and not static_updated_at:
            updates["imported_at"] = now
        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            connection.execute(
                f"UPDATE material_edge_options SET {assignments} WHERE id = ?",
                (*updates.values(), row_id),
            )

    material_rows = connection.execute(
        "SELECT id, article, image, source_url FROM materials WHERE image_cached_bytes IS NULL OR length(image_cached_bytes) = 0"
    ).fetchall()
    edge_rows = connection.execute(
        "SELECT id, material_article, edge_key, article, image, source_url FROM material_edge_options WHERE image_cached_bytes IS NULL OR length(image_cached_bytes) = 0"
    ).fetchall()

    warmed_materials = 0
    warmed_edges = 0
    if warm_images:
        for row_id, article, image_value, source_url in material_rows:
            if _upsert_image_payload(
                row_id=row_id,
                table_name="materials",
                source_url=source_url,
                image_value=image_value,
                article=article,
                city=None,
                cookie_override=None,
                connection=connection,
            ):
                warmed_materials += 1

        for row_id, material_article, edge_key, article, image_value, source_url in edge_rows:
            if _upsert_image_payload(
                row_id=row_id,
                table_name="material_edge_options",
                source_url=source_url,
                image_value=image_value,
                article=article or material_article,
                city=None,
                cookie_override=None,
                connection=connection,
            ):
                warmed_edges += 1

    connection.commit()
    return {
        "warmed_materials": warmed_materials,
        "warmed_edges": warmed_edges,
    }


def apply_material_price_promo_plan(connection: sqlite3.Connection) -> dict[str, int]:
    if table_exists(connection, "material_prices"):
        _add_missing_columns(connection, "material_prices", MATERIAL_PRICE_PROMO_COLUMNS)

    connection.commit()
    return {
        "warmed_materials": 0,
        "warmed_edges": 0,
    }


def main() -> int:
    args = parse_args()
    database_path = Path(args.database).resolve()
    ensure_safe_database(database_path)

    with sqlite3.connect(database_path) as connection:
        promo_only = bool(args.material_price_promo_only)
        plan = build_plan(connection, promo_only=promo_only)
        backup_path = create_backup(database_path) if args.apply else None

        if args.apply and promo_only:
            apply_result = apply_material_price_promo_plan(connection)
        elif args.apply:
            apply_result = apply_plan(connection, plan, warm_images=bool(args.warm_images))
        else:
            apply_result = {"warmed_materials": 0, "warmed_edges": 0}

        print_plan(database_path, plan, args.apply, backup_path)
        print("Warmed materials:", apply_result["warmed_materials"])
        print("Warmed edges:", apply_result["warmed_edges"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
