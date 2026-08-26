"""Add unique identity indexes to material supplier offers.

This migration is additive only:
- dry-run by default
- backup before apply
- no existing rows are rewritten
- duplicate identities block the update with a clear error
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


INDEXES = {
    "uq_material_supplier_offers_identity_external": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_material_supplier_offers_identity_external "
        "ON material_supplier_offers (material_id, supplier_id, external_product_id) "
        "WHERE external_product_id IS NOT NULL"
    ),
    "uq_material_supplier_offers_identity_no_external": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_material_supplier_offers_identity_no_external "
        "ON material_supplier_offers (material_id, supplier_id) "
        "WHERE external_product_id IS NULL"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add unique identity indexes to material supplier offers.",
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


def _driver_execute(connection, statement: str, parameters=None):
    executor = getattr(connection, "exec_driver_sql", None)
    if callable(executor):
        if parameters is None:
            return executor(statement)
        return executor(statement, parameters)

    cursor = connection.cursor()
    if parameters is None:
        return cursor.execute(statement)
    return cursor.execute(statement, parameters)


def _table_exists(connection, table_name: str) -> bool:
    row = _driver_execute(
        connection,
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _index_exists(connection, index_name: str) -> bool:
    row = _driver_execute(
        connection,
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone()
    return row is not None


def _integrity_check(connection) -> str:
    row = _driver_execute(connection, "PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else "unknown"


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _find_duplicates(connection) -> list[dict[str, object]]:
    if not _table_exists(connection, "material_supplier_offers"):
        return []

    duplicates: list[dict[str, object]] = []

    for row in _driver_execute(
        connection,
        """
        SELECT material_id, supplier_id, external_product_id, COUNT(*) AS duplicate_count
        FROM material_supplier_offers
        WHERE external_product_id IS NOT NULL
        GROUP BY material_id, supplier_id, external_product_id
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, material_id, supplier_id, external_product_id
        """,
    ).fetchall():
        duplicates.append(
            {
                "scope": "external_product_id",
                "material_id": int(row[0]),
                "supplier_id": int(row[1]),
                "external_product_id": row[2],
                "duplicate_count": int(row[3]),
            }
        )

    for row in _driver_execute(
        connection,
        """
        SELECT material_id, supplier_id, COUNT(*) AS duplicate_count
        FROM material_supplier_offers
        WHERE external_product_id IS NULL
        GROUP BY material_id, supplier_id
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, material_id, supplier_id
        """,
    ).fetchall():
        duplicates.append(
            {
                "scope": "no_external_product_id",
                "material_id": int(row[0]),
                "supplier_id": int(row[1]),
                "duplicate_count": int(row[2]),
            }
        )

    return duplicates


def _build_plan(connection) -> dict[str, object]:
    return {
        "missing_tables": [] if _table_exists(connection, "material_supplier_offers") else ["material_supplier_offers"],
        "missing_indexes": [
            index_name
            for index_name in INDEXES
            if not _index_exists(connection, index_name)
        ],
        "duplicates": _find_duplicates(connection),
    }


def _apply_plan(connection, plan: dict[str, object], *, caller_owns_transaction: bool = True) -> None:
    use_explicit_transaction = caller_owns_transaction and not hasattr(connection, "exec_driver_sql")

    _driver_execute(connection, "PRAGMA foreign_keys = ON")
    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed before material supplier offers update")

    if plan["duplicates"]:
        details = ", ".join(
            (
                f"{item['scope']} material_id={item['material_id']} supplier_id={item['supplier_id']}"
                + (
                    f" external_product_id={item.get('external_product_id')}"
                    if item.get("external_product_id") is not None
                    else ""
                )
                + f" count={item['duplicate_count']}"
            )
            for item in plan["duplicates"]
        )
        raise SystemExit(
            "Duplicate material_supplier_offers identities found; resolve them before creating unique indexes: "
            + details
        )

    if use_explicit_transaction:
        _driver_execute(connection, "BEGIN")
    try:
        for index_name in plan["missing_indexes"]:
            _driver_execute(connection, INDEXES[index_name])
    except Exception:
        if use_explicit_transaction:
            connection.rollback()
        raise
    else:
        if use_explicit_transaction:
            connection.commit()

    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed after material supplier offers update")


def ensure_material_supplier_offers_schema(connection) -> None:
    plan = _build_plan(connection)
    if plan["missing_indexes"]:
        _apply_plan(connection, plan, caller_owns_transaction=False)


def _print_plan(database_path: Path, plan: dict[str, object], apply: bool, backup_path: Path | None) -> None:
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    print("Missing tables:", ", ".join(plan["missing_tables"]) or "none")
    print("Missing indexes:", ", ".join(plan["missing_indexes"]) or "none")
    if plan["duplicates"]:
        print("Duplicate identities:")
        for item in plan["duplicates"]:
            label = f"material_id={item['material_id']} supplier_id={item['supplier_id']}"
            if item.get("external_product_id") is not None:
                label += f" external_product_id={item['external_product_id']}"
            print(f" - {item['scope']} {label} count={item['duplicate_count']}")
    else:
        print("Duplicate identities: none")


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()

    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        plan = _build_plan(connection)
        has_changes = bool(plan["missing_indexes"] or plan["duplicates"])
        backup_path = _create_backup(database_path) if args.apply and has_changes else None
        if args.apply and has_changes:
            _apply_plan(connection, plan, caller_owns_transaction=False)
        _print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
