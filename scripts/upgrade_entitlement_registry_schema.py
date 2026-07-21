"""Add the system/custom marker to entitlement_features.

This script is additive only:
- dry-run by default
- backup before apply
- no registry seed data
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


TABLE_NAME = "entitlement_features"
COLUMN_NAME = "is_system"
INDEX_NAME = "ix_entitlement_features_is_system"

ALTER_COLUMN_SQL = """
    ALTER TABLE entitlement_features
    ADD COLUMN is_system BOOLEAN NOT NULL DEFAULT 0
"""

INDEX_SQL = """
    CREATE INDEX IF NOT EXISTS ix_entitlement_features_is_system
    ON entitlement_features (is_system)
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add the system/custom entitlement registry marker.",
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


def _column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def _index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone()
    return row is not None


def _build_plan(connection: sqlite3.Connection) -> dict[str, object]:
    if not _table_exists(connection, TABLE_NAME):
        return {
            "prerequisite_missing": True,
            "missing_tables": [TABLE_NAME],
            "missing_columns": [],
            "missing_indexes": [],
        }

    return {
        "prerequisite_missing": False,
        "missing_tables": [],
        "missing_columns": [
            COLUMN_NAME
            for column_name in (COLUMN_NAME,)
            if not _column_exists(connection, TABLE_NAME, column_name)
        ],
        "missing_indexes": [
            INDEX_NAME
            for index_name in (INDEX_NAME,)
            if not _index_exists(connection, index_name)
        ],
    }


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _apply_plan(connection: sqlite3.Connection, plan: dict[str, object]) -> None:
    if plan["prerequisite_missing"]:
        raise SystemExit(
            "Table entitlement_features does not exist. Run the stage 1 schema migration first."
        )

    connection.execute("BEGIN")
    try:
        if COLUMN_NAME in plan["missing_columns"]:
            connection.execute(ALTER_COLUMN_SQL)

        for index_name in plan["missing_indexes"]:
            if index_name == INDEX_NAME:
                connection.execute(INDEX_SQL)
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def _print_plan(
    database_path: Path,
    plan: dict[str, object],
    apply: bool,
    backup_path: Path | None,
) -> None:
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    if plan["prerequisite_missing"]:
        print("Prerequisite missing: entitlement_features table is absent")
        return
    print("Missing columns:", ", ".join(plan["missing_columns"]) or "none")
    print("Missing indexes:", ", ".join(plan["missing_indexes"]) or "none")


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()

    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        plan = _build_plan(connection)
        has_changes = not plan["prerequisite_missing"] and any(
            plan[key]
            for key in ("missing_columns", "missing_indexes")
        )
        backup_path = _create_backup(database_path) if args.apply and has_changes else None
        if args.apply and has_changes:
            _apply_plan(connection, plan)
        elif args.apply and plan["prerequisite_missing"]:
            _print_plan(database_path, plan, args.apply, backup_path)
            raise SystemExit(1)
        _print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
