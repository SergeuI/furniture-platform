"""Safely add registration identity and challenge schema.

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


USER_COLUMNS = {
    "registration_status": "VARCHAR",
    "phone_verified_at": "DATETIME",
}

TABLES = {
    "registration_identities": """
        CREATE TABLE IF NOT EXISTS registration_identities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identity_type VARCHAR NOT NULL,
            identity_value_normalized VARCHAR NOT NULL,
            first_user_id VARCHAR,
            verified_at DATETIME,
            trial_used_at DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(identity_type, identity_value_normalized)
        )
    """,
    "registration_challenges": """
        CREATE TABLE IF NOT EXISTS registration_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR,
            channel VARCHAR NOT NULL,
            token_hash VARCHAR(64) NOT NULL,
            expected_identity_type VARCHAR NOT NULL,
            expected_identity_value_normalized VARCHAR NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'pending',
            attempts_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            expires_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            verified_at DATETIME,
            consumed_at DATETIME,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(token_hash)
        )
    """,
}

TABLE_COLUMNS = {
    "registration_identities": {
        "identity_type": "VARCHAR NOT NULL",
        "identity_value_normalized": "VARCHAR NOT NULL",
        "first_user_id": "VARCHAR",
        "verified_at": "DATETIME",
        "trial_used_at": "DATETIME",
        "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    },
    "registration_challenges": {
        "user_id": "VARCHAR",
        "channel": "VARCHAR NOT NULL",
        "token_hash": "VARCHAR(64) NOT NULL",
        "expected_identity_type": "VARCHAR NOT NULL",
        "expected_identity_value_normalized": "VARCHAR NOT NULL",
        "status": "VARCHAR NOT NULL DEFAULT 'pending'",
        "attempts_count": "INTEGER NOT NULL DEFAULT 0",
        "max_attempts": "INTEGER NOT NULL DEFAULT 5",
        "expires_at": "DATETIME NOT NULL",
        "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "verified_at": "DATETIME",
        "consumed_at": "DATETIME",
        "updated_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    },
}

INDEXES = {
    "ix_registration_identities_identity_type": (
        "CREATE INDEX IF NOT EXISTS ix_registration_identities_identity_type "
        "ON registration_identities (identity_type)"
    ),
    "ix_registration_identities_identity_value_normalized": (
        "CREATE INDEX IF NOT EXISTS ix_registration_identities_identity_value_normalized "
        "ON registration_identities (identity_value_normalized)"
    ),
    "ix_registration_challenges_user_id": (
        "CREATE INDEX IF NOT EXISTS ix_registration_challenges_user_id "
        "ON registration_challenges (user_id)"
    ),
    "ix_registration_challenges_status": (
        "CREATE INDEX IF NOT EXISTS ix_registration_challenges_status "
        "ON registration_challenges (status)"
    ),
    "ix_registration_challenges_expires_at": (
        "CREATE INDEX IF NOT EXISTS ix_registration_challenges_expires_at "
        "ON registration_challenges (expires_at)"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add registration identity schema.",
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


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _build_plan(connection: sqlite3.Connection) -> dict[str, list]:
    if not _table_exists(connection, "users"):
        raise SystemExit("Table 'users' does not exist.")

    existing_user_columns = _column_names(connection, "users")
    missing_user_columns = [
        column_name
        for column_name in USER_COLUMNS
        if column_name not in existing_user_columns
    ]

    missing_tables = [
        table_name
        for table_name in TABLES
        if not _table_exists(connection, table_name)
    ]

    missing_table_columns: list[tuple[str, str]] = []
    for table_name, columns in TABLE_COLUMNS.items():
        if not _table_exists(connection, table_name):
            continue

        existing_columns = _column_names(connection, table_name)
        for column_name in columns:
            if column_name not in existing_columns:
                missing_table_columns.append((table_name, column_name))

    missing_indexes = [
        index_name
        for index_name in INDEXES
        if not _index_exists(connection, index_name)
    ]

    return {
        "user_columns": missing_user_columns,
        "tables": missing_tables,
        "table_columns": missing_table_columns,
        "indexes": missing_indexes,
    }


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _apply_plan(connection: sqlite3.Connection, plan: dict[str, list]) -> None:
    for column_name in plan["user_columns"]:
        connection.execute(
            f"ALTER TABLE users ADD COLUMN {column_name} {USER_COLUMNS[column_name]}"
        )

    for table_name in plan["tables"]:
        connection.execute(TABLES[table_name])

    for table_name, column_name in plan["table_columns"]:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {TABLE_COLUMNS[table_name][column_name]}"
        )

    for index_name in plan["indexes"]:
        connection.execute(INDEXES[index_name])

    connection.commit()


def _print_plan(database_path: Path, plan: dict[str, list], apply: bool, backup_path: Path | None) -> None:
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    print("Missing user columns:", ", ".join(plan["user_columns"]) or "none")
    print("Missing tables:", ", ".join(plan["tables"]) or "none")
    if plan["table_columns"]:
        print(
            "Missing table columns:",
            ", ".join(f"{table}.{column}" for table, column in plan["table_columns"]),
        )
    else:
        print("Missing table columns: none")
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
