"""Add the first additive Material Catalog v2 taxonomy tables.

This migration is additive only:
- dry-run by default
- backup before apply
- no existing material rows are rewritten
- seed categories are idempotent
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path


TABLES = {
    "material_categories": """
        CREATE TABLE IF NOT EXISTS material_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            owner_user_id TEXT,
            parent_id INTEGER,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            is_system BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_user_id) REFERENCES users (id),
            FOREIGN KEY(parent_id) REFERENCES material_categories (id) ON DELETE SET NULL,
            UNIQUE(code),
            CHECK (trim(code) <> ''),
            CHECK (trim(name) <> '')
        )
    """,
    "material_manufacturers": """
        CREATE TABLE IF NOT EXISTS material_manufacturers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            code TEXT,
            website_url TEXT,
            logo_url TEXT,
            owner_user_id TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            is_system BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_user_id) REFERENCES users (id),
            UNIQUE(normalized_name),
            UNIQUE(code),
            CHECK (trim(name) <> ''),
            CHECK (trim(normalized_name) <> '')
        )
    """,
    "material_manufacturer_aliases": """
        CREATE TABLE IF NOT EXISTS material_manufacturer_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manufacturer_id INTEGER NOT NULL,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            source TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(manufacturer_id) REFERENCES material_manufacturers (id) ON DELETE CASCADE,
            UNIQUE(normalized_alias),
            CHECK (trim(alias) <> ''),
            CHECK (trim(normalized_alias) <> '')
        )
    """,
    "material_supplier_offers": """
        CREATE TABLE IF NOT EXISTS material_supplier_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            article TEXT,
            external_product_id TEXT,
            source_url TEXT,
            price REAL,
            currency TEXT DEFAULT 'UAH',
            unit TEXT DEFAULT 'шт',
            stock TEXT,
            city TEXT,
            region TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 0,
            parsed_at DATETIME,
            price_updated_at DATETIME,
            source_payload_json TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(material_id) REFERENCES materials (id) ON DELETE CASCADE,
            FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE CASCADE
        )
    """,
}

INDEXES = {
    "ix_material_categories_parent_id": (
        "CREATE INDEX IF NOT EXISTS ix_material_categories_parent_id "
        "ON material_categories (parent_id)"
    ),
    "ix_material_categories_owner_user_id": (
        "CREATE INDEX IF NOT EXISTS ix_material_categories_owner_user_id "
        "ON material_categories (owner_user_id)"
    ),
    "ix_material_categories_is_active": (
        "CREATE INDEX IF NOT EXISTS ix_material_categories_is_active "
        "ON material_categories (is_active)"
    ),
    "ix_material_categories_is_system": (
        "CREATE INDEX IF NOT EXISTS ix_material_categories_is_system "
        "ON material_categories (is_system)"
    ),
    "ix_material_manufacturers_is_active": (
        "CREATE INDEX IF NOT EXISTS ix_material_manufacturers_is_active "
        "ON material_manufacturers (is_active)"
    ),
    "ix_material_manufacturers_is_system": (
        "CREATE INDEX IF NOT EXISTS ix_material_manufacturers_is_system "
        "ON material_manufacturers (is_system)"
    ),
    "ix_material_manufacturers_owner_user_id": (
        "CREATE INDEX IF NOT EXISTS ix_material_manufacturers_owner_user_id "
        "ON material_manufacturers (owner_user_id)"
    ),
    "ix_material_manufacturer_aliases_manufacturer_id": (
        "CREATE INDEX IF NOT EXISTS ix_material_manufacturer_aliases_manufacturer_id "
        "ON material_manufacturer_aliases (manufacturer_id)"
    ),
    "ix_material_supplier_offers_material_id": (
        "CREATE INDEX IF NOT EXISTS ix_material_supplier_offers_material_id "
        "ON material_supplier_offers (material_id)"
    ),
    "ix_material_supplier_offers_supplier_id": (
        "CREATE INDEX IF NOT EXISTS ix_material_supplier_offers_supplier_id "
        "ON material_supplier_offers (supplier_id)"
    ),
    "ix_material_supplier_offers_priority": (
        "CREATE INDEX IF NOT EXISTS ix_material_supplier_offers_priority "
        "ON material_supplier_offers (priority)"
    ),
}

CATEGORY_SEED_ROWS = [
    ("dsp", "ДСП", 0),
    ("mdf", "МДФ", 1),
    ("hdf", "ДВП / HDF", 2),
    ("plywood", "Фанера", 3),
    ("countertop", "Стільниці", 4),
    ("compact_board", "Компакт-плита", 5),
    ("facade_material", "Фасадні матеріали", 6),
]

CATEGORY_SEED_DESCRIPTIONS = {
    "dsp": {
        "description": "Ламіновані деревинно-стружкові плити для корпусних меблів і деталей.",
        "image_url": None,
    },
    "mdf": {
        "description": "Щільні деревоволокнисті плити для фасадів, панелей і точних деталей.",
        "image_url": None,
    },
    "hdf": {
        "description": "Тонкі тверді плити для задніх стінок, дна та технічних елементів.",
        "image_url": None,
    },
    "plywood": {
        "description": "Шаровий матеріал для конструктивних і декоративних меблевих деталей.",
        "image_url": None,
    },
    "countertop": {
        "description": "Стільниці для кухонь, робочих зон і стійких до навантаження поверхонь.",
        "image_url": None,
    },
    "compact_board": {
        "description": "Щільний вологостійкий матеріал для інтенсивної експлуатації.",
        "image_url": None,
    },
    "facade_material": {
        "description": "Матеріали для фасадів і лицьових меблевих поверхонь.",
        "image_url": None,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add Material Catalog v2 taxonomy tables.",
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


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    rows = _driver_execute(connection, f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def _missing_columns(connection, table_name: str, expected_columns: dict[str, str]) -> list[tuple[str, str]]:
    if not _table_exists(connection, table_name):
        return []

    return [
        (column_name, column_type)
        for column_name, column_type in expected_columns.items()
        if not _column_exists(connection, table_name, column_name)
    ]


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


def _normalize_identity_text(value: str | None) -> str | None:
    normalized = " ".join(str(value or "").split()).strip()
    if not normalized:
        return None

    normalized = unicodedata.normalize("NFKC", normalized).casefold()
    normalized = re.sub(r"[^0-9\w]+", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _build_material_manufacturer_candidates(connection) -> dict[int, set[str]]:
    if not _table_exists(connection, "material_manufacturers"):
        return {}

    candidates: dict[int, set[str]] = {}
    for row in _driver_execute(
        connection,
        "SELECT id, name, normalized_name, code FROM material_manufacturers",
    ).fetchall():
        manufacturer_id = int(row[0])
        candidate_set = candidates.setdefault(manufacturer_id, set())
        for value in (row[1], row[2], row[3]):
            normalized = _normalize_identity_text(value)
            if normalized:
                candidate_set.add(normalized)

    if _table_exists(connection, "material_manufacturer_aliases"):
        for row in _driver_execute(
            connection,
            "SELECT manufacturer_id, alias, normalized_alias FROM material_manufacturer_aliases",
        ).fetchall():
            manufacturer_id = int(row[0])
            candidate_set = candidates.setdefault(manufacturer_id, set())
            for value in (row[1], row[2]):
                normalized = _normalize_identity_text(value)
                if normalized:
                    candidate_set.add(normalized)

    return candidates


def _resolve_material_manufacturer_id(
    material_text: str,
    candidates_by_manufacturer: dict[int, set[str]],
) -> int | None:
    normalized_material_text = _normalize_identity_text(material_text)
    if not normalized_material_text:
        return None

    padded_text = f" {normalized_material_text} "
    matched_ids = {
        manufacturer_id
        for manufacturer_id, candidates in candidates_by_manufacturer.items()
        if any(f" {candidate} " in padded_text for candidate in candidates)
    }

    if len(matched_ids) == 1:
        return next(iter(matched_ids))

    return None


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _build_plan(connection) -> dict[str, object]:
    return {
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
        "missing_columns": {
            "material_categories": _missing_columns(
                    connection,
                    "material_categories",
                    {
                        "description": "TEXT",
                        "image_url": "TEXT",
                        "owner_user_id": "TEXT",
                    },
                ),
            "material_manufacturers": _missing_columns(
                    connection,
                    "material_manufacturers",
                    {
                        "owner_user_id": "TEXT",
                    },
                ),
            "materials": _missing_columns(
                    connection,
                    "materials",
                    {
                        "manufacturer_id": "INTEGER",
                    },
                ),
            "material_supplier_offers": _missing_columns(
                    connection,
                    "material_supplier_offers",
                    {
                        "material_id": "INTEGER",
                        "supplier_id": "INTEGER",
                        "article": "TEXT",
                        "external_product_id": "TEXT",
                        "source_url": "TEXT",
                        "price": "REAL",
                        "currency": "TEXT",
                        "unit": "TEXT",
                        "stock": "TEXT",
                        "city": "TEXT",
                        "region": "TEXT",
                        "is_active": "BOOLEAN NOT NULL DEFAULT 1",
                        "priority": "INTEGER NOT NULL DEFAULT 0",
                        "parsed_at": "DATETIME",
                        "price_updated_at": "DATETIME",
                        "source_payload_json": "TEXT",
                        "created_at": "DATETIME",
                        "updated_at": "DATETIME",
                    },
                ),
            },
        "seed_rows": [
            row
            for row in CATEGORY_SEED_ROWS
            if not _table_exists(connection, "material_categories")
            or not _category_seed_exists(connection, row[0])
        ],
        "existing_category_count": _count_rows(connection, "material_categories"),
        "existing_manufacturer_count": _count_rows(connection, "material_manufacturers"),
        "materials_count": _count_rows(connection, "materials"),
    }


def _count_rows(connection, table_name: str) -> int:
    if not _table_exists(connection, table_name):
        return 0
    row = _driver_execute(connection, f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(row[0]) if row else 0


def _category_seed_exists(connection, code: str) -> bool:
    if not _table_exists(connection, "material_categories"):
        return False
    row = _driver_execute(
        connection,
        "SELECT 1 FROM material_categories WHERE code = ?",
        (code,),
    ).fetchone()
    return row is not None


def _apply_plan(connection, plan: dict[str, object], *, caller_owns_transaction: bool = True) -> None:
    use_explicit_transaction = caller_owns_transaction and not hasattr(connection, "exec_driver_sql")

    _driver_execute(connection, "PRAGMA foreign_keys = ON")
    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed before Material Catalog v2 update")

    if use_explicit_transaction:
        _driver_execute(connection, "BEGIN")
    try:
        for table_name, statement in TABLES.items():
            if table_name in plan["missing_tables"]:
                _driver_execute(connection, statement)

        for table_name, columns in plan.get("missing_columns", {}).items():
            for column_name, column_type in columns:
                _driver_execute(
                    connection,
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}",
                )

        if _column_exists(connection, "materials", "manufacturer_id"):
            manufacturer_candidates = _build_material_manufacturer_candidates(connection)
            if manufacturer_candidates:
                material_rows = _driver_execute(
                    connection,
                    "SELECT id, name, article FROM materials WHERE manufacturer_id IS NULL",
                ).fetchall()
                for row in material_rows:
                    material_id = int(row[0])
                    material_text = " ".join(
                        value
                        for value in (
                            str(row[1] or "").strip(),
                            str(row[2] or "").strip(),
                        )
                        if value
                    ).strip()
                    manufacturer_id = _resolve_material_manufacturer_id(
                        material_text,
                        manufacturer_candidates,
                    )
                    if manufacturer_id is not None:
                        _driver_execute(
                            connection,
                            "UPDATE materials SET manufacturer_id = ? WHERE id = ?",
                            (manufacturer_id, material_id),
                        )

        for index_name in plan["missing_indexes"]:
            _driver_execute(connection, INDEXES[index_name])

        if _table_exists(connection, "material_categories"):
            for code, name, sort_order in CATEGORY_SEED_ROWS:
                _driver_execute(
                    connection,
                    """
                    INSERT INTO material_categories (
                        code,
                        name,
                        description,
                        image_url,
                        parent_id,
                        sort_order,
                        is_active,
                        is_system
                    )
                    VALUES (?, ?, ?, ?, NULL, ?, 1, 1)
                    ON CONFLICT(code) DO UPDATE SET
                        name = excluded.name,
                        description = CASE
                            WHEN material_categories.description IS NULL OR trim(material_categories.description) = ''
                            THEN excluded.description
                            ELSE material_categories.description
                        END,
                        image_url = CASE
                            WHEN material_categories.image_url IS NULL OR trim(material_categories.image_url) = ''
                            THEN excluded.image_url
                            ELSE material_categories.image_url
                        END,
                        parent_id = excluded.parent_id,
                        sort_order = excluded.sort_order,
                        is_active = excluded.is_active,
                        is_system = excluded.is_system,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        code,
                        name,
                        CATEGORY_SEED_DESCRIPTIONS.get(code, {}).get("description"),
                        CATEGORY_SEED_DESCRIPTIONS.get(code, {}).get("image_url"),
                        sort_order,
                    ),
                )
    except Exception:
        if use_explicit_transaction:
            connection.rollback()
        raise
    else:
        if use_explicit_transaction:
            connection.commit()

    if _integrity_check(connection) != "ok":
        raise SystemExit("Integrity check failed after Material Catalog v2 update")


def ensure_material_catalog_v2_schema(connection) -> None:
    plan = _build_plan(connection)
    if (
        plan["missing_tables"]
        or plan["missing_indexes"]
        or plan["seed_rows"]
        or any(plan.get("missing_columns", {}).values())
    ):
        _apply_plan(connection, plan, caller_owns_transaction=False)


def _print_plan(database_path: Path, plan: dict[str, object], apply: bool, backup_path: Path | None) -> None:
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    print("Missing tables:", ", ".join(plan["missing_tables"]) or "none")
    print("Missing indexes:", ", ".join(plan["missing_indexes"]) or "none")
    missing_columns = [
        f"{table_name}.{column_name}"
        for table_name, columns in plan.get("missing_columns", {}).items()
        for column_name, _ in columns
    ]
    print("Missing columns:", ", ".join(missing_columns) or "none")
    print("Seed rows:", len(plan["seed_rows"]))
    print("Materials rows:", plan["materials_count"])
    print("Categories:", plan["existing_category_count"])
    print("Manufacturers:", plan["existing_manufacturer_count"])


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()

    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        plan = _build_plan(connection)
        has_changes = bool(
            plan["missing_tables"]
            or plan["missing_indexes"]
            or plan["seed_rows"]
            or any(plan.get("missing_columns", {}).values())
        )
        backup_path = _create_backup(database_path) if args.apply and has_changes else None
        if args.apply and has_changes:
            _apply_plan(connection, plan, caller_owns_transaction=False)
        _print_plan(database_path, plan, args.apply, backup_path)


if __name__ == "__main__":
    main()
