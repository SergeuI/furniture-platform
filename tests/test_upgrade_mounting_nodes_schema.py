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
                "mounting_node_versions",
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
                self.assertTrue(self._table_exists(connection, "mounting_node_versions"))
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
                self.assertIn("is_archived", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("archived_at", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("archived_by_user_id", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("category_code", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("functional_code", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("preview_mode", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("preview_generated_image_url", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("preview_custom_image_url", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("preview_generated_at", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("preview_auto_image_url", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("preview_3d_image_url", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("preview_auto_generated_at", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("preview_3d_generated_at", self._get_column_names(connection, "mounting_nodes"))
                self.assertIn("snapshot", self._get_column_names(connection, "mounting_node_versions"))

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

    def test_existing_mounting_nodes_table_gets_preview_columns_without_losing_rows(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE mounting_nodes (
                        id INTEGER PRIMARY KEY,
                        code TEXT,
                        name TEXT,
                        owner_user_id TEXT,
                        created_by_user_id TEXT,
                        updated_by_user_id TEXT,
                        is_archived BOOLEAN NOT NULL DEFAULT 0,
                        archived_by_user_id TEXT
                    )
                    """
                )
                connection.execute("INSERT INTO mounting_nodes (id, code, name) VALUES (1, 'legacy', 'Legacy')")
                connection.commit()
                plan = migration._build_plan(connection)
                self.assertEqual(set(plan["missing_columns"]), set(migration.MOUNTING_NODE_COLUMN_ADDITIONS))
                migration._apply_plan(connection, plan)
                row = connection.execute("SELECT preview_mode, name FROM mounting_nodes WHERE id = 1").fetchone()
                self.assertEqual(row, ("auto", "Legacy"))

    def test_generated_preview_backfills_3d_only_without_overwriting_new_values(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)
            with sqlite3.connect(database_path) as connection:
                connection.execute(migration.TABLES["mounting_nodes"].replace(
                    "            preview_auto_image_url TEXT,\n            preview_3d_image_url TEXT,\n", "",
                ).replace(
                    "            preview_auto_generated_at DATETIME,\n            preview_3d_generated_at DATETIME,\n", "",
                ))
                connection.execute("INSERT INTO mounting_nodes (code, name, preview_generated_image_url, preview_generated_at) VALUES ('old', 'Old', '/legacy.png', '2026-01-01')")
                connection.execute("INSERT INTO mounting_nodes (code, name, preview_mode) VALUES ('invalid', 'Invalid custom', 'custom')")
                connection.commit()
                plan = migration._build_plan(connection)
                self.assertIn("preview_3d_image_url", plan["missing_columns"])
                self.assertEqual(plan["preview_backfill_rows"], 1)
                migration._apply_plan(connection, plan)
                row = connection.execute("SELECT preview_mode, preview_auto_image_url, preview_3d_image_url, preview_3d_generated_at, preview_generated_image_url FROM mounting_nodes WHERE code = 'old'").fetchone()
                self.assertEqual(row, ("auto", None, "/legacy.png", "2026-01-01", "/legacy.png"))
                self.assertEqual(connection.execute("SELECT preview_mode FROM mounting_nodes WHERE code = 'invalid'").fetchone()[0], "auto")
                connection.execute("UPDATE mounting_nodes SET preview_3d_image_url = '/new.png', preview_3d_generated_at = '2026-02-01' WHERE code = 'old'")
                connection.commit()
                second_plan = migration._build_plan(connection)
                self.assertEqual(second_plan["preview_backfill_rows"], 0)
                migration._apply_plan(connection, second_plan)
                self.assertEqual(connection.execute("SELECT preview_3d_image_url, preview_3d_generated_at FROM mounting_nodes WHERE code = 'old'").fetchone(), ("/new.png", "2026-02-01"))

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

    @staticmethod
    def _get_column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row[1] for row in rows}


if __name__ == "__main__":
    unittest.main()
