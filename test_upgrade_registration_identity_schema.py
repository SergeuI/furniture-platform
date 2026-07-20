from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import upgrade_registration_identity_schema


class UpgradeRegistrationIdentitySchemaTests(unittest.TestCase):
    def test_dry_run_does_not_change_existing_database(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_users_table(database_path)

            with sqlite3.connect(database_path) as connection:
                before_tables = self._table_names(connection)
                before_columns = self._column_names(connection, "users")
                plan = upgrade_registration_identity_schema._build_plan(connection)
                after_tables = self._table_names(connection)
                after_columns = self._column_names(connection, "users")

            self.assertEqual(before_tables, after_tables)
            self.assertEqual(before_columns, after_columns)
            self.assertEqual(plan["user_columns"], ["registration_status", "phone_verified_at"])
            self.assertIn("registration_identities", plan["tables"])
            self.assertIn("registration_challenges", plan["tables"])

    def test_apply_adds_columns_tables_and_indexes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_users_table(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = upgrade_registration_identity_schema._build_plan(connection)
                upgrade_registration_identity_schema._apply_plan(connection, plan)

            with sqlite3.connect(database_path) as connection:
                user_columns = self._column_names(connection, "users")
                self.assertIn("registration_status", user_columns)
                self.assertIn("phone_verified_at", user_columns)
                self.assertTrue(self._table_exists(connection, "registration_identities"))
                self.assertTrue(self._table_exists(connection, "registration_challenges"))
                self.assertTrue(self._index_exists(connection, "ix_registration_identities_identity_type"))
                self.assertTrue(self._index_exists(connection, "ix_registration_challenges_status"))
                self.assertIn("status_token_hash", self._column_names(connection, "registration_challenges"))
                self.assertTrue(self._index_exists(connection, "uq_registration_challenges_status_token_hash"))

                dry_plan = upgrade_registration_identity_schema._build_plan(connection)
                self.assertEqual(dry_plan["user_columns"], [])
                self.assertEqual(dry_plan["tables"], [])
                self.assertEqual(dry_plan["table_columns"], [])
                self.assertEqual(dry_plan["indexes"], [])

    @staticmethod
    def _create_legacy_users_table(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE users (
                    id VARCHAR PRIMARY KEY,
                    email VARCHAR NOT NULL,
                    password_hash VARCHAR NOT NULL,
                    role VARCHAR NOT NULL,
                    is_active BOOLEAN NOT NULL
                )
                """
            )
            connection.commit()

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {str(row[0]) for row in rows}

    @staticmethod
    def _column_names(connection: sqlite3.Connection, table_name: str) -> list[str]:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return [str(row[1]) for row in rows]

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
