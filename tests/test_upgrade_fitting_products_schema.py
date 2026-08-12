from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine

from scripts import upgrade_fitting_products_schema as migration


class UpgradeFittingProductsSchemaTests(unittest.TestCase):
    def test_dry_run_reports_canonical_products_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                before_count = connection.execute(
                    "SELECT COUNT(*) FROM fittings",
                ).fetchone()[0]
                plan = migration._build_plan(connection)
                after_count = connection.execute(
                    "SELECT COUNT(*) FROM fittings",
                ).fetchone()[0]

            self.assertEqual(before_count, after_count)
            self.assertFalse(plan["prerequisite_missing"])
            self.assertEqual(plan["missing_tables"], ["fitting_products"])
            self.assertEqual(plan["missing_columns"], ["technical_product_id"])
            self.assertIn("uq_fitting_products_article", plan["missing_indexes"])
            self.assertIn("ix_fittings_technical_product_id", plan["missing_indexes"])
            self.assertEqual(len(plan["canonical_groups"]), 2)
            self.assertEqual(len(plan["ambiguous_groups"]), 1)
            self.assertEqual(len(plan["products_to_upsert"]), 2)
            self.assertEqual(len(plan["fitting_link_updates"]), 3)
            self.assertEqual(len(plan["ambiguous_nullifications"]), 0)

    def test_apply_creates_schema_backfills_only_unambiguous_rows_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                counts_before = self._counts_snapshot(connection)
                plan = migration._build_plan(connection)
                migration._apply_plan(connection, plan, False)

            with sqlite3.connect(database_path) as connection:
                counts_after = self._counts_snapshot(connection)
                self.assertEqual(counts_before["fittings"], counts_after["fittings"])
                self.assertEqual(counts_after["fitting_products"], 2)
                self.assertEqual(
                    connection.execute(
                        "PRAGMA integrity_check",
                    ).fetchone()[0],
                    "ok",
                )

                product_rows = connection.execute(
                    """
                    SELECT id, article, code, name, brand, description, is_active
                    FROM fitting_products
                    ORDER BY id
                    """,
                ).fetchall()
                self.assertEqual([row[1] for row in product_rows], ["A-100", "C-300"])

                fitting_rows = {
                    row[0]: row[1]
                    for row in connection.execute(
                        "SELECT id, technical_product_id FROM fittings ORDER BY id",
                    ).fetchall()
                }
                self.assertIsNotNone(fitting_rows[1])
                self.assertEqual(fitting_rows[1], fitting_rows[2])
                self.assertIsNone(fitting_rows[3])
                self.assertIsNone(fitting_rows[4])
                self.assertIsNotNone(fitting_rows[5])
                self.assertIsNone(fitting_rows[6])

                second_plan = migration._build_plan(connection)
                self.assertEqual(second_plan["missing_tables"], [])
                self.assertEqual(second_plan["missing_columns"], [])
                self.assertEqual(second_plan["missing_indexes"], [])
                self.assertEqual(second_plan["products_to_upsert"], [])
                self.assertEqual(second_plan["fitting_link_updates"], [])
                self.assertEqual(second_plan["ambiguous_nullifications"], [])
                migration.ensure_fitting_products_schema(connection)

            with sqlite3.connect(database_path) as connection:
                self.assertEqual(
                    connection.execute(
                        "PRAGMA integrity_check",
                    ).fetchone()[0],
                    "ok",
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM fitting_products").fetchone()[0],
                    2,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM fittings").fetchone()[0],
                    6,
                )

    def test_ensure_inside_outer_transaction_keeps_transaction_open(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            with engine.begin() as connection:
                migration.ensure_fitting_products_schema(connection)
                self.assertEqual(
                    connection.exec_driver_sql("SELECT COUNT(*) FROM fitting_products").fetchone()[0],
                    2,
                )
                self.assertEqual(
                    connection.exec_driver_sql("SELECT 1").fetchone()[0],
                    1,
                )
                migration.ensure_fitting_products_schema(connection)
                self.assertEqual(
                    connection.exec_driver_sql("SELECT COUNT(*) FROM fitting_products").fetchone()[0],
                    2,
                )

            with sqlite3.connect(database_path) as connection:
                self.assertEqual(
                    connection.execute(
                        "PRAGMA integrity_check",
                    ).fetchone()[0],
                    "ok",
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM fitting_products").fetchone()[0],
                    2,
                )

    @staticmethod
    def _create_legacy_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT,
                    code TEXT,
                    name TEXT,
                    brand TEXT,
                    description TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO fittings (
                    id,
                    article,
                    code,
                    name,
                    brand,
                    description,
                    is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (1, "A-100", "C100", "Alpha", "BrandA", "Desc A", 1),
                    (2, "A-100", "C100", "Alpha", "BrandA", "Desc A", 1),
                    (3, "B-200", "C200", "Bravo", "BrandB", None, 1),
                    (4, "B-200", "C200", "Bravo alt", "BrandB", None, 1),
                    (5, "C-300", None, "Charlie", None, None, 0),
                    (6, None, None, "No Article", None, None, 1),
                ],
            )
            connection.commit()

    @staticmethod
    def _counts_snapshot(connection: sqlite3.Connection) -> dict[str, int]:
        fitting_products_count = 0
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'fitting_products'",
        ).fetchone() is not None:
            fitting_products_count = connection.execute(
                "SELECT COUNT(*) FROM fitting_products",
            ).fetchone()[0]
        return {
            "fittings": connection.execute("SELECT COUNT(*) FROM fittings").fetchone()[0],
            "fitting_products": fitting_products_count,
        }


if __name__ == "__main__":
    unittest.main()
