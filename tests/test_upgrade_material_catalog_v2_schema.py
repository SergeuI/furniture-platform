from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import upgrade_material_catalog_v2_schema as migration


class UpgradeMaterialCatalogV2SchemaTests(unittest.TestCase):
    def test_apply_creates_taxonomy_tables_and_seeds_categories_idempotently(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                before_material_count = connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
                plan = migration._build_plan(connection)
                self.assertIn("material_categories", plan["missing_tables"])
                self.assertIn("material_manufacturers", plan["missing_tables"])
                self.assertIn("material_manufacturer_aliases", plan["missing_tables"])
                self.assertIn("material_supplier_offers", plan["missing_tables"])
                self.assertEqual(len(plan["seed_rows"]), 7)

                migration._apply_plan(connection, plan, caller_owns_transaction=False)

                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0], before_material_count)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM material_categories").fetchone()[0], 7)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM material_manufacturers").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM material_manufacturer_aliases").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM material_supplier_offers").fetchone()[0], 0)
                self.assertEqual(
                    [row[1] for row in connection.execute("PRAGMA table_info(material_categories)").fetchall()],
                    [
                        "id",
                        "code",
                        "name",
                        "description",
                        "image_url",
                        "owner_user_id",
                        "parent_id",
                        "sort_order",
                        "is_active",
                        "is_system",
                        "created_at",
                        "updated_at",
                    ],
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT description FROM material_categories WHERE code = 'dsp'"
                    ).fetchone()[0],
                    "Ламіновані деревинно-стружкові плити для корпусних меблів і деталей.",
                )
                self.assertEqual(
                    [row[0] for row in connection.execute("SELECT code FROM material_categories ORDER BY sort_order, id").fetchall()],
                    [
                        "dsp",
                        "mdf",
                        "hdf",
                        "plywood",
                        "countertop",
                        "compact_board",
                        "facade_material",
                    ],
                )

                second_plan = migration._build_plan(connection)
                self.assertEqual(second_plan["missing_tables"], [])
                self.assertEqual(second_plan["missing_indexes"], [])
                self.assertEqual(second_plan["seed_rows"], [])
                self.assertEqual(
                    second_plan["missing_columns"],
                    {
                        "material_categories": [],
                        "material_manufacturers": [],
                        "materials": [],
                        "material_supplier_offers": [],
                    },
                )

                connection.execute(
                    "UPDATE material_categories SET description = 'Manual override' WHERE code = 'dsp'"
                )
                connection.commit()

                migration._apply_plan(connection, second_plan, caller_owns_transaction=False)

                self.assertEqual(connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0], before_material_count)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM material_categories").fetchone()[0], 7)
                self.assertEqual(
                    connection.execute(
                        "SELECT description FROM material_categories WHERE code = 'dsp'"
                    ).fetchone()[0],
                    "Manual override",
                )
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_apply_adds_material_supplier_offers_table_additively(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy-with-supplier-offers.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                before_material_count = connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
                plan = migration._build_plan(connection)
                self.assertIn("material_supplier_offers", plan["missing_tables"])

                migration._apply_plan(connection, plan, caller_owns_transaction=False)

                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0], before_material_count)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM material_supplier_offers").fetchone()[0], 0)
                self.assertEqual(
                    [row[1] for row in connection.execute("PRAGMA table_info(material_supplier_offers)").fetchall()],
                    [
                        "id",
                        "material_id",
                        "supplier_id",
                        "article",
                        "external_product_id",
                        "source_url",
                        "price",
                        "currency",
                        "unit",
                        "stock",
                        "city",
                        "region",
                        "is_active",
                        "priority",
                        "parsed_at",
                        "price_updated_at",
                        "source_payload_json",
                        "created_at",
                        "updated_at",
                    ],
                )

                second_plan = migration._build_plan(connection)
                self.assertNotIn("material_supplier_offers", second_plan["missing_tables"])
                self.assertEqual(second_plan["missing_columns"]["material_supplier_offers"], [])

    def test_apply_adds_owner_user_id_to_existing_material_categories_table(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy-with-categories.db"
            self._create_legacy_database_with_categories(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = migration._build_plan(connection)
                self.assertIn(("owner_user_id", "TEXT"), plan["missing_columns"]["material_categories"])

                migration._apply_plan(connection, plan, caller_owns_transaction=False)

                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertIn(
                    "owner_user_id",
                    [row[1] for row in connection.execute("PRAGMA table_info(material_categories)").fetchall()],
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM material_categories").fetchone()[0],
                    7,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM material_categories WHERE owner_user_id IS NOT NULL"
                    ).fetchone()[0],
                    0,
                )

    def test_apply_adds_owner_user_id_to_existing_material_manufacturers_table(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy-with-manufacturers.db"
            self._create_legacy_database_with_manufacturers(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = migration._build_plan(connection)
                self.assertIn(("owner_user_id", "TEXT"), plan["missing_columns"]["material_manufacturers"])

                migration._apply_plan(connection, plan, caller_owns_transaction=False)

                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertIn(
                    "owner_user_id",
                    [row[1] for row in connection.execute("PRAGMA table_info(material_manufacturers)").fetchall()],
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM material_manufacturers").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM material_manufacturers WHERE owner_user_id IS NOT NULL"
                    ).fetchone()[0],
                    0,
                )

    def test_apply_adds_material_manufacturer_id_and_backfills_obvious_matches_only(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy-with-material-manufacturers.db"
            self._create_legacy_database_with_material_manufacturers(database_path)

            with sqlite3.connect(database_path) as connection:
                before_material_count = connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
                plan = migration._build_plan(connection)
                self.assertIn(("manufacturer_id", "INTEGER"), plan["missing_columns"]["materials"])

                migration._apply_plan(connection, plan, caller_owns_transaction=False)

                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0], before_material_count)
                self.assertIn(
                    "manufacturer_id",
                    [row[1] for row in connection.execute("PRAGMA table_info(materials)").fetchall()],
                )

                material_manufacturers = {
                    row[0]: row[1]
                    for row in connection.execute("SELECT id, name FROM material_manufacturers").fetchall()
                }
                material_rows = {
                    row[0]: row[1]
                    for row in connection.execute(
                        "SELECT article, manufacturer_id FROM materials ORDER BY article"
                    ).fetchall()
                }

                self.assertEqual(material_manufacturers[material_rows["M-001"]], "Kronospan")
                self.assertEqual(material_manufacturers[material_rows["M-002"]], "Egger")
                self.assertEqual(material_manufacturers[material_rows["M-003"]], "Swiss Krono")
                self.assertIsNone(material_rows["M-004"])

    @staticmethod
    def _create_legacy_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE users (
                    id TEXT PRIMARY KEY
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT NOT NULL UNIQUE,
                    name TEXT,
                    category TEXT,
                    is_default INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.executemany(
                "INSERT INTO materials (article, name, category, is_default) VALUES (?, ?, ?, ?)",
                [
                    ("M-001", "ДСП 18", "dsp", 1),
                    ("M-002", "МДФ 16", "mdf", 0),
                ],
            )
            connection.commit()

    @staticmethod
    def _create_legacy_database_with_categories(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE users (
                    id TEXT PRIMARY KEY
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT NOT NULL UNIQUE,
                    name TEXT,
                    category TEXT,
                    is_default INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE material_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    image_url TEXT,
                    parent_id INTEGER,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_system BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(code),
                    CHECK (trim(code) <> ''),
                    CHECK (trim(name) <> '')
                )
                """
            )
            connection.commit()

    @staticmethod
    def _create_legacy_database_with_manufacturers(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE users (
                    id TEXT PRIMARY KEY
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE material_manufacturers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    code TEXT,
                    website_url TEXT,
                    logo_url TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_system BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(normalized_name),
                    UNIQUE(code),
                    CHECK (trim(name) <> ''),
                    CHECK (trim(normalized_name) <> '')
                )
                """
            )
            connection.execute(
                """
                INSERT INTO material_manufacturers (name, normalized_name, code, website_url, logo_url, is_active, is_system)
                VALUES ('Kronospan', 'kronospan', 'kronospan', 'https://kronospan.com', NULL, 1, 1)
                """
            )
            connection.commit()

    @staticmethod
    def _create_legacy_database_with_material_manufacturers(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE users (
                    id TEXT PRIMARY KEY
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT NOT NULL UNIQUE,
                    name TEXT,
                    category TEXT,
                    is_default INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE material_manufacturers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    code TEXT,
                    website_url TEXT,
                    logo_url TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_system BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(normalized_name),
                    UNIQUE(code),
                    CHECK (trim(name) <> ''),
                    CHECK (trim(normalized_name) <> '')
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE material_manufacturer_aliases (
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
                """
            )
            connection.executemany(
                "INSERT INTO material_manufacturers (name, normalized_name, code, website_url, logo_url, is_active, is_system) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    ("Kronospan", "kronospan", "kronospan", "https://kronospan.com", None, 1, 1),
                    ("Egger", "egger", "egger", "https://egger.com", None, 1, 1),
                    ("Swiss Krono", "swiss krono", "swiss_krono", "https://swisskrono.com", None, 1, 1),
                ],
            )
            connection.executemany(
                "INSERT INTO material_manufacturer_aliases (manufacturer_id, alias, normalized_alias, source) VALUES (?, ?, ?, ?)",
                [
                    (1, "Kronospan", "kronospan", "seed"),
                    (2, "EGGER", "egger", "seed"),
                    (3, "Swiss Krono", "swiss krono", "seed"),
                ],
            )
            connection.executemany(
                "INSERT INTO materials (article, name, category, is_default) VALUES (?, ?, ?, ?)",
                [
                    ("M-001", "ДСП Kronospan K 086 PW", "dsp", 1),
                    ("M-002", "Egger PerfectSense", "mdf", 0),
                    ("M-003", "Swiss Krono фасадна плита", "facade_material", 1),
                    ("M-004", "Невідомий матеріал", "dsp", 0),
                ],
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
