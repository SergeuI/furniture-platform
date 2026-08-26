"""Add the canonical edge foundation without touching legacy material edge tables.

This migration is additive only:
- dry-run by default
- backup before apply
- no existing edge rows are rewritten
- no legacy material edge tables are dropped or migrated
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


TABLES = {
    "canonical_edges": """
        CREATE TABLE IF NOT EXISTS canonical_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manufacturer_id INTEGER,
            manufacturer_article TEXT,
            name TEXT NOT NULL,
            decor_code TEXT,
            color TEXT,
            material_type TEXT,
            width_mm REAL,
            thickness_mm REAL,
            finish TEXT,
            image_url TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(manufacturer_id) REFERENCES material_manufacturers (id) ON DELETE SET NULL,
            CHECK (trim(name) <> '')
        )
    """,
    "material_edge_relations": """
        CREATE TABLE IF NOT EXISTS material_edge_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            edge_id INTEGER NOT NULL,
            relation_type TEXT NOT NULL DEFAULT 'recommended',
            source_supplier_id INTEGER,
            source_url TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(material_id) REFERENCES materials (id) ON DELETE CASCADE,
            FOREIGN KEY(edge_id) REFERENCES canonical_edges (id) ON DELETE CASCADE,
            FOREIGN KEY(source_supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL,
            CHECK (relation_type IN ('recommended', 'compatible', 'manual'))
        )
    """,
    "edge_supplier_offers": """
        CREATE TABLE IF NOT EXISTS edge_supplier_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            edge_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            article TEXT,
            external_product_id TEXT,
            source_url TEXT,
            unit TEXT,
            stock TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 0,
            parsed_at DATETIME,
            price_updated_at DATETIME,
            source_payload_json TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(edge_id) REFERENCES canonical_edges (id) ON DELETE CASCADE,
            FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE CASCADE
        )
    """,
    "edge_supplier_offer_prices": """
        CREATE TABLE IF NOT EXISTS edge_supplier_offer_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id INTEGER NOT NULL,
            city TEXT NOT NULL,
            price REAL,
            currency TEXT,
            availability TEXT,
            checked_at DATETIME,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(offer_id) REFERENCES edge_supplier_offers (id) ON DELETE CASCADE
        )
    """,
}

INDEXES = {
    "ix_canonical_edges_manufacturer_id": (
        "CREATE INDEX IF NOT EXISTS ix_canonical_edges_manufacturer_id "
        "ON canonical_edges (manufacturer_id)"
    ),
    "ix_canonical_edges_manufacturer_article": (
        "CREATE INDEX IF NOT EXISTS ix_canonical_edges_manufacturer_article "
        "ON canonical_edges (manufacturer_article)"
    ),
    "ix_canonical_edges_name": (
        "CREATE INDEX IF NOT EXISTS ix_canonical_edges_name "
        "ON canonical_edges (name)"
    ),
    "ix_canonical_edges_is_active": (
        "CREATE INDEX IF NOT EXISTS ix_canonical_edges_is_active "
        "ON canonical_edges (is_active)"
    ),
    "ix_material_edge_relations_material_id": (
        "CREATE INDEX IF NOT EXISTS ix_material_edge_relations_material_id "
        "ON material_edge_relations (material_id)"
    ),
    "ix_material_edge_relations_edge_id": (
        "CREATE INDEX IF NOT EXISTS ix_material_edge_relations_edge_id "
        "ON material_edge_relations (edge_id)"
    ),
    "ix_material_edge_relations_relation_type": (
        "CREATE INDEX IF NOT EXISTS ix_material_edge_relations_relation_type "
        "ON material_edge_relations (relation_type)"
    ),
    "ix_material_edge_relations_source_supplier_id": (
        "CREATE INDEX IF NOT EXISTS ix_material_edge_relations_source_supplier_id "
        "ON material_edge_relations (source_supplier_id)"
    ),
    "uq_material_edge_relations_identity_null_supplier": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_material_edge_relations_identity_null_supplier "
        "ON material_edge_relations (material_id, edge_id, relation_type) "
        "WHERE source_supplier_id IS NULL"
    ),
    "uq_material_edge_relations_identity_supplier": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_material_edge_relations_identity_supplier "
        "ON material_edge_relations (material_id, edge_id, relation_type, source_supplier_id) "
        "WHERE source_supplier_id IS NOT NULL"
    ),
    "ix_edge_supplier_offers_edge_id": (
        "CREATE INDEX IF NOT EXISTS ix_edge_supplier_offers_edge_id "
        "ON edge_supplier_offers (edge_id)"
    ),
    "ix_edge_supplier_offers_supplier_id": (
        "CREATE INDEX IF NOT EXISTS ix_edge_supplier_offers_supplier_id "
        "ON edge_supplier_offers (supplier_id)"
    ),
    "ix_edge_supplier_offers_priority": (
        "CREATE INDEX IF NOT EXISTS ix_edge_supplier_offers_priority "
        "ON edge_supplier_offers (priority)"
    ),
    "uq_edge_supplier_offers_identity_external": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_edge_supplier_offers_identity_external "
        "ON edge_supplier_offers (edge_id, supplier_id, external_product_id) "
        "WHERE external_product_id IS NOT NULL"
    ),
    "uq_edge_supplier_offers_identity_no_external": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_edge_supplier_offers_identity_no_external "
        "ON edge_supplier_offers (edge_id, supplier_id) "
        "WHERE external_product_id IS NULL"
    ),
    "ix_edge_supplier_offer_prices_offer_id": (
        "CREATE INDEX IF NOT EXISTS ix_edge_supplier_offer_prices_offer_id "
        "ON edge_supplier_offer_prices (offer_id)"
    ),
    "ix_edge_supplier_offer_prices_city": (
        "CREATE INDEX IF NOT EXISTS ix_edge_supplier_offer_prices_city "
        "ON edge_supplier_offer_prices (city)"
    ),
    "uq_edge_supplier_offer_prices_offer_city": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_edge_supplier_offer_prices_offer_city "
        "ON edge_supplier_offer_prices (offer_id, city)"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add the canonical edge foundation schema.",
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


def _build_plan(connection) -> dict[str, object]:
    missing_prerequisites = [
        table_name
        for table_name in ("materials", "material_manufacturers", "suppliers")
        if not _table_exists(connection, table_name)
    ]
    return {
        "prerequisite_missing": bool(missing_prerequisites),
        "missing_prerequisites": missing_prerequisites,
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
        "obsolete_indexes": [
            index_name
            for index_name in ("uq_material_edge_relations_identity",)
            if _index_exists(connection, index_name)
        ],
    }


def _apply_plan(
    connection,
    plan: dict[str, object],
    *,
    caller_owns_transaction: bool = True,
) -> None:
    if plan["prerequisite_missing"]:
        missing = ", ".join(plan["missing_prerequisites"]) or "unknown"
        raise SystemExit(f"Missing prerequisite tables: {missing}")

    _driver_execute(connection, "PRAGMA foreign_keys = ON")
    if not caller_owns_transaction:
        _driver_execute(connection, "BEGIN")

    try:
        for index_name in plan["obsolete_indexes"]:
            _driver_execute(connection, f"DROP INDEX IF EXISTS {index_name}")

        for table_name, table_sql in TABLES.items():
            if table_name in plan["missing_tables"]:
                _driver_execute(connection, table_sql)

        for index_name in plan["missing_indexes"]:
            _driver_execute(connection, INDEXES[index_name])
    except Exception:
        if not caller_owns_transaction:
            connection.rollback()
        raise
    else:
        if not caller_owns_transaction:
            connection.commit()

    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed after edge foundation update")


def ensure_edge_foundation_schema(connection) -> None:
    plan = _build_plan(connection)
    if plan["prerequisite_missing"]:
        missing = ", ".join(plan["missing_prerequisites"]) or "unknown"
        raise SystemExit(f"Missing prerequisite tables: {missing}")

    if plan["missing_tables"] or plan["missing_indexes"] or plan["obsolete_indexes"]:
        _apply_plan(connection, plan, caller_owns_transaction=False)


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
    print("Obsolete indexes:", ", ".join(plan["obsolete_indexes"]) or "none")


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()

    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        plan = _build_plan(connection)
        has_changes = (not plan["prerequisite_missing"]) and (
            bool(plan["missing_tables"]) or bool(plan["missing_indexes"]) or bool(plan["obsolete_indexes"])
        )
        backup_path = _create_backup(database_path) if args.apply and has_changes else None

        if args.apply and plan["prerequisite_missing"]:
            _print_plan(database_path, plan, args.apply, backup_path)
            raise SystemExit(1)

        if args.apply and has_changes:
            _apply_plan(connection, plan, caller_owns_transaction=False)

        _print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
