from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import upgrade_fittings_foundation_schema as migration


class UpgradeFittingsFoundationSchemaTests(unittest.TestCase):
    def test_dry_run_reports_catalog_key_backfill_and_new_tables_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                before_count = connection.execute(
                    "SELECT COUNT(*) FROM fittings",
                ).fetchone()[0]
                plan = migration._build_plan(connection)
                after_count = connection.execute(
                    "SELECT COUNT(*) FROM fittings",
                ).fetchone()[0]

            self.assertEqual(before_count, after_count)
            self.assertFalse(plan["prerequisite_missing"])
            self.assertEqual(set(plan["missing_tables"]), {
                "suppliers",
                "fitting_supplier_offers",
            })
            self.assertEqual(plan["missing_columns"], ["catalog_key"])
            self.assertIn("uq_fittings_catalog_key", plan["missing_indexes"])
            self.assertTrue(plan["seed_viyar_supplier"])
            self.assertEqual(len(plan["catalog_key_rows"]), 2)

    def test_apply_creates_foundation_schema_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = migration._build_plan(connection)
                migration._apply_plan(connection, plan)

            with sqlite3.connect(database_path) as connection:
                self.assertTrue(self._table_exists(connection, "suppliers"))
                self.assertTrue(self._table_exists(connection, "fitting_supplier_offers"))
                self.assertTrue(self._column_exists(connection, "fittings", "catalog_key"))
                self.assertTrue(self._index_exists(connection, "uq_fittings_catalog_key"))
                self.assertTrue(self._index_exists(connection, "ix_suppliers_code"))
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM fittings").fetchone()[0],
                    2,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM fitting_supplier_offers").fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM suppliers WHERE code = ?",
                        ("viyar",),
                    ).fetchone()[0],
                    1,
                )
                catalog_keys = [
                    row[0]
                    for row in connection.execute(
                        "SELECT catalog_key FROM fittings ORDER BY id",
                    ).fetchall()
                ]
                self.assertTrue(all(catalog_keys))
                self.assertEqual(len(set(catalog_keys)), 2)
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM keep_me").fetchone()[0],
                    1,
                )

                second_plan = migration._build_plan(connection)
                self.assertEqual(second_plan["missing_tables"], [])
                self.assertEqual(second_plan["missing_columns"], [])
                self.assertEqual(second_plan["missing_indexes"], [])
                self.assertEqual(second_plan["catalog_key_rows"], [])
                self.assertFalse(second_plan["seed_viyar_supplier"])
                migration.ensure_fittings_foundation_schema(connection)

            with sqlite3.connect(database_path) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM fittings").fetchone()[0],
                    2,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM fitting_supplier_offers").fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM keep_me").fetchone()[0],
                    1,
                )

    def test_missing_fittings_table_is_reported_without_creating_schema(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE keep_me (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL
                    )
                    """
                )
                connection.commit()

                plan = migration._build_plan(connection)
                self.assertTrue(plan["prerequisite_missing"])
                self.assertIn("fittings", plan["missing_prerequisites"])
                with self.assertRaises(SystemExit):
                    migration.ensure_fittings_foundation_schema(connection)

                self.assertTrue(self._table_exists(connection, "keep_me"))
                self.assertFalse(self._table_exists(connection, "suppliers"))

    @staticmethod
    def _create_legacy_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT,
                    article TEXT,
                    name TEXT,
                    price REAL,
                    source TEXT,
                    is_system INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1
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
                INSERT INTO fittings (code, article, name, price, source, is_system, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("leg_50", "131761", "Опора INTEGRATO D 32мм", 82.56, None, 1, 1),
                    (None, "190106", "Конфірмат (стяжка) оцинков. 7,0х50 мм", 1.14, "viyar", 1, 1),
                ],
            )
            connection.execute(
                "INSERT INTO keep_me (name) VALUES (?)",
                ("stable",),
            )
            connection.commit()

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

    @staticmethod
    def _index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            (index_name,),
        ).fetchone()
        return row is not None


if __name__ == "__main__":
    unittest.main()
