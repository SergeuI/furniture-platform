from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import upgrade_entitlement_registry_schema as migration


class UpgradeEntitlementRegistrySchemaTests(unittest.TestCase):
    def test_dry_run_reports_missing_is_system_column_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                before_columns = self._column_names(connection)
                plan = migration._build_plan(connection)
                after_columns = self._column_names(connection)

            self.assertEqual(before_columns, after_columns)
            self.assertEqual(plan["prerequisite_missing"], False)
            self.assertEqual(plan["missing_columns"], ["is_system"])
            self.assertEqual(plan["missing_indexes"], ["ix_entitlement_features_is_system"])

    def test_apply_adds_is_system_column_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = migration._build_plan(connection)
                migration._apply_plan(connection, plan)

            with sqlite3.connect(database_path) as connection:
                self.assertTrue(self._column_exists(connection, "entitlement_features", "is_system"))
                self.assertTrue(self._index_exists(connection, "ix_entitlement_features_is_system"))
                self.assertEqual(
                    connection.execute(
                        "SELECT is_system FROM entitlement_features WHERE feature_key = ?",
                        ("legacy_feature",),
                    ).fetchone()[0],
                    0,
                )

                second_plan = migration._build_plan(connection)
                self.assertEqual(second_plan["missing_columns"], [])
                self.assertEqual(second_plan["missing_indexes"], [])

                migration._apply_plan(connection, second_plan)

            with sqlite3.connect(database_path) as connection:
                self.assertTrue(self._column_exists(connection, "entitlement_features", "is_system"))
                self.assertTrue(self._index_exists(connection, "ix_entitlement_features_is_system"))
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM entitlement_features",
                    ).fetchone()[0],
                    1,
                )

    def test_apply_rolls_back_entire_schema_on_error(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            original_index_sql = migration.INDEX_SQL
            migration.INDEX_SQL = (
                "CREATE INDEX IF NOT EXISTS ix_entitlement_features_is_system ON entitlement_features ("
            )
            try:
                with sqlite3.connect(database_path) as connection:
                    plan = migration._build_plan(connection)
                    with self.assertRaises(sqlite3.OperationalError):
                        migration._apply_plan(connection, plan)
            finally:
                migration.INDEX_SQL = original_index_sql

            with sqlite3.connect(database_path) as connection:
                self.assertFalse(self._column_exists(connection, "entitlement_features", "is_system"))
                self.assertFalse(self._index_exists(connection, "ix_entitlement_features_is_system"))
                self.assertTrue(self._table_exists(connection, "entitlement_features"))
                self.assertTrue(self._table_exists(connection, "keep_me"))
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM keep_me",
                    ).fetchone()[0],
                    1,
                )

    def test_missing_prerequisite_table_is_reported_without_creating_schema(self) -> None:
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
                self.assertEqual(plan["missing_tables"], ["entitlement_features"])
                with self.assertRaises(SystemExit):
                    migration._apply_plan(connection, plan)

                self.assertFalse(self._table_exists(connection, "entitlement_features"))
                self.assertTrue(self._table_exists(connection, "keep_me"))

    @staticmethod
    def _create_legacy_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE entitlement_features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feature_key VARCHAR NOT NULL UNIQUE,
                    name_uk VARCHAR NOT NULL,
                    description_uk TEXT,
                    category VARCHAR NOT NULL,
                    value_type VARCHAR NOT NULL,
                    enum_options_json JSON,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK (trim(feature_key) <> ''),
                    CHECK (trim(name_uk) <> ''),
                    CHECK (trim(category) <> ''),
                    CHECK (value_type IN ('boolean', 'integer', 'decimal', 'text', 'enum'))
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
                """
                INSERT INTO entitlement_features (
                    feature_key,
                    name_uk,
                    description_uk,
                    category,
                    value_type,
                    enum_options_json,
                    is_active,
                    sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy_feature",
                    "Legacy feature",
                    None,
                    "legacy",
                    "boolean",
                    None,
                    1,
                    0,
                ),
            )
            connection.execute(
                "INSERT INTO keep_me (name) VALUES (?)",
                ("stable",),
            )
            connection.commit()

    @staticmethod
    def _column_names(connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute("PRAGMA table_info(entitlement_features)").fetchall()
        return {str(row[1]) for row in rows}

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

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None


if __name__ == "__main__":
    unittest.main()
