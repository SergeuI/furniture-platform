"""Safely add entitlement feature and plan entitlement tables.

This script is additive only:
- dry-run by default
- backup before apply
- no data rows are changed
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


FEATURE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS entitlement_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feature_key VARCHAR NOT NULL UNIQUE,
        name_uk VARCHAR NOT NULL,
        description_uk TEXT,
        category VARCHAR NOT NULL,
        value_type VARCHAR NOT NULL,
        enum_options_json JSON,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK (trim(feature_key) <> ''),
        CHECK (trim(name_uk) <> ''),
        CHECK (trim(category) <> ''),
        CHECK (value_type IN ('boolean', 'integer', 'decimal', 'text', 'enum'))
    )
"""


PLAN_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS plan_entitlements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feature_id INTEGER NOT NULL,
        plan_code VARCHAR NOT NULL,
        bool_value BOOLEAN,
        integer_value INTEGER,
        decimal_value NUMERIC,
        text_value TEXT,
        is_unlimited BOOLEAN NOT NULL DEFAULT 0,
        is_not_applicable BOOLEAN NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(feature_id) REFERENCES entitlement_features(id),
        UNIQUE(feature_id, plan_code),
        CHECK (trim(plan_code) <> ''),
        CHECK (plan_code IN ('trial', 'free', 'pro', 'business')),
        CHECK (NOT (is_unlimited AND is_not_applicable))
    )
"""


INDEXES = {
    "ix_entitlement_features_category": (
        "CREATE INDEX IF NOT EXISTS ix_entitlement_features_category "
        "ON entitlement_features (category)"
    ),
    "ix_plan_entitlements_feature_id": (
        "CREATE INDEX IF NOT EXISTS ix_plan_entitlements_feature_id "
        "ON plan_entitlements (feature_id)"
    ),
    "ix_plan_entitlements_plan_code": (
        "CREATE INDEX IF NOT EXISTS ix_plan_entitlements_plan_code "
        "ON plan_entitlements (plan_code)"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add entitlement feature and plan entitlement schema.",
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


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone()
    return row is not None


def _build_plan(connection: sqlite3.Connection) -> dict[str, list[str]]:
    return {
        "tables": [
            table_name
            for table_name in ("entitlement_features", "plan_entitlements")
            if not _table_exists(connection, table_name)
        ],
        "indexes": [
            index_name
            for index_name in INDEXES
            if not _index_exists(connection, index_name)
        ],
    }


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _apply_plan(connection: sqlite3.Connection, plan: dict[str, list[str]]) -> None:
    connection.execute("BEGIN")
    try:
        if "entitlement_features" in plan["tables"]:
            connection.execute(FEATURE_TABLE_SQL)

        if "plan_entitlements" in plan["tables"]:
            connection.execute(PLAN_TABLE_SQL)

        for index_name in plan["indexes"]:
            connection.execute(INDEXES[index_name])
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def _print_plan(
    database_path: Path,
    plan: dict[str, list[str]],
    apply: bool,
    backup_path: Path | None,
) -> None:
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    print("Missing tables:", ", ".join(plan["tables"]) or "none")
    print("Missing indexes:", ", ".join(plan["indexes"]) or "none")


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()

    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        plan = _build_plan(connection)
        backup_path = _create_backup(database_path) if args.apply else None
        if args.apply and any(plan.values()):
            _apply_plan(connection, plan)
        _print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
