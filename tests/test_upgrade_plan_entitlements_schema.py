from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import upgrade_plan_entitlements_schema


class UpgradePlanEntitlementsSchemaTests(unittest.TestCase):
    def test_dry_run_does_not_change_existing_database(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                before_tables = self._table_names(connection)
                plan = upgrade_plan_entitlements_schema._build_plan(connection)
                after_tables = self._table_names(connection)

            self.assertEqual(before_tables, after_tables)
            self.assertEqual(
                plan["tables"],
                ["entitlement_features", "plan_entitlements"],
            )

    def test_apply_creates_tables_indexes_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = upgrade_plan_entitlements_schema._build_plan(connection)
                upgrade_plan_entitlements_schema._apply_plan(connection, plan)

            with sqlite3.connect(database_path) as connection:
                self.assertTrue(self._table_exists(connection, "entitlement_features"))
                self.assertTrue(self._table_exists(connection, "plan_entitlements"))
                self.assertTrue(self._table_exists(connection, "keep_me"))
                self.assertTrue(self._index_exists(connection, "ix_entitlement_features_category"))
                self.assertTrue(self._index_exists(connection, "ix_plan_entitlements_feature_id"))
                self.assertTrue(self._index_exists(connection, "ix_plan_entitlements_plan_code"))

                dry_plan = upgrade_plan_entitlements_schema._build_plan(connection)
                self.assertEqual(dry_plan["tables"], [])
                self.assertEqual(dry_plan["indexes"], [])

                upgrade_plan_entitlements_schema._apply_plan(connection, dry_plan)

            with sqlite3.connect(database_path) as connection:
                self.assertTrue(self._table_exists(connection, "entitlement_features"))
                self.assertTrue(self._table_exists(connection, "plan_entitlements"))

    def test_constraints_and_foreign_keys_work_on_temp_database(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                connection.execute("PRAGMA foreign_keys=ON")
                plan = upgrade_plan_entitlements_schema._build_plan(connection)
                upgrade_plan_entitlements_schema._apply_plan(connection, plan)

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
                        "ai_scan_limit",
                        "Ліміт AI-сканів",
                        None,
                        "ai",
                        "integer",
                        None,
                        1,
                        0,
                    ),
                )
                feature_id = connection.execute(
                    "SELECT id FROM entitlement_features WHERE feature_key = ?",
                    ("ai_scan_limit",),
                ).fetchone()[0]

                connection.execute(
                    """
                    INSERT INTO plan_entitlements (
                        feature_id,
                        plan_code,
                        bool_value,
                        integer_value,
                        decimal_value,
                        text_value,
                        is_unlimited,
                        is_not_applicable
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (feature_id, "pro", None, 15, None, None, 0, 0),
                )

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO plan_entitlements (
                            feature_id,
                            plan_code,
                            bool_value,
                            integer_value,
                            decimal_value,
                            text_value,
                            is_unlimited,
                            is_not_applicable
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (feature_id, "starter", None, None, None, None, 0, 0),
                    )
                connection.rollback()

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO plan_entitlements (
                            feature_id,
                            plan_code,
                            bool_value,
                            integer_value,
                            decimal_value,
                            text_value,
                            is_unlimited,
                            is_not_applicable
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (999999, "free", 1, None, None, None, 0, 0),
                    )
                connection.rollback()

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO plan_entitlements (
                            feature_id,
                            plan_code,
                            bool_value,
                            integer_value,
                            decimal_value,
                            text_value,
                            is_unlimited,
                            is_not_applicable
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (feature_id, "business", None, None, None, None, 1, 1),
                    )
                connection.rollback()

                with self.assertRaises(sqlite3.IntegrityError):
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
                        ("bad-type", "Bad type", None, "ai", "blob", None, 1, 0),
                    )
                connection.rollback()

                connection.commit()

    def test_apply_rolls_back_entire_schema_on_error(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            original_plan_sql = upgrade_plan_entitlements_schema.PLAN_TABLE_SQL
            upgrade_plan_entitlements_schema.PLAN_TABLE_SQL = "CREATE TABLE plan_entitlements (bad sql"
            try:
                with sqlite3.connect(database_path) as connection:
                    plan = upgrade_plan_entitlements_schema._build_plan(connection)
                    with self.assertRaises(sqlite3.OperationalError):
                        upgrade_plan_entitlements_schema._apply_plan(connection, plan)
            finally:
                upgrade_plan_entitlements_schema.PLAN_TABLE_SQL = original_plan_sql

            with sqlite3.connect(database_path) as connection:
                self.assertFalse(self._table_exists(connection, "entitlement_features"))
                self.assertFalse(self._table_exists(connection, "plan_entitlements"))
                self.assertFalse(self._index_exists(connection, "ix_entitlement_features_category"))
                self.assertFalse(self._index_exists(connection, "ix_plan_entitlements_feature_id"))
                self.assertFalse(self._index_exists(connection, "ix_plan_entitlements_plan_code"))
                self.assertTrue(self._table_exists(connection, "keep_me"))
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM keep_me").fetchone()[0],
                    1,
                )

    @staticmethod
    def _create_legacy_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
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
    def _table_names(connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {str(row[0]) for row in rows}

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            (index_name,),
        ).fetchone()
        return row is not None


if __name__ == "__main__":
    unittest.main()
