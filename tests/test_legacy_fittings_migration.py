from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.legacy_db_config import migrate_legacy_sqlite_to_unified_db


class LegacyFittingsMigrationTests(unittest.TestCase):
    def test_startup_mode_skips_copying_fittings(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            target_db_path = Path(tmpdir) / "target.db"
            legacy_db_path = Path(tmpdir) / "legacy.db"

            self._create_target_database(target_db_path)
            self._create_legacy_database(legacy_db_path)

            migrate_legacy_sqlite_to_unified_db(
                target_db_path=str(target_db_path),
                legacy_db_path=str(legacy_db_path),
                copy_fittings=False,
            )

            with sqlite3.connect(target_db_path) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fittings").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0], 0)
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_explicit_migration_still_copies_fittings(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            target_db_path = Path(tmpdir) / "target.db"
            legacy_db_path = Path(tmpdir) / "legacy.db"

            self._create_target_database(target_db_path)
            self._create_legacy_database(legacy_db_path)

            migrate_legacy_sqlite_to_unified_db(
                target_db_path=str(target_db_path),
                legacy_db_path=str(legacy_db_path),
            )

            with sqlite3.connect(target_db_path) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fittings").fetchone()[0], 1)
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    @staticmethod
    def _create_target_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city TEXT,
                    code TEXT,
                    article TEXT,
                    name TEXT,
                    price REAL,
                    stock TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT,
                    name TEXT
                )
                """
            )
            connection.commit()

    @staticmethod
    def _create_legacy_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city TEXT,
                    code TEXT,
                    article TEXT,
                    name TEXT,
                    price REAL,
                    stock TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                INSERT INTO fittings (id, city, code, article, name, price, stock)
                VALUES (1, 'kyiv', 'C-1', 'A-1', 'Legacy fitting', 10.5, 'in stock')
                """
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
