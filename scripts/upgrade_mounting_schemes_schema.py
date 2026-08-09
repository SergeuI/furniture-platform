"""Add the mounting schemes foundation on top of the existing mounting-nodes schema."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


TABLES = {
    "mounting_schemes": """
        CREATE TABLE IF NOT EXISTS mounting_schemes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(128) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (trim(code) <> ''),
            CHECK (trim(name) <> '')
        )
    """,
    "mounting_scheme_nodes": """
        CREATE TABLE IF NOT EXISTS mounting_scheme_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id INTEGER NOT NULL,
            node_id INTEGER NOT NULL,
            group_key VARCHAR(64) NOT NULL,
            quantity_per_group INTEGER NOT NULL DEFAULT 1,
            role_code VARCHAR(64),
            order_index INTEGER NOT NULL DEFAULT 0,
            is_required BOOLEAN NOT NULL DEFAULT 1,
            CHECK (trim(group_key) <> ''),
            CHECK (quantity_per_group > 0),
            FOREIGN KEY(scheme_id) REFERENCES mounting_schemes (id) ON DELETE CASCADE,
            FOREIGN KEY(node_id) REFERENCES mounting_nodes (id)
        )
    """,
    "mounting_scheme_placement_rules": """
        CREATE TABLE IF NOT EXISTS mounting_scheme_placement_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id INTEGER NOT NULL,
            group_key VARCHAR(64) NOT NULL,
            distribution_mode VARCHAR(32) NOT NULL DEFAULT 'equal',
            min_group_count INTEGER NOT NULL DEFAULT 1,
            max_group_count INTEGER,
            fixed_group_count INTEGER,
            start_offset_mm INTEGER,
            end_offset_mm INTEGER,
            max_spacing_mm INTEGER,
            fixed_spacing_mm INTEGER,
            CHECK (trim(group_key) <> ''),
            CHECK (min_group_count > 0),
            CHECK (max_group_count IS NULL OR max_group_count >= min_group_count),
            CHECK (fixed_group_count IS NULL OR fixed_group_count > 0),
            CHECK (start_offset_mm IS NULL OR start_offset_mm >= 0),
            CHECK (end_offset_mm IS NULL OR end_offset_mm >= 0),
            CHECK (max_spacing_mm IS NULL OR max_spacing_mm > 0),
            CHECK (fixed_spacing_mm IS NULL OR fixed_spacing_mm > 0),
            FOREIGN KEY(scheme_id) REFERENCES mounting_schemes (id) ON DELETE CASCADE,
            UNIQUE(scheme_id, group_key)
        )
    """,
}

INDEXES = {
    "ix_mounting_schemes_name": "CREATE INDEX IF NOT EXISTS ix_mounting_schemes_name ON mounting_schemes (name)",
    "ix_mounting_schemes_is_active": "CREATE INDEX IF NOT EXISTS ix_mounting_schemes_is_active ON mounting_schemes (is_active)",
    "ix_mounting_scheme_nodes_scheme_id": "CREATE INDEX IF NOT EXISTS ix_mounting_scheme_nodes_scheme_id ON mounting_scheme_nodes (scheme_id)",
    "ix_mounting_scheme_nodes_node_id": "CREATE INDEX IF NOT EXISTS ix_mounting_scheme_nodes_node_id ON mounting_scheme_nodes (node_id)",
    "ix_mounting_scheme_nodes_group_key": "CREATE INDEX IF NOT EXISTS ix_mounting_scheme_nodes_group_key ON mounting_scheme_nodes (group_key)",
    "ix_mounting_scheme_nodes_role_code": "CREATE INDEX IF NOT EXISTS ix_mounting_scheme_nodes_role_code ON mounting_scheme_nodes (role_code)",
    "ix_mounting_scheme_nodes_order_index": "CREATE INDEX IF NOT EXISTS ix_mounting_scheme_nodes_order_index ON mounting_scheme_nodes (order_index)",
    "ix_mounting_scheme_placement_rules_scheme_id": "CREATE INDEX IF NOT EXISTS ix_mounting_scheme_placement_rules_scheme_id ON mounting_scheme_placement_rules (scheme_id)",
    "ix_mounting_scheme_placement_rules_group_key": "CREATE INDEX IF NOT EXISTS ix_mounting_scheme_placement_rules_group_key ON mounting_scheme_placement_rules (group_key)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add the mounting schemes foundation to furniture_platform.db.",
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


def _execute(connection, sql: str, params: tuple | list | None = None):
    if hasattr(connection, "exec_driver_sql"):
        return connection.exec_driver_sql(sql, params or ())
    return connection.execute(sql, params or ())


def _table_exists(connection, table_name: str) -> bool:
    row = _execute(
        connection,
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _index_exists(connection, index_name: str) -> bool:
    row = _execute(
        connection,
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone()
    return row is not None


def _integrity_check(connection) -> str:
    row = _execute(connection, "PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else "unknown"


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _build_plan(connection: sqlite3.Connection) -> dict[str, object]:
    missing_prerequisites = [
        table_name
        for table_name in ("mounting_nodes",)
        if not _table_exists(connection, table_name)
    ]

    if missing_prerequisites:
        return {
            "prerequisite_missing": True,
            "missing_prerequisites": missing_prerequisites,
            "missing_tables": [],
            "missing_indexes": [],
        }

    return {
        "prerequisite_missing": False,
        "missing_prerequisites": [],
        "missing_tables": [
            table_name
            for table_name in TABLES
            if not _table_exists(connection, table_name)
        ],
        "missing_indexes": [
            index_name
            for index_name in INDEXES
            if not _index_exists(connection, index_name)
        ],
    }


def ensure_mounting_schemes_schema(connection) -> None:
    plan = _build_plan(connection)
    if plan["prerequisite_missing"]:
        missing = ", ".join(plan["missing_prerequisites"]) or "unknown"
        raise SystemExit(f"Missing prerequisite tables: {missing}")

    _execute(connection, "PRAGMA foreign_keys = ON")
    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed before schema update")

    for table_name in plan["missing_tables"]:
        _execute(connection, TABLES[table_name])

    for index_name in plan["missing_indexes"]:
        _execute(connection, INDEXES[index_name])

    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed after schema update")


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
    print("Missing tables:", ", ".join(plan["missing_tables"]) or "none")
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
            for key in ("missing_tables", "missing_indexes")
        )
        backup_path = _create_backup(database_path) if args.apply and has_changes else None

        if args.apply and plan["prerequisite_missing"]:
            _print_plan(database_path, plan, args.apply, backup_path)
            raise SystemExit(1)

        if args.apply and has_changes:
            ensure_mounting_schemes_schema(connection)

        _print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
