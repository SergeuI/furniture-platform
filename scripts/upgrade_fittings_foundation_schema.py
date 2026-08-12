"""Add the canonical fittings foundation without moving legacy offer fields.

This script is additive only:
- dry-run by default
- backup before apply
- no existing fitting rows are deleted
- no offer data is migrated out of fittings yet
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


FITTINGS_CATALOG_KEY_COLUMN_SQL = """
    ALTER TABLE fittings ADD COLUMN catalog_key VARCHAR
"""

SUPPLIERS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code VARCHAR NOT NULL UNIQUE,
        name VARCHAR NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK (trim(code) <> ''),
        CHECK (trim(name) <> '')
    )
"""

FITTING_SUPPLIER_OFFERS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS fitting_supplier_offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fitting_id INTEGER NOT NULL,
        supplier_id INTEGER NOT NULL,
        article VARCHAR,
        external_product_id VARCHAR,
        source_url VARCHAR,
        price NUMERIC,
        currency VARCHAR DEFAULT 'UAH',
        unit VARCHAR DEFAULT 'шт',
        stock VARCHAR,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        priority INTEGER NOT NULL DEFAULT 0,
        parsed_at DATETIME,
        price_updated_at DATETIME,
        source_payload_json TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(fitting_id) REFERENCES fittings (id),
        FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
    )
"""

INDEXES = {
    "uq_fittings_catalog_key": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fittings_catalog_key "
        "ON fittings (catalog_key)"
    ),
    "ix_suppliers_code": (
        "CREATE INDEX IF NOT EXISTS ix_suppliers_code "
        "ON suppliers (code)"
    ),
    "ix_fitting_supplier_offers_fitting_id": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_supplier_offers_fitting_id "
        "ON fitting_supplier_offers (fitting_id)"
    ),
    "ix_fitting_supplier_offers_supplier_id": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_supplier_offers_supplier_id "
        "ON fitting_supplier_offers (supplier_id)"
    ),
    "ix_fitting_supplier_offers_priority": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_supplier_offers_priority "
        "ON fitting_supplier_offers (priority)"
    ),
    "uq_fitting_supplier_offers_identity_external": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fitting_supplier_offers_identity_external "
        "ON fitting_supplier_offers (fitting_id, supplier_id, external_product_id) "
        "WHERE external_product_id IS NOT NULL"
    ),
    "uq_fitting_supplier_offers_identity_no_external": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fitting_supplier_offers_identity_no_external "
        "ON fitting_supplier_offers (fitting_id, supplier_id) "
        "WHERE external_product_id IS NULL"
    ),
}

VIYAR_SUPPLIER_CODE = "viyar"
VIYAR_SUPPLIER_NAME = "VIYAR"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add the canonical fittings foundation schema.",
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


def _driver_execute(connection: sqlite3.Connection, statement: str, parameters=None):
    executor = getattr(connection, "exec_driver_sql", None)
    if callable(executor):
        if parameters is None:
            return executor(statement)
        return executor(statement, parameters)

    cursor = connection.cursor()
    if parameters is None:
        return cursor.execute(statement)
    return cursor.execute(statement, parameters)


def _driver_executemany(connection: sqlite3.Connection, statement: str, parameter_sets):
    executor = getattr(connection, "exec_driver_sql", None)
    if callable(executor):
        return executor(statement, parameter_sets)

    executemany = getattr(connection, "executemany", None)
    if callable(executemany):
        return executemany(statement, parameter_sets)

    cursor = connection.cursor()
    return cursor.executemany(statement, parameter_sets)


def _connection_in_transaction(connection: sqlite3.Connection) -> bool:
    in_transaction = getattr(connection, "in_transaction", None)
    if callable(in_transaction):
        return bool(in_transaction())
    if in_transaction is not None:
        return bool(in_transaction)
    return False


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = _driver_execute(
        connection,
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = _driver_execute(connection, f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def _index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
    row = _driver_execute(
        connection,
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone()
    return row is not None


def _build_catalog_key_rows(
    connection: sqlite3.Connection,
    has_catalog_key_column: bool,
) -> list[dict[str, object]]:
    if has_catalog_key_column:
        rows = _driver_execute(
            connection,
            """
            SELECT id, code, name
            FROM fittings
            WHERE catalog_key IS NULL OR trim(catalog_key) = ''
            ORDER BY id
            """
        ).fetchall()
    else:
        rows = _driver_execute(
            connection,
            """
            SELECT id, code, name
            FROM fittings
            ORDER BY id
            """
        ).fetchall()
    return [
        {
            "fitting_id": int(row[0]),
            "old_code": row[1],
            "name": row[2],
            "new_catalog_key": str(uuid.uuid4()),
        }
        for row in rows
    ]


def _build_plan(connection: sqlite3.Connection) -> dict[str, object]:
    if not _table_exists(connection, "fittings"):
        return {
            "prerequisite_missing": True,
            "missing_prerequisites": ["fittings"],
            "missing_tables": [],
            "missing_columns": [],
            "missing_indexes": [],
            "catalog_key_rows": [],
            "seed_viyar_supplier": False,
        }

    has_catalog_key_column = _column_exists(connection, "fittings", "catalog_key")
    catalog_key_rows = _build_catalog_key_rows(connection, has_catalog_key_column)
    supplier_table_exists = _table_exists(connection, "suppliers")

    return {
        "prerequisite_missing": False,
        "missing_prerequisites": [],
        "missing_tables": [
            table_name
            for table_name in ("suppliers", "fitting_supplier_offers")
            if not _table_exists(connection, table_name)
        ],
        "missing_columns": [
            "catalog_key"
            for column_name in ("catalog_key",)
            if not has_catalog_key_column
        ],
        "missing_indexes": [
            index_name
            for index_name in INDEXES
            if not _index_exists(connection, index_name)
        ],
        "catalog_key_rows": catalog_key_rows,
        "seed_viyar_supplier": (
            not supplier_table_exists
            or not _supplier_exists(connection, VIYAR_SUPPLIER_CODE)
        ),
    }


def _supplier_exists(connection: sqlite3.Connection, code: str) -> bool:
    row = _driver_execute(
        connection,
        "SELECT 1 FROM suppliers WHERE code = ?",
        (code,),
    ).fetchone()
    return row is not None


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _apply_plan(
    connection: sqlite3.Connection,
    plan: dict[str, object],
    caller_owns_transaction: bool = False,
) -> None:
    if plan["prerequisite_missing"]:
        raise SystemExit("Table fittings does not exist. Run the base schema first.")

    _driver_execute(connection, "PRAGMA foreign_keys = ON")
    if not caller_owns_transaction and not _connection_in_transaction(connection):
        _driver_execute(connection, "BEGIN")
    try:
        for table_name in plan["missing_tables"]:
            if table_name == "suppliers":
                _driver_execute(connection, SUPPLIERS_TABLE_SQL)
            elif table_name == "fitting_supplier_offers":
                _driver_execute(connection, FITTING_SUPPLIER_OFFERS_TABLE_SQL)

        if "catalog_key" in plan["missing_columns"]:
            _driver_execute(connection, FITTINGS_CATALOG_KEY_COLUMN_SQL)

        if plan["catalog_key_rows"]:
            _driver_executemany(
                connection,
                """
                UPDATE fittings
                SET catalog_key = ?
                WHERE id = ?
                """,
                [
                    (row["new_catalog_key"], row["fitting_id"])
                    for row in plan["catalog_key_rows"]
                ],
            )

        if plan["seed_viyar_supplier"]:
            if not _table_exists(connection, "suppliers"):
                raise SystemExit("Suppliers table was not created as expected.")
            if not _supplier_exists(connection, VIYAR_SUPPLIER_CODE):
                _driver_execute(
                    connection,
                    """
                    INSERT INTO suppliers (code, name, is_active)
                    VALUES (?, ?, 1)
                    """,
                    (VIYAR_SUPPLIER_CODE, VIYAR_SUPPLIER_NAME),
                )

        for index_name in plan["missing_indexes"]:
            _driver_execute(connection, INDEXES[index_name])
    except Exception:
        if not caller_owns_transaction:
            connection.rollback()
        raise
    else:
        if not caller_owns_transaction:
            connection.commit()


def ensure_fittings_foundation_schema(connection: sqlite3.Connection) -> None:
    caller_owns_transaction = _connection_in_transaction(connection)
    try:
        plan = _build_plan(connection)
        if plan["prerequisite_missing"]:
            missing = ", ".join(plan["missing_prerequisites"]) or "unknown"
            raise SystemExit(f"Missing prerequisite tables: {missing}")

        if any(
            plan[key]
            for key in ("missing_tables", "missing_columns", "missing_indexes", "catalog_key_rows")
        ) or plan["seed_viyar_supplier"]:
            _apply_plan(connection, plan, caller_owns_transaction)
        elif not caller_owns_transaction:
            connection.commit()
    except BaseException:
        if not caller_owns_transaction and _connection_in_transaction(connection):
            connection.rollback()
        raise


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
    print("Missing columns:", ", ".join(plan["missing_columns"]) or "none")
    print("Missing indexes:", ", ".join(plan["missing_indexes"]) or "none")
    print("Backfill catalog_key rows:", len(plan["catalog_key_rows"]))
    for row in plan["catalog_key_rows"]:
        print(
            "catalog_key mapping:",
            f"fitting_id={row['fitting_id']}",
            f"name={row['name']}",
            f"old_code={row['old_code']}",
            f"new_catalog_key={row['new_catalog_key']}",
        )
    print("Seed VIYAR supplier:", "yes" if plan["seed_viyar_supplier"] else "no")


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()

    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        plan = _build_plan(connection)
        has_changes = (
            not plan["prerequisite_missing"]
            and (
                any(
                    plan[key]
                    for key in (
                        "missing_tables",
                        "missing_columns",
                        "missing_indexes",
                        "catalog_key_rows",
                    )
                )
                or bool(plan["seed_viyar_supplier"])
            )
        )
        backup_path = _create_backup(database_path) if args.apply and has_changes else None

        if args.apply and plan["prerequisite_missing"]:
            _print_plan(database_path, plan, args.apply, backup_path)
            raise SystemExit(1)

        if args.apply and has_changes:
            _apply_plan(connection, plan)

        _print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
