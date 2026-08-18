from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import upgrade_suppliers_ownership_schema as migration


class UpgradeSuppliersOwnershipSchemaTests(unittest.TestCase):
    def test_apply_adds_owner_and_system_columns_and_backfills_existing_suppliers(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = migration._build_plan(connection)
                self.assertFalse(plan["prerequisite_missing"])
                self.assertEqual(plan["missing_columns"], ["owner_user_id", "is_system", "logo_url"])
                self.assertEqual(
                    set(plan["missing_indexes"]),
                    {"ix_suppliers_owner_user_id", "ix_suppliers_is_system"},
                )
                self.assertEqual(plan["existing_supplier_count"], 2)
                migration._apply_plan(connection, plan)

            with sqlite3.connect(database_path) as connection:
                supplier_rows = connection.execute(
                    "SELECT id, code, logo_url, owner_user_id, is_system FROM suppliers ORDER BY id",
                ).fetchall()
                offer_count = connection.execute(
                    "SELECT COUNT(*) FROM fitting_supplier_offers",
                ).fetchone()[0]
                fk_rows = connection.execute("PRAGMA foreign_key_list(suppliers)").fetchall()
                columns = [row[1] for row in connection.execute("PRAGMA table_info(suppliers)").fetchall()]

                self.assertEqual(len(supplier_rows), 2)
                self.assertEqual([tuple(row) for row in supplier_rows], [
                    (1, "viyar", None, None, 1),
                    (2, "private-legacy", None, None, 1),
                ])
                self.assertIn("logo_url", columns)
                self.assertEqual(offer_count, 1)
                self.assertTrue(
                    any(
                        str(row[2]) == "users"
                        and str(row[3]) == "owner_user_id"
                        and str(row[4]) == "id"
                        for row in fk_rows
                    )
                )
                self.assertTrue(self._index_exists(connection, "ix_suppliers_owner_user_id"))
                self.assertTrue(self._index_exists(connection, "ix_suppliers_is_system"))
                self.assertEqual(
                    connection.execute("PRAGMA integrity_check").fetchone()[0],
                    "ok",
                )
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

                second_plan = migration._build_plan(connection)
                self.assertEqual(second_plan["missing_columns"], [])
                self.assertEqual(second_plan["missing_indexes"], [])
                migration._apply_plan(connection, second_plan)

    def test_dry_run_keeps_legacy_counts_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                before_count = connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
                plan = migration._build_plan(connection)
                after_count = connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]

            self.assertEqual(before_count, after_count)
            self.assertFalse(plan["prerequisite_missing"])
            self.assertEqual(before_count, 2)

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
                CREATE TABLE suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fitting_supplier_offers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fitting_id INTEGER NOT NULL,
                    supplier_id INTEGER NOT NULL,
                    article TEXT,
                    external_product_id TEXT,
                    source_url TEXT,
                    price REAL,
                    currency TEXT DEFAULT 'UAH',
                    unit TEXT DEFAULT 'шт',
                    stock TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 0,
                    parsed_at TEXT,
                    price_updated_at TEXT,
                    source_payload_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(fitting_id) REFERENCES fittings (id),
                    FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
                )
                """
            )
            connection.execute(
                "INSERT INTO users (id, email) VALUES (?, ?)",
                ("owner-1", "owner@example.com"),
            )
            connection.execute(
                "INSERT INTO fittings (id, name) VALUES (?, ?)",
                (10, "Legacy fitting"),
            )
            connection.executemany(
                """
                INSERT INTO suppliers (id, code, name, is_active)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (1, "viyar", "VIYAR", 1),
                    (2, "private-legacy", "Private Legacy", 1),
                ],
            )
            connection.execute(
                """
                INSERT INTO fitting_supplier_offers (
                    fitting_id,
                    supplier_id,
                    article,
                    source_url,
                    price,
                    is_active,
                    priority
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (10, 1, "190106", "https://viyar.ua/ua/catalog/konfirmat-7x50/", 1.14, 1, 100),
            )
            connection.commit()

    @staticmethod
    def _index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            (index_name,),
        ).fetchone()
        return row is not None


if __name__ == "__main__":
    unittest.main()
