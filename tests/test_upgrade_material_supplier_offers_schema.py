from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import upgrade_material_supplier_offers_schema as migration


class UpgradeMaterialSupplierOffersSchemaTests(unittest.TestCase):
    def test_apply_adds_unique_indexes_idempotently(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy-offers.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                plan = migration._build_plan(connection)
                self.assertEqual(plan["missing_tables"], [])
                self.assertIn("uq_material_supplier_offers_identity_external", plan["missing_indexes"])
                self.assertIn("uq_material_supplier_offers_identity_no_external", plan["missing_indexes"])
                self.assertEqual(plan["duplicates"], [])

                migration._apply_plan(connection, plan, caller_owns_transaction=False)

                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertTrue(
                    connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'uq_material_supplier_offers_identity_external'"
                    ).fetchone()
                )
                self.assertTrue(
                    connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'uq_material_supplier_offers_identity_no_external'"
                    ).fetchone()
                )

                second_plan = migration._build_plan(connection)
                self.assertEqual(second_plan["missing_indexes"], [])
                self.assertEqual(second_plan["duplicates"], [])

    def test_apply_blocks_duplicate_identities(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy-offers-duplicates.db"
            self._create_legacy_database(database_path, with_duplicates=True)

            with sqlite3.connect(database_path) as connection:
                plan = migration._build_plan(connection)
                self.assertTrue(plan["duplicates"])

                with self.assertRaises(SystemExit):
                    migration._apply_plan(connection, plan, caller_owns_transaction=False)

    @staticmethod
    def _create_legacy_database(database_path: Path, *, with_duplicates: bool = False) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE material_supplier_offers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_id INTEGER NOT NULL,
                    supplier_id INTEGER NOT NULL,
                    article TEXT,
                    external_product_id TEXT,
                    source_url TEXT
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO material_supplier_offers (
                    material_id,
                    supplier_id,
                    article,
                    external_product_id,
                    source_url
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (1, 1, "A-1", "ext-1", "https://example.test/a"),
                    (1, 1, "A-2", None, "https://example.test/b"),
                ],
            )
            if with_duplicates:
                connection.executemany(
                    """
                    INSERT INTO material_supplier_offers (
                        material_id,
                        supplier_id,
                        article,
                        external_product_id,
                        source_url
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (1, 1, "A-1-DUP", "ext-1", "https://example.test/a-dup"),
                        (1, 1, "A-2-DUP", None, "https://example.test/b-dup"),
                    ],
                )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
