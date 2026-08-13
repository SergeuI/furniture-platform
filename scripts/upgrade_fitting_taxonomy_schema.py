"""Add normalized fitting taxonomy for canonical fitting_products.

This migration is additive only:
- dry-run by default
- backup before apply
- no existing IDs are changed
- no legacy fitting links are rewritten
- safe manufacturer/category backfill only
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from database.repositories.inventory_repository import (
    FITTING_CATEGORY_DEFINITIONS,
    FITTING_GROUP_LABELS,
)


PREREQUISITE_TABLES = ("fitting_products",)

TABLES = {
    "fitting_manufacturers": """
        CREATE TABLE IF NOT EXISTS fitting_manufacturers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            website_url TEXT,
            logo_url TEXT,
            country_code TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (trim(code) <> ''),
            CHECK (trim(name) <> '')
        )
    """,
    "fitting_series": """
        CREATE TABLE IF NOT EXISTS fitting_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manufacturer_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(manufacturer_id) REFERENCES fitting_manufacturers (id) ON DELETE CASCADE,
            CHECK (trim(code) <> ''),
            CHECK (trim(name) <> '')
        )
    """,
    "fitting_categories": """
        CREATE TABLE IF NOT EXISTS fitting_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(parent_id) REFERENCES fitting_categories (id) ON DELETE SET NULL,
            CHECK (trim(code) <> ''),
            CHECK (trim(name) <> '')
        )
    """,
}

COLUMNS = {
    "manufacturer_id": "INTEGER",
    "series_id": "INTEGER",
    "category_id": "INTEGER",
}

INDEXES = {
    "uq_fitting_manufacturers_code": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fitting_manufacturers_code "
        "ON fitting_manufacturers (code)"
    ),
    "ix_fitting_manufacturers_is_active": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_manufacturers_is_active "
        "ON fitting_manufacturers (is_active)"
    ),
    "uq_fitting_series_manufacturer_code": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fitting_series_manufacturer_code "
        "ON fitting_series (manufacturer_id, code)"
    ),
    "ix_fitting_series_manufacturer_id": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_series_manufacturer_id "
        "ON fitting_series (manufacturer_id)"
    ),
    "ix_fitting_series_is_active": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_series_is_active "
        "ON fitting_series (is_active)"
    ),
    "uq_fitting_categories_code": (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fitting_categories_code "
        "ON fitting_categories (code)"
    ),
    "ix_fitting_categories_parent_id": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_categories_parent_id "
        "ON fitting_categories (parent_id)"
    ),
    "ix_fitting_categories_is_active": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_categories_is_active "
        "ON fitting_categories (is_active)"
    ),
    "ix_fitting_products_manufacturer_id": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_products_manufacturer_id "
        "ON fitting_products (manufacturer_id)"
    ),
    "ix_fitting_products_series_id": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_products_series_id "
        "ON fitting_products (series_id)"
    ),
    "ix_fitting_products_category_id": (
        "CREATE INDEX IF NOT EXISTS ix_fitting_products_category_id "
        "ON fitting_products (category_id)"
    ),
}

MANUFACTURER_EXCLUSIONS = {"китай"}

ROOT_CATEGORIES = [
    {
        "code": code,
        "name": name,
        "description": None,
        "sort_order": index,
    }
    for index, (code, name) in enumerate(sorted(FITTING_GROUP_LABELS.items()))
]

LEAF_CATEGORIES = [
    {
        "code": item["code"],
        "name": item["name"],
        "description": item.get("description"),
        "group_code": item["group"],
        "sort_order": index,
    }
    for index, item in enumerate(FITTING_CATEGORY_DEFINITIONS)
]

CATEGORY_CODE_TO_LEAF = {
    row["code"]: row
    for row in LEAF_CATEGORIES
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add normalized fitting taxonomy for fitting_products.",
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


def _driver_executemany(connection, statement: str, parameter_sets):
    executor = getattr(connection, "exec_driver_sql", None)
    if callable(executor):
        return executor(statement, parameter_sets)

    executemany = getattr(connection, "executemany", None)
    if callable(executemany):
        return executemany(statement, parameter_sets)

    cursor = connection.cursor()
    return cursor.executemany(statement, parameter_sets)


def _connection_in_transaction(connection) -> bool:
    in_transaction = getattr(connection, "in_transaction", None)
    if callable(in_transaction):
        return bool(in_transaction())
    if in_transaction is not None:
        return bool(in_transaction)
    return False


def _table_exists(connection, table_name: str) -> bool:
    row = _driver_execute(
        connection,
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    rows = _driver_execute(connection, f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


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


def _normalize_text(value) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _slugify_code(value: str | None) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        return ""
    slug = []
    previous_was_separator = False
    for char in normalized.casefold():
        if char.isalnum():
            slug.append(char)
            previous_was_separator = False
        elif not previous_was_separator:
            slug.append("_")
            previous_was_separator = True
    result = "".join(slug).strip("_")
    while "__" in result:
        result = result.replace("__", "_")
    return result


def _load_products(connection) -> list[dict[str, object]]:
    has_manufacturer_column = _column_exists(connection, "fitting_products", "manufacturer_id")
    has_series_column = _column_exists(connection, "fitting_products", "series_id")
    has_category_column = _column_exists(connection, "fitting_products", "category_id")

    select_columns = [
        "id",
        "article",
        "code",
        "name",
        "brand",
        "description",
        "is_active",
    ]
    if has_manufacturer_column:
        select_columns.append("manufacturer_id")
    if has_series_column:
        select_columns.append("series_id")
    if has_category_column:
        select_columns.append("category_id")

    rows = _driver_execute(
        connection,
        f"""
        SELECT {", ".join(select_columns)}
        FROM fitting_products
        ORDER BY id
        """,
    ).fetchall()
    products: list[dict[str, object]] = []
    for row in rows:
        offset = 0
        manufacturer_id = None
        series_id = None
        category_id = None
        if has_manufacturer_column:
            manufacturer_id = row[7 + offset]
            offset += 1
        if has_series_column:
            series_id = row[7 + offset]
            offset += 1
        if has_category_column:
            category_id = row[7 + offset]
        products.append(
            {
                "id": int(row[0]),
                "article": _normalize_text(row[1]),
                "code": _normalize_text(row[2]),
                "name": _normalize_text(row[3]),
                "brand": _normalize_text(row[4]),
                "description": _normalize_text(row[5]),
                "is_active": 1 if row[6] in (None, 1, True) else 0,
                "manufacturer_id": manufacturer_id,
                "series_id": series_id,
                "category_id": category_id,
            }
        )
    return products


def _load_legacy_category_rows(connection) -> dict[int, dict[str, object]]:
    if not _table_exists(connection, "fittings"):
        return {}

    rows = _driver_execute(
        connection,
        """
        SELECT technical_product_id, fitting_type, fitting_group
        FROM fittings
        WHERE technical_product_id IS NOT NULL
        ORDER BY technical_product_id, id
        """,
    ).fetchall()

    grouped: dict[int, dict[str, object]] = {}
    for row in rows:
        product_id = int(row[0])
        entry = grouped.setdefault(
            product_id,
            {
                "fitting_types": set(),
                "fitting_groups": set(),
            },
        )
        fitting_type = _normalize_text(row[1])
        fitting_group = _normalize_text(row[2])
        if fitting_type:
            entry["fitting_types"].add(fitting_type)
        if fitting_group:
            entry["fitting_groups"].add(fitting_group)

    return grouped


def _build_manufacturer_seed_rows(products: list[dict[str, object]]) -> list[dict[str, object]]:
    brands = sorted(
        {
            brand
            for brand in (
                _normalize_text(product["brand"])
                for product in products
            )
            if brand and brand.casefold() not in MANUFACTURER_EXCLUSIONS
        },
        key=lambda value: value.casefold(),
    )
    return [
        {
            "code": _slugify_code(brand),
            "name": brand,
            "description": None,
            "website_url": None,
            "logo_url": None,
            "country_code": None,
            "is_active": 1,
            "sort_order": index,
        }
        for index, brand in enumerate(brands)
    ]


def _build_series_seed_rows() -> list[dict[str, object]]:
    return []


def _build_category_seed_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for root in ROOT_CATEGORIES:
        rows.append(
            {
                "code": root["code"],
                "name": root["name"],
                "parent_code": None,
                "description": root["description"],
                "is_active": 1,
                "sort_order": root["sort_order"],
            }
        )
    for leaf in LEAF_CATEGORIES:
        rows.append(
            {
                "code": leaf["code"],
                "name": leaf["name"],
                "parent_code": leaf["group_code"],
                "description": leaf["description"],
                "is_active": 1,
                "sort_order": leaf["sort_order"],
            }
        )
    return rows


def _load_code_id_map(connection, table_name: str) -> dict[str, int]:
    rows = _driver_execute(
        connection,
        f"SELECT id, code FROM {table_name} ORDER BY id",
    ).fetchall()
    return {str(row[1]): int(row[0]) for row in rows}


def _load_existing_rows_by_code(connection, table_name: str) -> dict[str, dict[str, object]]:
    if not _table_exists(connection, table_name):
        return {}

    if table_name == "fitting_manufacturers":
        rows = _driver_execute(
            connection,
            """
            SELECT code, name, description, website_url, logo_url, country_code, is_active, sort_order
            FROM fitting_manufacturers
            """,
        ).fetchall()
        return {
            str(row[0]): {
                "code": str(row[0]),
                "name": row[1],
                "description": row[2],
                "website_url": row[3],
                "logo_url": row[4],
                "country_code": row[5],
                "is_active": 1 if row[6] in (None, 1, True) else 0,
                "sort_order": int(row[7] or 0),
            }
            for row in rows
        }

    if table_name == "fitting_categories":
        rows = _driver_execute(
            connection,
            """
            SELECT code, name, parent_id, description, is_active, sort_order
            FROM fitting_categories
            """,
        ).fetchall()
        return {
            str(row[0]): {
                "code": str(row[0]),
                "name": row[1],
                "parent_id": row[2],
                "description": row[3],
                "is_active": 1 if row[4] in (None, 1, True) else 0,
                "sort_order": int(row[5] or 0),
            }
            for row in rows
        }

    return {}


def _load_product_rows_by_id(connection) -> dict[int, dict[str, object]]:
    products = _load_products(connection)
    return {int(product["id"]): product for product in products}


def _build_plan(connection) -> dict[str, object]:
    if any(not _table_exists(connection, table_name) for table_name in PREREQUISITE_TABLES):
        return {
            "prerequisite_missing": True,
            "missing_prerequisites": [table_name for table_name in PREREQUISITE_TABLES if not _table_exists(connection, table_name)],
            "missing_tables": [],
            "missing_columns": [],
            "missing_indexes": [],
            "manufacturer_seed_rows": [],
            "series_seed_rows": [],
            "category_seed_rows": [],
            "manufacturer_updates": [],
            "series_updates": [],
            "category_updates": [],
            "category_conflicts": [],
            "products_without_series": 0,
            "products_without_manufacturer": 0,
            "products_without_category": 0,
            "products_total": 0,
        }

    products = _load_products(connection)
    legacy_category_rows = _load_legacy_category_rows(connection)
    has_manufacturer_column = _column_exists(connection, "fitting_products", "manufacturer_id")
    has_series_column = _column_exists(connection, "fitting_products", "series_id")
    has_category_column = _column_exists(connection, "fitting_products", "category_id")
    product_rows_by_id = _load_product_rows_by_id(connection)
    existing_manufacturer_code_to_id = (
        _load_code_id_map(connection, "fitting_manufacturers")
        if _table_exists(connection, "fitting_manufacturers")
        else {}
    )
    existing_category_code_to_id = (
        _load_code_id_map(connection, "fitting_categories")
        if _table_exists(connection, "fitting_categories")
        else {}
    )

    manufacturer_seed_rows = _build_manufacturer_seed_rows(products)
    series_seed_rows = _build_series_seed_rows()
    category_seed_rows = _build_category_seed_rows()
    existing_manufacturer_rows = _load_existing_rows_by_code(connection, "fitting_manufacturers")
    existing_category_rows = _load_existing_rows_by_code(connection, "fitting_categories")

    manufacturer_seed_rows = [
        row
        for row in manufacturer_seed_rows
        if existing_manufacturer_rows.get(row["code"]) != row
    ]

    category_code_to_row = {
        row["code"]: row
        for row in category_seed_rows
    }
    category_seed_rows = [
        row
        for row in category_seed_rows
        if existing_category_rows.get(row["code"]) != {
            "code": row["code"],
            "name": row["name"],
            "parent_id": (
                existing_category_code_to_id.get(str(row["parent_code"]))
                if row.get("parent_code")
                else None
            ),
            "description": row["description"],
            "is_active": row["is_active"],
            "sort_order": row["sort_order"],
        }
    ]

    manufacturer_updates: list[dict[str, object]] = []
    series_updates: list[dict[str, object]] = []
    category_updates: list[dict[str, object]] = []
    category_conflicts: list[dict[str, object]] = []
    category_mapped_product_ids: set[int] = set()

    for product in products:
        product_id = int(product["id"])
        brand = _normalize_text(product["brand"])
        desired_manufacturer_code = None
        if brand and brand.casefold() not in MANUFACTURER_EXCLUSIONS:
            desired_manufacturer_code = _slugify_code(brand)
        current_manufacturer_id = product_rows_by_id[product_id].get("manufacturer_id") if has_manufacturer_column else None
        if desired_manufacturer_code:
            desired_manufacturer_id = existing_manufacturer_code_to_id.get(desired_manufacturer_code)
            if not has_manufacturer_column or current_manufacturer_id != desired_manufacturer_id:
                manufacturer_updates.append(
                    {
                        "product_id": product_id,
                        "article": product["article"],
                        "brand": brand,
                        "manufacturer_code": desired_manufacturer_code,
                        "manufacturer_name": brand,
                        "current_manufacturer_id": current_manufacturer_id,
                        "desired_manufacturer_id": desired_manufacturer_id,
                    }
                )
        elif has_manufacturer_column and current_manufacturer_id is not None:
            manufacturer_updates.append(
                {
                    "product_id": product_id,
                    "article": product["article"],
                    "brand": brand,
                    "manufacturer_code": None,
                    "manufacturer_name": None,
                    "current_manufacturer_id": current_manufacturer_id,
                }
            )

        legacy_row = legacy_category_rows.get(product_id, {"fitting_types": set(), "fitting_groups": set()})
        fitting_types = sorted(str(value) for value in legacy_row["fitting_types"])
        fitting_groups = sorted(str(value) for value in legacy_row["fitting_groups"])
        desired_category_code = None
        if len(fitting_types) == 1:
            candidate = fitting_types[0]
            if candidate in category_code_to_row:
                desired_category_code = candidate
                category_mapped_product_ids.add(product_id)
            else:
                category_conflicts.append(
                    {
                        "product_id": product_id,
                        "article": product["article"],
                        "brand": brand,
                        "fitting_types": fitting_types,
                        "fitting_groups": fitting_groups,
                        "reason": "unknown_fitting_type",
                    }
                )
        elif len(fitting_types) > 1:
            category_conflicts.append(
                {
                    "product_id": product_id,
                    "article": product["article"],
                    "brand": brand,
                    "fitting_types": fitting_types,
                    "fitting_groups": fitting_groups,
                    "reason": "multiple_fitting_types",
                }
            )

        current_category_id = product_rows_by_id[product_id].get("category_id") if has_category_column else None
        if desired_category_code:
            desired_category_id = existing_category_code_to_id.get(desired_category_code)
            if not has_category_column or current_category_id != desired_category_id:
                category_updates.append(
                    {
                        "product_id": product_id,
                        "article": product["article"],
                        "category_code": desired_category_code,
                        "current_category_id": current_category_id,
                        "desired_category_id": desired_category_id,
                        "fitting_types": fitting_types,
                        "fitting_groups": fitting_groups,
                    }
                )
        elif has_category_column and current_category_id is not None:
            category_updates.append(
                {
                    "product_id": product_id,
                    "article": product["article"],
                    "category_code": None,
                    "current_category_id": current_category_id,
                    "fitting_types": fitting_types,
                    "fitting_groups": fitting_groups,
                }
            )

    missing_tables = [
        table_name
        for table_name in TABLES
        if not _table_exists(connection, table_name)
    ]
    missing_columns = [
        column_name
        for column_name in COLUMNS
        if not _column_exists(connection, "fitting_products", column_name)
    ]
    missing_indexes = [
        index_name
        for index_name in INDEXES
        if not _index_exists(connection, index_name)
    ]

    products_without_manufacturer = sum(
        1
        for product in products
        if not _normalize_text(product["brand"])
        or _normalize_text(product["brand"]).casefold() in MANUFACTURER_EXCLUSIONS
    )
    products_without_category = sum(
        1
        for product in products
        if int(product["id"]) not in category_mapped_product_ids
    )

    return {
        "prerequisite_missing": False,
        "missing_prerequisites": [],
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "missing_indexes": missing_indexes,
        "manufacturer_seed_rows": manufacturer_seed_rows,
        "series_seed_rows": series_seed_rows,
        "category_seed_rows": category_seed_rows,
        "manufacturer_updates": manufacturer_updates,
        "series_updates": series_updates,
        "category_updates": category_updates,
        "category_conflicts": category_conflicts,
        "products_without_series": len(products),
        "products_without_manufacturer": products_without_manufacturer,
        "products_without_category": products_without_category,
        "products_total": len(products),
    }


def _upsert_code_row(
    connection,
    table_name: str,
    row: dict[str, object],
) -> None:
    columns = [
        "code",
        "name",
        "description",
        "is_active",
        "sort_order",
        "created_at",
        "updated_at",
    ]
    values = [
        row.get("code"),
        row.get("name"),
        row.get("description"),
        int(row.get("is_active", 1)),
        int(row.get("sort_order", 0)),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ]

    if table_name == "fitting_manufacturers":
        columns.extend(["website_url", "logo_url", "country_code"])
        values.extend([row.get("website_url"), row.get("logo_url"), row.get("country_code")])

    if table_name == "fitting_categories":
        columns.append("parent_id")
        values.append(row.get("parent_id"))

    columns_sql = ", ".join(columns)
    placeholders = ", ".join(["?"] * len(columns))
    updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in columns
        if column not in {"code", "created_at"}
    )

    _driver_execute(
        connection,
        f"""
        INSERT INTO {table_name} ({columns_sql})
        VALUES ({placeholders})
        ON CONFLICT(code) DO UPDATE SET
            {updates}
        """,
        tuple(values),
    )


def _seed_tables(connection, plan: dict[str, object]) -> None:
    for table_name, ddl in TABLES.items():
        if table_name in plan["missing_tables"]:
            _driver_execute(connection, ddl)

    for column_name, column_type in COLUMNS.items():
        if column_name in plan["missing_columns"]:
            _driver_execute(
                connection,
                f"ALTER TABLE fitting_products ADD COLUMN {column_name} {column_type}",
            )

    for index_name in plan["missing_indexes"]:
        _driver_execute(connection, INDEXES[index_name])

    for row in plan["manufacturer_seed_rows"]:
        _upsert_code_row(connection, "fitting_manufacturers", row)

    manufacturer_code_to_id = _load_code_id_map(connection, "fitting_manufacturers")
    category_code_to_id = _load_code_id_map(connection, "fitting_categories")

    for row in plan["category_seed_rows"]:
        parent_id = None
        parent_code = row.get("parent_code")
        if parent_code:
            parent_id = category_code_to_id.get(str(parent_code))
        _upsert_code_row(
            connection,
            "fitting_categories",
            {
                **row,
                "parent_id": parent_id,
            },
        )
        category_code_to_id = _load_code_id_map(connection, "fitting_categories")

    for row in plan["series_seed_rows"]:
        manufacturer_code = _normalize_text(row.get("manufacturer_code"))
        manufacturer_id = manufacturer_code_to_id.get(manufacturer_code or "")
        if manufacturer_id is None:
            continue
        _driver_execute(
            connection,
            """
            INSERT INTO fitting_series (
                manufacturer_id, code, name, description, is_active, sort_order, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(manufacturer_id, code) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                is_active = excluded.is_active,
                sort_order = excluded.sort_order,
                updated_at = excluded.updated_at
            """,
            (
                int(manufacturer_id),
                row.get("code"),
                row.get("name"),
                row.get("description"),
                int(row.get("is_active", 1)),
                int(row.get("sort_order", 0)),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    manufacturer_code_to_id = _load_code_id_map(connection, "fitting_manufacturers")
    category_code_to_id = _load_code_id_map(connection, "fitting_categories")
    series_code_to_id: dict[tuple[int, str], int] = {}
    series_rows = _driver_execute(
        connection,
        "SELECT id, manufacturer_id, code FROM fitting_series ORDER BY id",
    ).fetchall()
    for row in series_rows:
        series_code_to_id[(int(row[1]), str(row[2]))] = int(row[0])

    for update in plan["manufacturer_updates"]:
        manufacturer_code = update["manufacturer_code"]
        desired_manufacturer_id = manufacturer_code_to_id.get(manufacturer_code or "") if manufacturer_code else None
        current_manufacturer_id = update.get("current_manufacturer_id")
        if desired_manufacturer_id == current_manufacturer_id:
            continue
        _driver_execute(
            connection,
            """
            UPDATE fitting_products
            SET manufacturer_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                desired_manufacturer_id,
                int(update["product_id"]),
            ),
        )

    for update in plan["series_updates"]:
        manufacturer_code = update["manufacturer_code"]
        series_code = update["series_code"]
        manufacturer_id = manufacturer_code_to_id.get(manufacturer_code or "") if manufacturer_code else None
        desired_series_id = None
        if manufacturer_id is not None and series_code:
            desired_series_id = series_code_to_id.get((int(manufacturer_id), series_code))
        if desired_series_id == update.get("current_series_id"):
            continue
        _driver_execute(
            connection,
            """
            UPDATE fitting_products
            SET series_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                desired_series_id,
                int(update["product_id"]),
            ),
        )

    for update in plan["category_updates"]:
        category_code = update["category_code"]
        desired_category_id = category_code_to_id.get(category_code or "") if category_code else None
        if desired_category_id == update.get("current_category_id"):
            continue
        _driver_execute(
            connection,
            """
            UPDATE fitting_products
            SET category_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                desired_category_id,
                int(update["product_id"]),
            ),
        )


def _apply_plan(connection, plan: dict[str, object], caller_owns_transaction: bool = False) -> None:
    if plan["prerequisite_missing"]:
        missing = ", ".join(plan["missing_prerequisites"]) or "unknown"
        raise SystemExit(f"Missing prerequisite tables: {missing}")

    _driver_execute(connection, "PRAGMA foreign_keys = ON")
    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed before schema update")

    owns_transaction = caller_owns_transaction or _connection_in_transaction(connection)
    if not owns_transaction:
        _driver_execute(connection, "BEGIN")

    try:
        _seed_tables(connection, plan)
    except Exception:
        if not owns_transaction and _connection_in_transaction(connection):
            _driver_execute(connection, "ROLLBACK")
        raise
    else:
        if not owns_transaction and _connection_in_transaction(connection):
            _driver_execute(connection, "COMMIT")

    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed after schema update")


def ensure_fitting_taxonomy_schema(connection) -> None:
    plan = _build_plan(connection)
    _apply_plan(
        connection,
        plan,
        caller_owns_transaction=_connection_in_transaction(connection),
    )


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
    print("Manufacturer seed rows:", len(plan["manufacturer_seed_rows"]))
    print("Series seed rows:", len(plan["series_seed_rows"]))
    print("Category seed rows:", len(plan["category_seed_rows"]))
    print("Manufacturer updates:", len(plan["manufacturer_updates"]))
    print("Series updates:", len(plan["series_updates"]))
    print("Category updates:", len(plan["category_updates"]))
    print("Category conflicts:", len(plan["category_conflicts"]))
    print("Products without manufacturer:", plan["products_without_manufacturer"])
    print("Products without series:", plan["products_without_series"])
    print("Products without category:", plan["products_without_category"])


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()

    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        plan = _build_plan(connection)
        has_changes = not plan["prerequisite_missing"] and any(
            plan[key]
            for key in (
                "missing_tables",
                "missing_columns",
                "missing_indexes",
                "manufacturer_seed_rows",
                "series_seed_rows",
                "category_seed_rows",
                "manufacturer_updates",
                "series_updates",
                "category_updates",
            )
        )
        backup_path = _create_backup(database_path) if args.apply and has_changes else None

        if args.apply and plan["prerequisite_missing"]:
            _print_plan(database_path, plan, args.apply, backup_path)
            raise SystemExit(1)

        if args.apply and has_changes:
            _apply_plan(connection, plan, caller_owns_transaction=False)
            plan = _build_plan(connection)

        _print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
