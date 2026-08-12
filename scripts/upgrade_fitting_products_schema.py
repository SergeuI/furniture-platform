"""Add canonical fitting products and technical product links.

This script is additive only:
- dry-run by default
- backup before apply
- no existing fitting rows are deleted
- ambiguous fitting groups remain unlinked
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


PREREQUISITE_TABLES = ("fittings",)

FITTING_PRODUCTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS fitting_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article VARCHAR,
        code VARCHAR,
        name VARCHAR NOT NULL,
        brand VARCHAR,
        description TEXT,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK (trim(name) <> '')
    )
"""

FITTINGS_TECHNICAL_PRODUCT_COLUMN_SQL = """
    ALTER TABLE fittings ADD COLUMN technical_product_id INTEGER
"""

INDEXES = {
    "uq_fitting_products_article": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fitting_products_article "
        "ON fitting_products (article) "
        "WHERE article IS NOT NULL AND trim(article) <> ''"
    ),
    "ix_fitting_products_code": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_products_code "
        "ON fitting_products (code)"
    ),
    "ix_fitting_products_article": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_products_article "
        "ON fitting_products (article)"
    ),
    "ix_fitting_products_brand": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_products_brand "
        "ON fitting_products (brand)"
    ),
    "ix_fitting_products_is_active": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_products_is_active "
        "ON fitting_products (is_active)"
    ),
    "ix_fittings_technical_product_id": (
        "CREATE INDEX IF NOT EXISTS ix_fittings_technical_product_id "
        "ON fittings (technical_product_id)"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add canonical fitting products and technical product links.",
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


def _integrity_check(connection: sqlite3.Connection) -> str:
    row = _driver_execute(connection, "PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else "unknown"


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _normalize_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_fitting_rows(connection: sqlite3.Connection) -> list[dict[str, object]]:
    has_technical_product_id = _column_exists(connection, "fittings", "technical_product_id")
    if has_technical_product_id:
        rows = _driver_execute(
            connection,
            """
            SELECT
                id,
                article,
                code,
                name,
                brand,
                description,
                is_active,
                technical_product_id
            FROM fittings
            ORDER BY article, id
            """,
        ).fetchall()
    else:
        rows = _driver_execute(
            connection,
            """
            SELECT
                id,
                article,
                code,
                name,
                brand,
                description,
                is_active
            FROM fittings
            ORDER BY article, id
            """,
        ).fetchall()
    fitting_rows: list[dict[str, object]] = []
    for row in rows:
        fitting_rows.append(
            {
                "id": int(row[0]),
                "article": _normalize_text(row[1]),
                "code": _normalize_text(row[2]),
                "name": _normalize_text(row[3]),
                "brand": _normalize_text(row[4]),
                "description": _normalize_text(row[5]),
                "is_active": 1 if row[6] in (None, 1, True) else 0,
                "technical_product_id": row[7] if has_technical_product_id else None,
            }
        )
    return fitting_rows


def _load_existing_product_rows(connection: sqlite3.Connection) -> dict[str, dict[str, object]]:
    if not _table_exists(connection, "fitting_products"):
        return {}

    rows = _driver_execute(
        connection,
        """
        SELECT id, article, code, name, brand, description, is_active
        FROM fitting_products
        WHERE article IS NOT NULL AND trim(article) <> ''
        ORDER BY id
        """,
    ).fetchall()
    existing: dict[str, dict[str, object]] = {}
    for row in rows:
        article = _normalize_text(row[1])
        if article and article not in existing:
            existing[article] = {
                "id": int(row[0]),
                "article": article,
                "code": _normalize_text(row[2]),
                "name": _normalize_text(row[3]),
                "brand": _normalize_text(row[4]),
                "description": _normalize_text(row[5]),
                "is_active": 1 if row[6] in (None, 1, True) else 0,
            }
    return existing


def _nonblank_unique_values(rows: list[dict[str, object]], field_name: str) -> list[str]:
    values = {
        value
        for value in (
            _normalize_text(row[field_name])
            for row in rows
        )
        if value is not None
    }
    return sorted(values)


def _first_nonblank(rows: list[dict[str, object]], field_name: str) -> str | None:
    for row in rows:
        value = _normalize_text(row[field_name])
        if value is not None:
            return value
    return None


def _build_product_groups(
    connection: sqlite3.Connection,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[int, dict[str, object]]]:
    fitting_rows = _load_fitting_rows(connection)
    fitting_rows_by_id = {int(row["id"]): row for row in fitting_rows}
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in fitting_rows:
        article = row["article"]
        if not article:
            continue
        grouped.setdefault(article, []).append(row)

    existing_products = _load_existing_product_rows(connection)
    canonical_groups: list[dict[str, object]] = []
    ambiguous_groups: list[dict[str, object]] = []

    for article, rows in sorted(
        grouped.items(),
        key=lambda item: (item[0], min(int(row["id"]) for row in item[1])),
    ):
        name_values = _nonblank_unique_values(rows, "name")
        code_values = _nonblank_unique_values(rows, "code")
        brand_values = _nonblank_unique_values(rows, "brand")

        is_ambiguous = (
            not name_values
            or len(name_values) > 1
            or len(code_values) > 1
            or len(brand_values) > 1
        )
        if is_ambiguous:
            ambiguous_groups.append(
                {
                    "article": article,
                    "fitting_ids": [int(row["id"]) for row in rows],
                    "name_values": name_values,
                    "code_values": code_values,
                    "brand_values": brand_values,
                }
            )
            continue

        canonical_groups.append(
            {
                "article": article,
                "fitting_ids": [int(row["id"]) for row in rows],
                "product": {
                    "article": article,
                    "code": _first_nonblank(rows, "code"),
                    "name": _first_nonblank(rows, "name"),
                    "brand": _first_nonblank(rows, "brand"),
                    "description": _first_nonblank(rows, "description"),
                    "is_active": 1 if any(int(row["is_active"]) for row in rows) else 0,
                },
                "existing_product": existing_products.get(article),
            }
        )

    return canonical_groups, ambiguous_groups, fitting_rows_by_id


def _build_plan(connection: sqlite3.Connection) -> dict[str, object]:
    if not _table_exists(connection, "fittings"):
        return {
            "prerequisite_missing": True,
            "missing_prerequisites": ["fittings"],
            "missing_tables": [],
            "missing_columns": [],
            "missing_indexes": [],
            "canonical_groups": [],
            "ambiguous_groups": [],
            "products_to_upsert": [],
            "fitting_link_updates": [],
            "ambiguous_nullifications": [],
        }

    canonical_groups, ambiguous_groups, fitting_rows_by_id = _build_product_groups(connection)
    products_to_upsert: list[dict[str, object]] = []
    fitting_link_updates: list[dict[str, object]] = []
    ambiguous_nullifications: list[int] = []

    for group in canonical_groups:
        desired_product = group["product"]
        existing_product = group["existing_product"]
        if existing_product is None:
            products_to_upsert.append(group)
        else:
            current_values = {
                key: existing_product[key]
                for key in ("article", "code", "name", "brand", "description", "is_active")
            }
            desired_values = {
                key: desired_product[key]
                for key in ("article", "code", "name", "brand", "description", "is_active")
            }
            if current_values != desired_values:
                products_to_upsert.append(group)

        expected_product_id = None if existing_product is None else int(existing_product["id"])
        for fitting_id in group["fitting_ids"]:
            row = fitting_rows_by_id[fitting_id]
            if expected_product_id is None or row["technical_product_id"] != expected_product_id:
                fitting_link_updates.append(
                    {
                        "fitting_id": fitting_id,
                        "article": group["article"],
                    }
                )

    for group in ambiguous_groups:
        for fitting_id in group["fitting_ids"]:
            row = fitting_rows_by_id[fitting_id]
            if row["technical_product_id"] is not None:
                ambiguous_nullifications.append(fitting_id)

    missing_columns = [
        "technical_product_id"
        for column_name in ("technical_product_id",)
        if not _column_exists(connection, "fittings", column_name)
    ]

    return {
        "prerequisite_missing": False,
        "missing_prerequisites": [],
        "missing_tables": [
            table_name
            for table_name in ("fitting_products",)
            if not _table_exists(connection, table_name)
        ],
        "missing_columns": missing_columns,
        "missing_indexes": [
            index_name
            for index_name in INDEXES
            if not _index_exists(connection, index_name)
        ],
        "canonical_groups": canonical_groups,
        "ambiguous_groups": ambiguous_groups,
        "products_to_upsert": products_to_upsert,
        "fitting_link_updates": fitting_link_updates,
        "ambiguous_nullifications": ambiguous_nullifications,
    }


def _ensure_product_row(
    connection: sqlite3.Connection,
    product: dict[str, object],
) -> int:
    article = product["article"]
    existing_product = _load_existing_product_rows(connection).get(str(article))
    if existing_product is not None:
        existing_id = int(existing_product["id"])
        _driver_execute(
            connection,
            """
            UPDATE fitting_products
            SET code = ?,
                name = ?,
                brand = ?,
                description = ?,
                is_active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                product["code"],
                product["name"],
                product["brand"],
                product["description"],
                int(product["is_active"]),
                existing_id,
            ),
        )
        return existing_id

    _driver_execute(
        connection,
        """
        INSERT INTO fitting_products (article, code, name, brand, description, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            product["article"],
            product["code"],
            product["name"],
            product["brand"],
            product["description"],
            int(product["is_active"]),
        ),
    )
    row = _driver_execute(
        connection,
        """
        SELECT id
        FROM fitting_products
        WHERE article = ?
        ORDER BY id
        LIMIT 1
        """,
        (article,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Unable to resolve fitting_products id for article {article!r}")
    return int(row[0])


def _apply_plan(
    connection: sqlite3.Connection,
    plan: dict[str, object],
    caller_owns_transaction: bool = False,
) -> None:
    if plan["prerequisite_missing"]:
        raise SystemExit("Table fittings does not exist. Run the base schema first.")

    _driver_execute(connection, "PRAGMA foreign_keys = ON")
    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed before schema update")
    if not caller_owns_transaction and not _connection_in_transaction(connection):
        _driver_execute(connection, "BEGIN")
    try:
        for table_name in plan["missing_tables"]:
            if table_name == "fitting_products":
                _driver_execute(connection, FITTING_PRODUCTS_TABLE_SQL)

        if "technical_product_id" in plan["missing_columns"]:
            _driver_execute(connection, FITTINGS_TECHNICAL_PRODUCT_COLUMN_SQL)

        for group in plan["products_to_upsert"]:
            _ensure_product_row(connection, group["product"])

        product_ids = {
            article: int(product_row["id"])
            for article, product_row in _load_existing_product_rows(connection).items()
        }

        fitting_updates = []
        for update in plan["fitting_link_updates"]:
            fitting_updates.append(
                (
                    product_ids[update["article"]],
                    update["fitting_id"],
                )
            )

        if fitting_updates:
            _driver_executemany(
                connection,
                """
                UPDATE fittings
                SET technical_product_id = ?
                WHERE id = ?
                """,
                fitting_updates,
            )

        if plan["ambiguous_nullifications"]:
            _driver_executemany(
                connection,
                """
                UPDATE fittings
                SET technical_product_id = NULL
                WHERE id = ?
                """,
                [
                    (fitting_id,)
                    for fitting_id in plan["ambiguous_nullifications"]
                ],
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

    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed after schema update")


def ensure_fitting_products_schema(connection: sqlite3.Connection) -> None:
    caller_owns_transaction = _connection_in_transaction(connection)
    try:
        plan = _build_plan(connection)
        if plan["prerequisite_missing"]:
            missing = ", ".join(plan["missing_prerequisites"]) or "unknown"
            raise SystemExit(f"Missing prerequisite tables: {missing}")

        has_changes = any(
            plan[key]
            for key in ("missing_tables", "missing_columns", "missing_indexes")
        ) or bool(plan["products_to_upsert"]) or bool(plan["fitting_link_updates"]) or bool(plan["ambiguous_nullifications"])

        if has_changes:
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
    print("Canonical product groups:", len(plan["canonical_groups"]))
    print("Ambiguous groups:", len(plan["ambiguous_groups"]))
    print("Products to upsert:", len(plan["products_to_upsert"]))
    print("Fitting links to update:", len(plan["fitting_link_updates"]))
    print("Ambiguous nullifications:", len(plan["ambiguous_nullifications"]))
    for group in plan["canonical_groups"]:
        print(
            "product mapping:",
            f"article={group['product']['article']}",
            f"existing_product_id={None if group['existing_product'] is None else group['existing_product']['id']}",
            f"fitting_ids={group['fitting_ids']}",
        )
    for group in plan["ambiguous_groups"]:
        print(
            "ambiguous group:",
            f"article={group['article']}",
            f"fitting_ids={group['fitting_ids']}",
        )


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
                    )
                )
                or bool(plan["products_to_upsert"])
                or bool(plan["fitting_link_updates"])
                or bool(plan["ambiguous_nullifications"])
            )
        )
        backup_path = _create_backup(database_path) if args.apply and has_changes else None

        if args.apply and plan["prerequisite_missing"]:
            _print_plan(database_path, plan, args.apply, backup_path)
            raise SystemExit(1)

        if args.apply and has_changes:
            _apply_plan(connection, plan, False)

        _print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
