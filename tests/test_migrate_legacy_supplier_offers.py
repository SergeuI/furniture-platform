from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import migrate_legacy_supplier_offers as migration


class MigrateLegacySupplierOffersTests(unittest.TestCase):
    def test_dry_run_reports_canonical_groups_and_skipped_source_null_rows(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                plan = migration._build_plan(connection)

            self.assertFalse(plan["prerequisite_missing"])
            self.assertEqual(plan["missing_columns"], [])
            self.assertEqual(plan["missing_indexes"], [])
            self.assertIsNotNone(plan["supplier"])
            self.assertEqual(len(plan["offer_rows"]), 7)
            self.assertEqual(len(plan["planned_offers"]), 4)
            self.assertEqual(len(plan["skipped_rows"]), 3)

            statuses = {int(row["source_fitting_id"]): row["status"] for row in plan["offer_rows"]}
            self.assertEqual(statuses[41], "planned_offer")
            self.assertEqual(statuses[44], "planned_offer")
            self.assertEqual(statuses[45], "skipped_duplicate")
            self.assertEqual(statuses[46], "skipped_duplicate")
            self.assertEqual(statuses[48], "planned_offer")
            self.assertEqual(statuses[49], "skipped_duplicate")
            self.assertEqual(statuses[59], "planned_offer")

            groups = {row["article"]: row for row in plan["catalog_key_groups"]}
            self.assertEqual(groups["190106"]["canonical_fitting_id"], 45)
            self.assertEqual(groups["190106"]["source_fitting_ids"], [45, 46, 59])
            self.assertEqual(groups["61136"]["canonical_fitting_id"], 48)
            self.assertEqual(groups["61136"]["source_fitting_ids"], [48, 49])

    def test_apply_creates_expected_offers_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "legacy.db"
            self._create_legacy_database(database_path)

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                counts_before = self._counts_snapshot(connection)
                fittings_before = self._load_fittings(connection)
                plan = migration._build_plan(connection)
                migration._apply_plan(connection, plan)

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                counts_after = self._counts_snapshot(connection)
                fittings_after = self._load_fittings(connection)
                offers = self._load_offers(connection)
                supplier_rows = connection.execute(
                    "SELECT id, code, name, is_active FROM suppliers ORDER BY id",
                ).fetchall()

                self.assertEqual(counts_before["fittings"], counts_after["fittings"])
                self.assertEqual(counts_before["mounting_node_items"], counts_after["mounting_node_items"])
                self.assertEqual(counts_before["fitting_hole_templates"], counts_after["fitting_hole_templates"])
                self.assertEqual(counts_before["fitting_images"], counts_after["fitting_images"])
                self.assertEqual(len(fittings_before), len(fittings_after))
                self.assertEqual(fittings_before, fittings_after)

                self.assertEqual(len(offers), 4)
                self.assertEqual([row["fitting_id"] for row in offers], [41, 44, 45, 48])
                self.assertEqual([row["supplier_code"] for row in offers], ["viyar", "viyar", "viyar", "viyar"])
                self.assertEqual(offers[2]["article"], "190106")
                self.assertEqual(offers[2]["source_url"], "https://viyar.ua/ua/catalog/konfirmat-7x50/")
                self.assertEqual(offers[2]["priority"], 100)
                self.assertEqual(offers[2]["is_active"], 1)
                self.assertEqual(offers[2]["external_product_id"], None)
                self.assertEqual(offers[2]["payload"], "present")
                self.assertEqual(len(supplier_rows), 1)
                self.assertEqual(tuple(supplier_rows[0]), (1, "viyar", "VIYAR", 1))

                second_plan = migration._build_plan(connection)
                migration._apply_plan(connection, second_plan)

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                self.assertEqual(self._count(connection, "fitting_supplier_offers"), 4)
                self.assertEqual(self._count(connection, "suppliers"), 1)
                self.assertEqual(
                    [row["fitting_id"] for row in self._load_offers(connection)],
                    [41, 44, 45, 48],
                )
                self.assertEqual(self._count(connection, "fittings"), 7)
                self.assertEqual(self._count(connection, "mounting_node_items"), 1)
                self.assertEqual(self._count(connection, "fitting_hole_templates"), 1)
                self.assertEqual(self._count(connection, "fitting_images"), 1)

    @staticmethod
    def _create_legacy_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    catalog_key TEXT NOT NULL UNIQUE,
                    article TEXT,
                    name TEXT,
                    source TEXT,
                    price REAL,
                    currency TEXT,
                    unit TEXT,
                    stock TEXT,
                    source_url TEXT,
                    parsed_at TEXT,
                    price_updated_at TEXT,
                    source_payload_json TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1
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
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX uq_fitting_supplier_offers_identity_external
                ON fitting_supplier_offers (fitting_id, supplier_id, external_product_id)
                WHERE external_product_id IS NOT NULL
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX uq_fitting_supplier_offers_identity_no_external
                ON fitting_supplier_offers (fitting_id, supplier_id)
                WHERE external_product_id IS NULL
                """
            )
            connection.execute(
                """
                CREATE INDEX ix_fitting_supplier_offers_fitting_id
                ON fitting_supplier_offers (fitting_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX ix_fitting_supplier_offers_supplier_id
                ON fitting_supplier_offers (supplier_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX ix_fitting_supplier_offers_priority
                ON fitting_supplier_offers (priority)
                """
            )
            connection.execute(
                """
                CREATE TABLE mounting_node_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fitting_hole_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fitting_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                )
                """
            )
            connection.execute(
                "INSERT INTO suppliers (code, name, is_active) VALUES (?, ?, ?)",
                ("viyar", "VIYAR", 1),
            )
            connection.executemany(
                """
                INSERT INTO fittings (
                    id,
                    catalog_key,
                    article,
                    name,
                    source,
                    price,
                    currency,
                    unit,
                    stock,
                    source_url,
                    parsed_at,
                    price_updated_at,
                    source_payload_json,
                    is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        41,
                        "catalog-key-41",
                        "213753",
                        "Ручка LT22 / 192/212 алюміній C-0",
                        "viyar",
                        90.48,
                        "UAH",
                        "шт",
                        "В наявності",
                        "https://viyar.ua/ua/catalog/ruchka-lt22-192-212-alyuminiy-c-0/",
                        "2026-07-15T23:31:54Z",
                        "2026-07-15T23:31:54Z",
                        json.dumps(
                            {
                                "source_site": "viyar",
                                "source_url": "https://viyar.ua/ua/catalog/ruchka-lt22-192-212-alyuminiy-c-0/",
                                "parsed_item": {"article": "213753"},
                            },
                            ensure_ascii=False,
                        ),
                        1,
                    ),
                    (
                        44,
                        "catalog-key-44",
                        "57412",
                        "Ніжка кухонна H=100мм, чорна, Sсilm",
                        None,
                        13.98,
                        "UAH",
                        "шт",
                        None,
                        "https://viyar.ua/ua/catalog/nozhka_kukhonnaya_h_100mm_chernaya_ssilm/",
                        None,
                        None,
                        json.dumps(
                            {
                                "source_site": "viyar",
                                "source_url": "https://viyar.ua/ua/catalog/nozhka_kukhonnaya_h_100mm_chernaya_ssilm/",
                                "parsed_item": {"article": "57412"},
                            },
                            ensure_ascii=False,
                        ),
                        1,
                    ),
                    (
                        45,
                        "catalog-key-45",
                        "190106",
                        "Конфірмат (стяжка) оцинков. 7,0х50 мм під шестигранник",
                        None,
                        1.14,
                        "UAH",
                        "шт",
                        None,
                        "https://viyar.ua/ua/catalog/konfirmat-7x50/",
                        None,
                        None,
                        json.dumps(
                            {
                                "source_site": "viyar",
                                "source_url": "https://viyar.ua/ua/catalog/konfirmat-7x50/",
                                "parsed_item": {"article": "190106"},
                            },
                            ensure_ascii=False,
                        ),
                        1,
                    ),
                    (
                        46,
                        "catalog-key-46",
                        "190106",
                        "Конфірмат (стяжка) оцинков. 7,0х50 мм під шестигранник",
                        None,
                        1.14,
                        "UAH",
                        "шт",
                        None,
                        "https://viyar.ua/ua/catalog/konfirmat-7x50/",
                        None,
                        None,
                        json.dumps(
                            {
                                "source_site": "viyar",
                                "source_url": "https://viyar.ua/ua/catalog/konfirmat-7x50/",
                                "parsed_item": {"article": "190106"},
                            },
                            ensure_ascii=False,
                        ),
                        1,
                    ),
                    (
                        48,
                        "catalog-key-48",
                        "61136",
                        "Дюбель під стяжку VB DU 321 (9021847) Hettich",
                        "viyar",
                        5.1,
                        "UAH",
                        "шт",
                        "В наявності",
                        "https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                        None,
                        None,
                        json.dumps(
                            {
                                "source_site": "viyar",
                                "source_url": "https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                                "parsed_item": {"article": "61136"},
                            },
                            ensure_ascii=False,
                        ),
                        1,
                    ),
                    (
                        49,
                        "catalog-key-49",
                        "61136",
                        "Дюбель під стяжку VB DU 321 (9021847) Hettich",
                        "viyar",
                        5.1,
                        "UAH",
                        "шт",
                        "В наявності",
                        "https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                        None,
                        None,
                        json.dumps(
                            {
                                "source_site": "viyar",
                                "source_url": "https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                                "parsed_item": {"article": "61136"},
                            },
                            ensure_ascii=False,
                        ),
                        1,
                    ),
                    (
                        59,
                        "catalog-key-59",
                        "190106",
                        "Конфірмат (стяжка) оцинков. 7,0х50 мм під шестигранник",
                        "viyar",
                        1.14,
                        "UAH",
                        "шт",
                        "В наявності",
                        "https://viyar.ua/ua/catalog/konfirmat-7x50/",
                        None,
                        None,
                        json.dumps(
                            {
                                "source_site": "viyar",
                                "source_url": "https://viyar.ua/ua/catalog/konfirmat-7x50/",
                                "parsed_item": {"article": "190106"},
                            },
                            ensure_ascii=False,
                        ),
                        1,
                    ),
                ],
            )
            connection.execute("INSERT INTO mounting_node_items DEFAULT VALUES")
            connection.execute("INSERT INTO fitting_hole_templates DEFAULT VALUES")
            connection.execute("INSERT INTO fitting_images DEFAULT VALUES")
            connection.commit()

    @staticmethod
    def _load_fittings(connection: sqlite3.Connection) -> list[tuple]:
        return connection.execute(
            "SELECT id, catalog_key, article, name, source, price, currency, unit, stock, source_url, parsed_at, price_updated_at, source_payload_json, is_active FROM fittings ORDER BY id"
        ).fetchall()

    @staticmethod
    def _load_offers(connection: sqlite3.Connection) -> list[dict[str, object]]:
        rows = connection.execute(
            """
            SELECT
                offer.fitting_id,
                supplier.code AS supplier_code,
                offer.article,
                offer.external_product_id,
                offer.source_url,
                offer.price,
                offer.currency,
                offer.unit,
                offer.stock,
                offer.is_active,
                offer.priority,
                offer.parsed_at,
                offer.price_updated_at,
                offer.source_payload_json,
                CASE
                    WHEN offer.source_payload_json IS NULL OR trim(offer.source_payload_json) = '' THEN 'null'
                    ELSE 'present'
                END AS payload
            FROM fitting_supplier_offers offer
            JOIN suppliers supplier ON supplier.id = offer.supplier_id
            ORDER BY offer.fitting_id, offer.id
            """
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _counts_snapshot(connection: sqlite3.Connection) -> dict[str, int]:
        return {
            table_name: int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
            for table_name in (
                "fittings",
                "suppliers",
                "fitting_supplier_offers",
                "mounting_node_items",
                "fitting_hole_templates",
                "fitting_images",
            )
        }

    @staticmethod
    def _count(connection: sqlite3.Connection, table_name: str) -> int:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
