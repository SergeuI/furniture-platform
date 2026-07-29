from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import upgrade_mounting_nodes_schema as migration


class UpgradeMountingNodesSchemaTests(unittest.TestCase):
    def test_dry_run_reports_missing_tables_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                before_rows = connection.execute(
                    "SELECT COUNT(*) FROM keep_me",
                ).fetchone()[0]
                plan = migration._build_plan(connection)
                after_rows = connection.execute(
                    "SELECT COUNT(*) FROM keep_me",
                ).fetchone()[0]

            self.assertEqual(before_rows, after_rows)
            self.assertFalse(plan["prerequisite_missing"])
            self.assertEqual(set(plan["missing_tables"]), {
                "mounting_nodes",
                "mounting_node_items",
                "mounting_node_templates",
            })
            self.assertIn("ix_mounting_nodes_name", plan["missing_indexes"])

    def test_apply_creates_tables_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = migration._build_plan(connection)
                migration._apply_plan(connection, plan)

            with sqlite3.connect(database_path) as connection:
                self.assertTrue(self._table_exists(connection, "mounting_nodes"))
                self.assertTrue(self._table_exists(connection, "mounting_node_items"))
                self.assertTrue(self._table_exists(connection, "mounting_node_templates"))
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM keep_me").fetchone()[0],
                    1,
                )
                second_plan = migration._build_plan(connection)
                self.assertEqual(second_plan["missing_tables"], [])
                self.assertEqual(second_plan["missing_indexes"], [])
                migration._apply_plan(connection, second_plan)

            with sqlite3.connect(database_path) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM keep_me").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM mounting_nodes",
                    ).fetchone()[0],
                    0,
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
                self.assertIn("users", plan["missing_prerequisites"])
                with self.assertRaises(SystemExit):
                    migration._apply_plan(connection, plan)

                self.assertTrue(self._table_exists(connection, "keep_me"))
                self.assertFalse(self._table_exists(connection, "mounting_nodes"))

    @staticmethod
    def _create_legacy_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fitting_hole_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fitting_id INTEGER NOT NULL,
                    name TEXT,
                    mounting_variant_key TEXT NOT NULL DEFAULT 'surface_mount'
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
