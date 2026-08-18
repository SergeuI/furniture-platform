"""Add supplier ownership markers without changing supplier code uniqueness.

This migration is additive only:
- dry-run by default
- backup before apply
- no supplier rows are deleted
- existing suppliers are backfilled as system suppliers
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


TABLE_NAME = "suppliers"
PREREQUISITE_TABLES = ("users", "suppliers")

ALTER_OWNER_SQL = """
    ALTER TABLE suppliers
    ADD COLUMN owner_user_id VARCHAR REFERENCES users (id)
"""

ALTER_IS_SYSTEM_SQL = """
    ALTER TABLE suppliers
    ADD COLUMN is_system BOOLEAN NOT NULL DEFAULT 1
"""

ALTER_LOGO_SQL = """
    ALTER TABLE suppliers
    ADD COLUMN logo_url VARCHAR
"""

INDEXES = {
    "ix_suppliers_owner_user_id": (
        "CREATE INDEX IF NOT EXISTS ix_suppliers_owner_user_id "
        "ON suppliers (owner_user_id)"
    ),
    "ix_suppliers_is_system": (
        "CREATE INDEX IF NOT EXISTS ix_suppliers_is_system "
        "ON suppliers (is_system)"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add supplier ownership markers to furniture_platform.db.",
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
    row = _exec_sql(
        connection,
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = _exec_sql(connection, f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def _index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
    row = _exec_sql(
        connection,
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone()
    return row is not None


def _integrity_check(connection: sqlite3.Connection) -> str:
    row = _exec_sql(connection, "PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else "unknown"


def _foreign_key_check(connection: sqlite3.Connection) -> list[tuple]:
    return _exec_sql(connection, "PRAGMA foreign_key_check").fetchall()


def _exec_sql(connection, statement: str, params: tuple | dict | None = None):
    if hasattr(connection, "exec_driver_sql"):
        if params is None:
            return connection.exec_driver_sql(statement)
        return connection.exec_driver_sql(statement, params)
    if params is None:
        return connection.execute(statement)
    return connection.execute(statement, params)


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _build_plan(connection: sqlite3.Connection) -> dict[str, object]:
    missing_prerequisites = [
        table_name
        for table_name in PREREQUISITE_TABLES
        if not _table_exists(connection, table_name)
    ]

    if missing_prerequisites:
        return {
            "prerequisite_missing": True,
            "missing_prerequisites": missing_prerequisites,
            "missing_columns": [],
            "missing_indexes": [],
            "existing_supplier_count": 0,
        }

    return {
        "prerequisite_missing": False,
        "missing_prerequisites": [],
        "missing_columns": [
            column_name
            for column_name in ("owner_user_id", "is_system", "logo_url")
            if not _column_exists(connection, TABLE_NAME, column_name)
        ],
        "missing_indexes": [
            index_name
            for index_name in INDEXES
            if not _index_exists(connection, index_name)
        ],
        "existing_supplier_count": int(
            _exec_sql(connection, "SELECT COUNT(*) FROM suppliers").fetchone()[0]
        ),
    }


def _apply_plan(connection: sqlite3.Connection, plan: dict[str, object]) -> None:
    if plan["prerequisite_missing"]:
        missing = ", ".join(plan["missing_prerequisites"]) or "unknown"
        raise SystemExit(f"Missing prerequisite tables: {missing}")

    use_explicit_transaction = not hasattr(connection, "exec_driver_sql")

    _exec_sql(connection, "PRAGMA foreign_keys = ON")
    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed before supplier ownership update")

    if use_explicit_transaction:
        _exec_sql(connection, "BEGIN")
    try:
        if "owner_user_id" in plan["missing_columns"]:
            _exec_sql(connection, ALTER_OWNER_SQL)
        if "is_system" in plan["missing_columns"]:
            _exec_sql(connection, ALTER_IS_SYSTEM_SQL)
        if "logo_url" in plan["missing_columns"]:
            _exec_sql(connection, ALTER_LOGO_SQL)

        _exec_sql(
            connection,
            """
            UPDATE suppliers
            SET is_system = 1,
                owner_user_id = NULL
            """
        )

        for index_name in plan["missing_indexes"]:
            _exec_sql(connection, INDEXES[index_name])
    except Exception:
        if use_explicit_transaction:
            connection.rollback()
        raise
    else:
        if use_explicit_transaction:
            connection.commit()

    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed after supplier ownership update")

    if _foreign_key_check(connection):
        raise SystemExit("Foreign key check failed after supplier ownership update")


def ensure_suppliers_ownership_schema(connection: sqlite3.Connection) -> None:
    plan = _build_plan(connection)
    if plan["prerequisite_missing"]:
        missing = ", ".join(plan["missing_prerequisites"]) or "unknown"
        raise SystemExit(f"Missing prerequisite tables: {missing}")

    if any(plan[key] for key in ("missing_columns", "missing_indexes")):
        _apply_plan(connection, plan)


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
        print("Prerequisites missing:", ", ".join(plan["missing_prerequisites"]) or "unknown")
        return
    print("Missing columns:", ", ".join(plan["missing_columns"]) or "none")
    print("Missing indexes:", ", ".join(plan["missing_indexes"]) or "none")
    print("Existing suppliers:", plan["existing_supplier_count"])


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
