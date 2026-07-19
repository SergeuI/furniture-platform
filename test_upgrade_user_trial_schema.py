from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import upgrade_user_trial_schema


class UpgradeUserTrialSchemaTests(unittest.TestCase):
    def test_build_plan_and_apply_add_trial_columns(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_users_table(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = upgrade_user_trial_schema._build_plan(connection)
                self.assertEqual(plan, ["trial_started_at", "trial_ends_at"])
                upgrade_user_trial_schema._apply_plan(connection, plan)

            with sqlite3.connect(database_path) as connection:
                rows = connection.execute("PRAGMA table_info(users)").fetchall()
                column_names = [row[1] for row in rows]
                self.assertIn("trial_started_at", column_names)
                self.assertIn("trial_ends_at", column_names)

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
                    is_active BOOLEAN NOT NULL,
                    viyar_email VARCHAR,
                    viyar_password_secret VARCHAR,
                    viyar_cookie VARCHAR,
                    viyar_cookie_updated_at DATETIME,
                    viyar_last_auth_at DATETIME,
                    viyar_last_auth_status VARCHAR,
                    viyar_last_auth_error VARCHAR,
                    username VARCHAR,
                    phone VARCHAR,
                    telegram_id VARCHAR,
                    last_username_change_at DATETIME,
                    city VARCHAR
                )
                """
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
