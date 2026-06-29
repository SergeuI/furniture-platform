"""Idempotently extend fitting schema with source metadata and hole templates."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


FITTING_COLUMNS = {
    "source": "TEXT",
    "brand": "TEXT",
    "description": "TEXT",
    "unit": "TEXT DEFAULT 'шт'",
    "currency": "TEXT DEFAULT 'UAH'",
    "parsed_at": "DATETIME",
    "price_updated_at": "DATETIME",
    "source_payload_json": "TEXT",
}

TABLES = {
    "fitting_hole_templates": """
        CREATE TABLE IF NOT EXISTS fitting_hole_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fitting_id INTEGER NOT NULL,
            name VARCHAR,
            template_type VARCHAR,
            side VARCHAR,
            coordinate_system VARCHAR,
            mounting_variant_key TEXT NOT NULL DEFAULT 'surface_mount',
            is_default BOOLEAN NOT NULL DEFAULT 1,
            notes TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(fitting_id) REFERENCES fittings (id)
        )
    """,
    "fitting_hole_points": """
        CREATE TABLE IF NOT EXISTS fitting_hole_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            label VARCHAR,
            x_mm FLOAT,
            y_mm FLOAT,
            z_mm FLOAT,
            diameter_mm FLOAT,
            depth_mm FLOAT,
            side VARCHAR,
            operation VARCHAR,
            order_index INTEGER NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 1,
            mirrored BOOLEAN NOT NULL DEFAULT 0,
            notes TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(template_id) REFERENCES fitting_hole_templates (id)
        )
    """,
}

TABLE_COLUMNS = {
    "fitting_hole_templates": {
        "mounting_variant_key": "TEXT NOT NULL DEFAULT 'surface_mount'",
    },
}

INDEXES = {
    "ix_fittings_source": "CREATE INDEX IF NOT EXISTS ix_fittings_source ON fittings (source)",
    "ix_fittings_brand": "CREATE INDEX IF NOT EXISTS ix_fittings_brand ON fittings (brand)",
    "ix_fitting_hole_templates_fitting_id": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_hole_templates_fitting_id "
        "ON fitting_hole_templates (fitting_id)"
    ),
    "ix_fitting_hole_templates_template_type": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_hole_templates_template_type "
        "ON fitting_hole_templates (template_type)"
    ),
    "ix_fitting_hole_templates_side": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_hole_templates_side "
        "ON fitting_hole_templates (side)"
    ),
    "ix_fitting_hole_points_template_id": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_hole_points_template_id "
        "ON fitting_hole_points (template_id)"
    ),
    "ix_fitting_hole_points_side": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_hole_points_side "
        "ON fitting_hole_points (side)"
    ),
    "ix_fitting_hole_points_operation": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_hole_points_operation "
        "ON fitting_hole_points (operation)"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extend furniture_platform.db fitting schema.",
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
    return parser.parse_args()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone()
    return row is not None


def column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def ensure_safe_database(database_path: Path) -> None:
    if database_path.name == "mebli_calculator.db":
        raise SystemExit("Refusing to modify mebli_calculator.db.")
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")


def create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def build_plan(connection: sqlite3.Connection) -> dict[str, list]:
    if not table_exists(connection, "fittings"):
        raise SystemExit("Table 'fittings' does not exist.")

    existing_columns = column_names(connection, "fittings")
    missing_columns = [
        column_name
        for column_name in FITTING_COLUMNS
        if column_name not in existing_columns
    ]
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
    missing_table_columns: list[tuple[str, str]] = []
    for table_name, columns in TABLE_COLUMNS.items():
        if not table_exists(connection, table_name):
            continue
        existing_columns = column_names(connection, table_name)
        for column_name in columns:
            if column_name not in existing_columns:
                missing_table_columns.append((table_name, column_name))
    return {
        "columns": missing_columns,
        "tables": missing_tables,
        "indexes": missing_indexes,
        "table_columns": missing_table_columns,
    }


def apply_plan(connection: sqlite3.Connection, plan: dict[str, list]) -> None:
    for column_name in plan["columns"]:
        connection.execute(
            f"ALTER TABLE fittings ADD COLUMN {column_name} {FITTING_COLUMNS[column_name]}"
        )

    for table_name in plan["tables"]:
        connection.execute(TABLES[table_name])

    for index_name in plan["indexes"]:
        connection.execute(INDEXES[index_name])

    for table_name, column_name in plan.get("table_columns", []):
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {TABLE_COLUMNS[table_name][column_name]}"
        )

    connection.commit()


def print_plan(
    database_path: Path,
    plan: dict[str, list],
    apply: bool,
    backup_path: Path | None,
) -> None:
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    print("Missing fitting columns:", ", ".join(plan["columns"]) or "none")
    print("Missing tables:", ", ".join(plan["tables"]) or "none")
    print("Missing indexes:", ", ".join(plan["indexes"]) or "none")
    missing_table_columns = plan.get("table_columns", [])
    if missing_table_columns:
        formatted_columns = ", ".join(
            f"{table}.{column}" for table, column in missing_table_columns
        )
    else:
        formatted_columns = "none"
    print("Missing table columns:", formatted_columns)


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()
    ensure_safe_database(database_path)

    with sqlite3.connect(database_path) as connection:
        plan = build_plan(connection)
        backup_path = create_backup(database_path) if args.apply else None
        if args.apply:
            apply_plan(connection, plan)
        print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
