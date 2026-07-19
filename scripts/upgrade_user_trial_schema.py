"""Safely add 7-day trial columns to the users table.

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


TRIAL_COLUMNS = {
    "trial_started_at": "DATETIME",
    "trial_ends_at": "DATETIME",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add trial period columns to the users table.",
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


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _build_plan(connection: sqlite3.Connection) -> list[str]:
    if not _table_exists(connection, "users"):
        raise SystemExit("Table 'users' does not exist.")

    existing_columns = _column_names(connection, "users")
    return [
        column_name
        for column_name in TRIAL_COLUMNS
        if column_name not in existing_columns
    ]


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _apply_plan(connection: sqlite3.Connection, plan: list[str]) -> None:
    for column_name in plan:
        connection.execute(
            f"ALTER TABLE users ADD COLUMN {column_name} {TRIAL_COLUMNS[column_name]}"
        )

    connection.commit()


def _print_plan(database_path: Path, plan: list[str], apply: bool, backup_path: Path | None) -> None:
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    print("Missing columns:", ", ".join(plan) or "none")
    print("Trial duration days: 7")


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()

    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        plan = _build_plan(connection)
        backup_path = _create_backup(database_path) if args.apply else None
        if args.apply and plan:
            _apply_plan(connection, plan)
        _print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
