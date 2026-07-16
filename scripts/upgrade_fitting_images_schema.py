"""Idempotently create the fitting_images gallery table."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


TABLE_NAME = "fitting_images"

CREATE_TABLE_SQL = """
    CREATE TABLE fitting_images (
        id INTEGER NOT NULL,
        fitting_id INTEGER NOT NULL,
        sort_order INTEGER NOT NULL,
        is_primary BOOLEAN NOT NULL,
        source_url TEXT,
        image_cached_bytes BLOB NOT NULL,
        image_cached_content_type VARCHAR NOT NULL,
        image_sha256 VARCHAR(64) NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT uq_fitting_images_fitting_id_sort_order UNIQUE (fitting_id, sort_order),
        CONSTRAINT uq_fitting_images_fitting_id_image_sha256 UNIQUE (fitting_id, image_sha256),
        FOREIGN KEY(fitting_id) REFERENCES fittings (id) ON DELETE CASCADE
    )
"""

CREATE_INDEX_SQL = """
    CREATE INDEX IF NOT EXISTS ix_fitting_images_fitting_id_sort_order
    ON fitting_images (fitting_id, sort_order)
"""

EXPECTED_COLUMNS = {
    "id": "INTEGER",
    "fitting_id": "INTEGER",
    "sort_order": "INTEGER",
    "is_primary": "BOOLEAN",
    "source_url": "TEXT",
    "image_cached_bytes": "BLOB",
    "image_cached_content_type": "VARCHAR",
    "image_sha256": "VARCHAR(64)",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}

EXPECTED_NOTNULL_COLUMNS = {
    "id",
    "fitting_id",
    "sort_order",
    "is_primary",
    "image_cached_bytes",
    "image_cached_content_type",
    "image_sha256",
    "created_at",
    "updated_at",
}

EXPECTED_DEFAULT_VALUES = {
    "created_at": "CURRENT_TIMESTAMP",
    "updated_at": "CURRENT_TIMESTAMP",
}

EXPECTED_UNIQUE_INDEX_COLUMNS = {
    ("fitting_id", "sort_order"),
    ("fitting_id", "image_sha256"),
}

EXPECTED_FOREIGN_KEYS = {
    ("fitting_id", "fittings", "id", "CASCADE"),
}

EXPECTED_PLAN_COLUMNS = [
    "id INTEGER NOT NULL PRIMARY KEY",
    "fitting_id INTEGER NOT NULL",
    "sort_order INTEGER NOT NULL",
    "is_primary BOOLEAN NOT NULL",
    "source_url TEXT",
    "image_cached_bytes BLOB NOT NULL",
    "image_cached_content_type VARCHAR NOT NULL",
    "image_sha256 VARCHAR(64) NOT NULL",
    "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
]

EXPECTED_PLAN_CONSTRAINTS = [
    "UNIQUE(fitting_id, sort_order)",
    "UNIQUE(fitting_id, image_sha256)",
    "FOREIGN KEY(fitting_id) REFERENCES fittings (id) ON DELETE CASCADE",
]

EXPECTED_PLAN_INDEXES = [
    "ix_fitting_images_fitting_id_sort_order (fitting_id, sort_order)",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extend the SQLite schema with the fitting_images gallery table.",
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


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            (index_name,),
        ).fetchone()
        is not None
    )


def table_columns(connection: sqlite3.Connection, table_name: str) -> list[sqlite3.Row]:
    return connection.execute(f"PRAGMA table_info({table_name})").fetchall()


def foreign_key_rows(connection: sqlite3.Connection, table_name: str) -> list[sqlite3.Row]:
    return connection.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()


def index_rows(connection: sqlite3.Connection, table_name: str) -> list[sqlite3.Row]:
    return connection.execute(f"PRAGMA index_list({table_name})").fetchall()


def index_columns(connection: sqlite3.Connection, index_name: str) -> tuple[str, ...]:
    rows = connection.execute(f"PRAGMA index_info({index_name})").fetchall()
    return tuple(str(row[2]) for row in rows)


def normalize_declared_type(value: str | None) -> str:
    return " ".join(str(value or "").split()).upper()


def normalize_default_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("'") and text.endswith("'") and len(text) >= 2:
        text = text[1:-1]
    return text.upper()


def build_plan(connection: sqlite3.Connection) -> dict[str, object]:
    if not table_exists(connection, "fittings"):
        raise SystemExit("Table 'fittings' does not exist.")

    fitting_images_exists = table_exists(connection, TABLE_NAME)
    missing_tables = [] if fitting_images_exists else [TABLE_NAME]
    missing_indexes = []
    issues: list[str] = []

    if fitting_images_exists:
        columns = {str(row[1]): row for row in table_columns(connection, TABLE_NAME)}
        actual_column_names = set(columns)
        expected_column_names = set(EXPECTED_COLUMNS)
        table_sql_row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (TABLE_NAME,),
        ).fetchone()
        table_sql = str(table_sql_row[0]) if table_sql_row and table_sql_row[0] else ""
        normalized_table_sql = normalize_declared_type(table_sql)

        missing_column_names = sorted(expected_column_names - actual_column_names)
        extra_column_names = sorted(actual_column_names - expected_column_names)
        if missing_column_names:
            issues.append(
                "Missing columns: " + ", ".join(missing_column_names)
            )
        if extra_column_names:
            issues.append(
                "Unexpected columns: " + ", ".join(extra_column_names)
            )

        for column_name, expected_type in EXPECTED_COLUMNS.items():
            row = columns.get(column_name)
            if row is None:
                continue
            actual_type = normalize_declared_type(row[2])
            if actual_type != normalize_declared_type(expected_type):
                issues.append(
                    f"Column {column_name} has type {actual_type or 'none'}, expected {expected_type}"
                )

            expected_notnull = 1 if column_name in EXPECTED_NOTNULL_COLUMNS else 0
            actual_notnull = int(row[3])
            if actual_notnull != expected_notnull:
                issues.append(
                    f"Column {column_name} has NOT NULL={actual_notnull}, expected {expected_notnull}"
                )

            expected_default = EXPECTED_DEFAULT_VALUES.get(column_name)
            actual_default = normalize_default_value(row[4])
            if actual_default != expected_default:
                issues.append(
                    f"Column {column_name} has default {actual_default or 'none'}, expected {expected_default or 'none'}"
                )

        if "AUTOINCREMENT" in normalized_table_sql:
            issues.append("Table SQL must not use AUTOINCREMENT")

        fk_rows = foreign_key_rows(connection, TABLE_NAME)
        actual_fks = {
            (str(row[3]), str(row[2]), str(row[4]), str(row[6]).upper())
            for row in fk_rows
        }
        if EXPECTED_FOREIGN_KEYS - actual_fks:
            issues.append(
                "Foreign key mismatch: expected fitting_id -> fittings.id ON DELETE CASCADE"
            )

        unique_index_columns: set[tuple[str, ...]] = set()
        for row in index_rows(connection, TABLE_NAME):
            index_name = str(row[1])
            is_unique = int(row[2]) == 1
            if not is_unique:
                continue
            unique_index_columns.add(index_columns(connection, index_name))

        for expected_unique in EXPECTED_UNIQUE_INDEX_COLUMNS:
            if expected_unique not in unique_index_columns:
                issues.append(
                    f"Missing unique constraint/index on ({', '.join(expected_unique)})"
                )

        if not index_exists(connection, "ix_fitting_images_fitting_id_sort_order"):
            missing_indexes.append("ix_fitting_images_fitting_id_sort_order")
    else:
        missing_indexes.append("ix_fitting_images_fitting_id_sort_order")

    return {
        "missing_tables": missing_tables,
        "missing_indexes": missing_indexes,
        "issues": issues,
        "table_exists": fitting_images_exists,
    }


def print_plan(database_path: Path, plan: dict[str, object], apply: bool, backup_path: Path | None) -> None:
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    print("fittings table exists: yes")
    print(f"fitting_images table exists: {'yes' if plan['table_exists'] else 'no'}")
    print("Missing tables:", ", ".join(plan["missing_tables"]) or "none")
    print("Missing indexes:", ", ".join(plan["missing_indexes"]) or "none")
    print("Planned columns:")
    for column in EXPECTED_PLAN_COLUMNS:
        print(f"  - {column}")
    print("Planned constraints:")
    for constraint in EXPECTED_PLAN_CONSTRAINTS:
        print(f"  - {constraint}")
    print("Planned indexes:")
    for index in EXPECTED_PLAN_INDEXES:
        print(f"  - {index}")
    if plan["issues"]:
        print("Schema issues:")
        for issue in plan["issues"]:
            print(f"  - {issue}")
        print("Manual intervention required: yes")
    else:
        print("Schema issues: none")
    print(f"Changes needed: {'yes' if plan['missing_tables'] or plan['missing_indexes'] else 'no'}")
    if not apply:
        print("Use --apply to apply this plan.")


def apply_plan(connection: sqlite3.Connection, plan: dict[str, object]) -> None:
    if plan["issues"]:
        raise SystemExit("Existing fitting_images schema is not compatible with the expected layout.")

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")

    if TABLE_NAME in plan["missing_tables"]:
        connection.execute(CREATE_TABLE_SQL)

    if "ix_fitting_images_fitting_id_sort_order" in plan["missing_indexes"]:
        connection.execute(CREATE_INDEX_SQL)

    connection.commit()

    integrity = connection.execute("PRAGMA integrity_check").fetchone()
    if not integrity or str(integrity[0]).lower() != "ok":
        raise SystemExit(f"Integrity check failed: {integrity[0] if integrity else 'unknown'}")


def main() -> int:
    args = parse_args()
    database_path = Path(args.database).resolve()
    ensure_safe_database(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        plan = build_plan(connection)
        needs_changes = bool(plan["missing_tables"] or plan["missing_indexes"])
        if args.apply and plan["issues"]:
            print_plan(database_path, plan, True, None)
            raise SystemExit(1)

        backup_path = create_backup(database_path) if args.apply and needs_changes else None

        if args.apply and needs_changes:
            apply_plan(connection, plan)

        print_plan(database_path, plan, args.apply, backup_path)
        if args.apply and not needs_changes:
            print("Schema already current.")
        elif args.apply:
            print("Schema applied successfully.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
