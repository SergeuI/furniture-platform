from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

from scripts import upgrade_fitting_taxonomy_schema as migration


class UpgradeFittingTaxonomySchemaTests(unittest.TestCase):
    def test_dry_run_reports_taxonomy_plan_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = migration._build_plan(connection)

            self.assertFalse(plan["prerequisite_missing"])
            self.assertEqual(set(plan["missing_tables"]), {
                "fitting_manufacturers",
                "fitting_series",
                "fitting_categories",
            })
            self.assertEqual(set(plan["missing_columns"]), {
                "manufacturer_id",
                "series_id",
                "category_id",
            })
            self.assertGreaterEqual(len(plan["manufacturer_seed_rows"]), 4)
            self.assertEqual(len(plan["series_seed_rows"]), 0)
            self.assertGreaterEqual(len(plan["category_seed_rows"]), 15)
            self.assertEqual(len(plan["manufacturer_updates"]), 4)
            self.assertEqual(len(plan["category_updates"]), 5)
            self.assertEqual(len(plan["category_conflicts"]), 0)
            self.assertEqual(plan["products_without_series"], 6)
            self.assertEqual(plan["products_without_manufacturer"], 2)
            self.assertEqual(plan["products_without_category"], 1)

    def test_apply_creates_taxonomy_schema_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                before_counts = self._collect_counts(connection)
                plan = migration._build_plan(connection)
                migration._apply_plan(connection, plan, caller_owns_transaction=False)
                after_counts = self._collect_counts(connection)
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                second_plan = migration._build_plan(connection)
                migration._apply_plan(connection, second_plan, caller_owns_transaction=False)
                third_plan = migration._build_plan(connection)

                self.assertTrue(self._table_exists(connection, "fitting_manufacturers"))
                self.assertTrue(self._table_exists(connection, "fitting_series"))
                self.assertTrue(self._table_exists(connection, "fitting_categories"))
                self.assertTrue(self._column_exists(connection, "fitting_products", "manufacturer_id"))
                self.assertTrue(self._column_exists(connection, "fitting_products", "series_id"))
                self.assertTrue(self._column_exists(connection, "fitting_products", "category_id"))

                self.assertEqual(before_counts["fittings"], after_counts["fittings"])
                self.assertEqual(before_counts["fitting_products"], after_counts["fitting_products"])
                self.assertEqual(before_counts["mounting_node_items"], after_counts["mounting_node_items"])
                self.assertEqual(before_counts["fitting_hole_templates"], after_counts["fitting_hole_templates"])

                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM fitting_manufacturers").fetchone()[0],
                    4,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM fitting_series").fetchone()[0],
                    0,
                )
                self.assertGreaterEqual(
                    connection.execute("SELECT COUNT(*) FROM fitting_categories").fetchone()[0],
                    15,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM fitting_products WHERE manufacturer_id IS NOT NULL",
                    ).fetchone()[0],
                    4,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM fitting_products WHERE series_id IS NOT NULL",
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM fitting_products WHERE category_id IS NOT NULL",
                    ).fetchone()[0],
                    5,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM fittings WHERE technical_product_id IS NOT NULL",
                    ).fetchone()[0],
                    before_counts["legacy_links"],
                )
                self.assertEqual(second_plan["missing_tables"], [])
                self.assertEqual(second_plan["missing_columns"], [])
                self.assertEqual(second_plan["missing_indexes"], [])
                self.assertEqual(second_plan["manufacturer_seed_rows"], [])
                self.assertEqual(second_plan["series_seed_rows"], [])
                self.assertEqual(second_plan["category_seed_rows"], [])
                self.assertEqual(second_plan["manufacturer_updates"], [])
                self.assertEqual(second_plan["series_updates"], [])
                self.assertEqual(second_plan["category_updates"], [])
                self.assertEqual(third_plan["manufacturer_seed_rows"], [])
                self.assertEqual(third_plan["category_seed_rows"], [])

    def test_apply_preserves_existing_manufacturer_logo_url(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE fitting_manufacturers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL,
                        description TEXT,
                        website_url TEXT,
                        logo_url TEXT,
                        country_code TEXT,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """,
                )
                connection.execute(
                    """
                    INSERT INTO fitting_manufacturers (
                        code, name, description, website_url, logo_url, country_code, is_active, sort_order
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "hettich",
                        "Hettich",
                        None,
                        None,
                        "https://example.test/hettich-logo.png",
                        None,
                        1,
                        1,
                    ),
                )
                plan = migration._build_plan(connection)
                self.assertFalse(
                    any(row["code"] == "hettich" for row in plan["manufacturer_seed_rows"]),
                )
                migration._apply_plan(connection, plan, caller_owns_transaction=False)
                logo_url = connection.execute(
                    "SELECT logo_url FROM fitting_manufacturers WHERE code = ?",
                    ("hettich",),
                ).fetchone()[0]
                self.assertEqual(logo_url, "https://example.test/hettich-logo.png")

    def test_caller_owned_transaction_keeps_outer_connection_open(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)
            engine = create_engine(f"sqlite:///{database_path.as_posix()}")

            with engine.begin() as connection:
                plan = migration._build_plan(connection)
                migration.ensure_fitting_taxonomy_schema(connection)
                self.assertTrue(connection.in_transaction())
                self.assertIsNotNone(connection.exec_driver_sql("SELECT 1").fetchone())
                self.assertFalse(plan["prerequisite_missing"])

            with engine.connect() as connection:
                self.assertEqual(
                    connection.execute(text("PRAGMA integrity_check")).fetchone()[0],
                    "ok",
                )
                self.assertEqual(
                    connection.execute(text("SELECT COUNT(*) FROM fitting_products")).fetchone()[0],
                    6,
                )

    @staticmethod
    def _create_legacy_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE fitting_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT,
                    code TEXT,
                    name TEXT NOT NULL,
                    brand TEXT,
                    description TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    technical_product_id INTEGER,
                    fitting_type TEXT,
                    fitting_group TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE keep_me (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO fitting_products (article, code, name, brand, description, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("131761", "A1", "Опора", "Muller", "desc", 1),
                    ("190072", "A2", "Саморізи", "Китай", "desc", 1),
                    ("190106", "A3", "Конфірмат", None, "desc", 1),
                    ("190209", "A4", "Шкант", "Smart", "desc", 1),
                    ("46834", "A5", "Гачок", "Ferro Fiori", "desc", 1),
                    ("57722", "A6", "Дюбель", "Hettich", "desc", 1),
                ],
            )
            connection.executemany(
                """
                INSERT INTO fittings (technical_product_id, fitting_type, fitting_group)
                VALUES (?, ?, ?)
                """,
                [
                    (1, "connectors_fasteners", "fasteners"),
                    (2, None, None),
                    (3, "connectors_fasteners", "fasteners"),
                    (4, "handles_hooks", "fittings"),
                    (5, "legs_wheels", "fittings"),
                    (6, "hinges", "fittings"),
                ],
            )
            connection.execute(
                "INSERT INTO keep_me (name) VALUES (?)",
                ("stable",),
            )
            connection.commit()

    @staticmethod
    def _collect_counts(connection: sqlite3.Connection) -> dict[str, int]:
        return {
            "fittings": connection.execute("SELECT COUNT(*) FROM fittings").fetchone()[0],
            "fitting_products": connection.execute("SELECT COUNT(*) FROM fitting_products").fetchone()[0],
            "mounting_node_items": connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'mounting_node_items'").fetchone()[0],
            "fitting_hole_templates": connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'fitting_hole_templates'").fetchone()[0],
            "legacy_links": connection.execute("SELECT COUNT(*) FROM fittings WHERE technical_product_id IS NOT NULL").fetchone()[0],
        }

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return any(str(row[1]) == column_name for row in rows)


if __name__ == "__main__":
    unittest.main()
