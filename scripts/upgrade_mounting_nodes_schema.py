"""Add the mounting nodes schema on top of the existing fitting-holes schema."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


PREREQUISITE_TABLES = (
    "users",
    "fittings",
    "fitting_hole_templates",
)

TABLES = {
    "mounting_nodes": """
        CREATE TABLE IF NOT EXISTS mounting_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(128) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            owner_user_id VARCHAR,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_by_user_id VARCHAR,
            updated_by_user_id VARCHAR,
            is_archived BOOLEAN NOT NULL DEFAULT 0,
            archived_at DATETIME,
            archived_by_user_id VARCHAR,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (trim(code) <> ''),
            CHECK (trim(name) <> ''),
            FOREIGN KEY(owner_user_id) REFERENCES users (id),
            FOREIGN KEY(created_by_user_id) REFERENCES users (id),
            FOREIGN KEY(updated_by_user_id) REFERENCES users (id),
            FOREIGN KEY(archived_by_user_id) REFERENCES users (id)
        )
    """,
    "mounting_node_items": """
        CREATE TABLE IF NOT EXISTS mounting_node_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id INTEGER NOT NULL,
            fitting_id INTEGER NOT NULL,
            role VARCHAR(64),
            quantity INTEGER NOT NULL DEFAULT 1,
            is_required BOOLEAN NOT NULL DEFAULT 1,
            affects_processing BOOLEAN NOT NULL DEFAULT 1,
            order_index INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (quantity > 0),
            FOREIGN KEY(node_id) REFERENCES mounting_nodes (id) ON DELETE CASCADE,
            FOREIGN KEY(fitting_id) REFERENCES fittings (id),
            UNIQUE(node_id, fitting_id)
        )
    """,
    "mounting_node_templates": """
        CREATE TABLE IF NOT EXISTS mounting_node_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id INTEGER NOT NULL,
            template_id INTEGER NOT NULL,
            is_default BOOLEAN NOT NULL DEFAULT 0,
            order_index INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(node_id) REFERENCES mounting_nodes (id) ON DELETE CASCADE,
            FOREIGN KEY(template_id) REFERENCES fitting_hole_templates (id),
            UNIQUE(node_id, template_id),
            UNIQUE(template_id)
        )
    """,
    "mounting_node_versions": """
        CREATE TABLE IF NOT EXISTS mounting_node_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id INTEGER NOT NULL,
            node_code VARCHAR(128) NOT NULL,
            node_name VARCHAR(255) NOT NULL,
            version_number INTEGER NOT NULL,
            event_type VARCHAR(32) NOT NULL DEFAULT 'update',
            snapshot JSON NOT NULL,
            created_by_user_id VARCHAR,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(node_id, version_number),
            FOREIGN KEY(created_by_user_id) REFERENCES users (id)
        )
    """,
}

INDEXES = {
    "ix_mounting_nodes_name": "CREATE INDEX IF NOT EXISTS ix_mounting_nodes_name ON mounting_nodes (name)",
    "ix_mounting_nodes_owner_user_id": "CREATE INDEX IF NOT EXISTS ix_mounting_nodes_owner_user_id ON mounting_nodes (owner_user_id)",
    "ix_mounting_nodes_created_by_user_id": "CREATE INDEX IF NOT EXISTS ix_mounting_nodes_created_by_user_id ON mounting_nodes (created_by_user_id)",
    "ix_mounting_nodes_updated_by_user_id": "CREATE INDEX IF NOT EXISTS ix_mounting_nodes_updated_by_user_id ON mounting_nodes (updated_by_user_id)",
    "ix_mounting_nodes_is_archived": "CREATE INDEX IF NOT EXISTS ix_mounting_nodes_is_archived ON mounting_nodes (is_archived)",
    "ix_mounting_nodes_archived_by_user_id": "CREATE INDEX IF NOT EXISTS ix_mounting_nodes_archived_by_user_id ON mounting_nodes (archived_by_user_id)",
    "ix_mounting_node_versions_node_id": "CREATE INDEX IF NOT EXISTS ix_mounting_node_versions_node_id ON mounting_node_versions (node_id)",
    "ix_mounting_node_versions_version_number": "CREATE INDEX IF NOT EXISTS ix_mounting_node_versions_version_number ON mounting_node_versions (version_number)",
    "ix_mounting_node_items_node_id": "CREATE INDEX IF NOT EXISTS ix_mounting_node_items_node_id ON mounting_node_items (node_id)",
    "ix_mounting_node_items_fitting_id": "CREATE INDEX IF NOT EXISTS ix_mounting_node_items_fitting_id ON mounting_node_items (fitting_id)",
    "ix_mounting_node_items_order_index": "CREATE INDEX IF NOT EXISTS ix_mounting_node_items_order_index ON mounting_node_items (order_index)",
    "ix_mounting_node_templates_node_id": "CREATE INDEX IF NOT EXISTS ix_mounting_node_templates_node_id ON mounting_node_templates (node_id)",
    "ix_mounting_node_templates_template_id": "CREATE INDEX IF NOT EXISTS ix_mounting_node_templates_template_id ON mounting_node_templates (template_id)",
    "ix_mounting_node_templates_order_index": "CREATE INDEX IF NOT EXISTS ix_mounting_node_templates_order_index ON mounting_node_templates (order_index)",
    "ix_mounting_node_templates_is_default": "CREATE INDEX IF NOT EXISTS ix_mounting_node_templates_is_default ON mounting_node_templates (is_default)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add the mounting nodes schema to furniture_platform.db.",
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


def _integrity_check(connection: sqlite3.Connection) -> str:
    row = connection.execute("PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else "unknown"


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


def _apply_plan(connection: sqlite3.Connection, plan: dict[str, object]) -> None:
    if plan["prerequisite_missing"]:
        missing = ", ".join(plan["missing_prerequisites"]) or "unknown"
        raise SystemExit(f"Missing prerequisite tables: {missing}")

    connection.execute("PRAGMA foreign_keys = ON")
    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed before schema update")

    connection.execute("BEGIN")
    try:
        for table_name in plan["missing_tables"]:
            connection.execute(TABLES[table_name])

        for index_name in plan["missing_indexes"]:
            connection.execute(INDEXES[index_name])
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()

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
        if args.apply and has_changes:
            _apply_plan(connection, plan)
        elif args.apply and plan["prerequisite_missing"]:
            _print_plan(database_path, plan, args.apply, backup_path)
            raise SystemExit(1)
        _print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
