from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import upgrade_mounting_schemes_schema as migration


class UpgradeMountingSchemesSchemaTests(unittest.TestCase):
    def test_dry_run_reports_missing_tables_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                before_rows = connection.execute("SELECT COUNT(*) FROM keep_me").fetchone()[0]
                plan = migration._build_plan(connection)
                after_rows = connection.execute("SELECT COUNT(*) FROM keep_me").fetchone()[0]

            self.assertEqual(before_rows, after_rows)
            self.assertFalse(plan["prerequisite_missing"])
            self.assertEqual(set(plan["missing_tables"]), {
                "mounting_schemes",
                "mounting_scheme_nodes",
                "mounting_scheme_placement_rules",
            })
            self.assertIn("ix_mounting_schemes_name", plan["missing_indexes"])

    def test_apply_creates_tables_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = migration._build_plan(connection)
                migration.ensure_mounting_schemes_schema(connection)

            with sqlite3.connect(database_path) as connection:
                self.assertTrue(self._table_exists(connection, "mounting_schemes"))
                self.assertTrue(self._table_exists(connection, "mounting_scheme_nodes"))
                self.assertTrue(self._table_exists(connection, "mounting_scheme_placement_rules"))
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM keep_me").fetchone()[0],
                    1,
                )
                second_plan = migration._build_plan(connection)
                self.assertEqual(second_plan["missing_tables"], [])
                self.assertEqual(second_plan["missing_indexes"], [])
                migration.ensure_mounting_schemes_schema(connection)

            with sqlite3.connect(database_path) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM keep_me").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM mounting_nodes").fetchone()[0],
                    1,
                )

    def test_missing_prerequisites_are_reported(self) -> None:
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
                self.assertIn("mounting_nodes", plan["missing_prerequisites"])
                with self.assertRaises(SystemExit):
                    migration.ensure_mounting_schemes_schema(connection)

                self.assertTrue(self._table_exists(connection, "keep_me"))
                self.assertFalse(self._table_exists(connection, "mounting_schemes"))

    @staticmethod
    def _create_legacy_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE mounting_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL
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
            connection.execute(
                "INSERT INTO mounting_nodes (code, name) VALUES (?, ?)",
                ("mounting-node-confirmat", "Confirmat"),
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


if __name__ == "__main__":
    unittest.main()
