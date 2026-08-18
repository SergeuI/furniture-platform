from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.repositories import inventory_repository


class SupplierLogoRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database_path = Path(self._tmpdir.name) / "suppliers.db"
        self._create_schema(self.database_path)

        self.engine = create_engine(
            f"sqlite:///{self.database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        self._original_session_local = inventory_repository.SessionLocal
        inventory_repository.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def tearDown(self) -> None:
        inventory_repository.SessionLocal = self._original_session_local
        self.engine.dispose()
        self._tmpdir.cleanup()

    def test_create_update_clear_and_list_logo_url(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("INSERT INTO users (id, email) VALUES (?, ?)", ("owner-1", "owner@example.com"))
            connection.commit()

        created = inventory_repository.create_supplier(
            code="viyar",
            name="VIYAR",
            logo_url="https://example.test/viyar-logo.svg",
            is_system=True,
        )
        self.assertIsNotNone(created)
        assert created is not None
        self.assertEqual(created["code"], "viyar")
        self.assertEqual(created["logo_url"], "https://example.test/viyar-logo.svg")
        self.assertIsNone(created["owner_user_id"])
        self.assertTrue(created["is_system"])

        personal = inventory_repository.create_supplier(
            code="private-supplier",
            name="Private Supplier",
            owner_user_id="owner-1",
            is_system=False,
        )
        self.assertIsNotNone(personal)
        assert personal is not None
        self.assertEqual(personal["owner_user_id"], "owner-1")
        self.assertFalse(personal["is_system"])

        listed = inventory_repository.list_suppliers(include_inactive=True)
        self.assertEqual([item["code"] for item in listed], ["viyar"])
        self.assertEqual(listed[0]["logo_url"], "https://example.test/viyar-logo.svg")

        owner_listed = inventory_repository.list_suppliers(include_inactive=True, current_user_id="owner-1")
        self.assertEqual({item["code"] for item in owner_listed}, {"viyar", "private-supplier"})
        self.assertEqual(
            next(item for item in owner_listed if item["code"] == "private-supplier")["owner_user_id"],
            "owner-1",
        )

        detail = inventory_repository.get_supplier_by_id(created["id"])
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["logo_url"], "https://example.test/viyar-logo.svg")

        updated = inventory_repository.update_supplier(
            created["id"],
            name="VIYAR",
            logo_url="https://example.test/viyar-logo-2.svg",
        )
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["code"], "viyar")
        self.assertEqual(updated["logo_url"], "https://example.test/viyar-logo-2.svg")

        cleared = inventory_repository.update_supplier(
            created["id"],
            logo_url="",
        )
        self.assertIsNotNone(cleared)
        assert cleared is not None
        self.assertIsNone(cleared["logo_url"])
        self.assertEqual(cleared["code"], "viyar")

    @staticmethod
    def _create_schema(database_path: Path) -> None:
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
                CREATE TABLE suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    logo_url TEXT,
                    owner_user_id TEXT,
                    is_system INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
