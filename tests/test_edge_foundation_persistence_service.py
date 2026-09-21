from __future__ import annotations

import copy
import asyncio
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.repositories.edge_foundation_repository import EdgeFoundationRepository
from database.models.hole_library import HoleLibraryTypeModel  # noqa: F401
from scripts import upgrade_edge_foundation_schema as migration
from database.edge_lifecycle_schema import ensure_edge_lifecycle_schema
import services.edge_foundation_persistence_service as persistence_module
from services.edge_foundation_persistence_service import EdgeFoundationPersistenceService
from services.material_manufacturer_rules import MISSING_MANUFACTURER_NAME


def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def _edge_preview_item(
    *,
    source_url: str,
    manufacturer_article: str,
    supplier_code: str,
    supplier_article: str,
    name: str,
    width_mm: float | None,
    thickness_mm: float | None,
    price: float,
    availability: str,
    image_url: str | None = None,
    technology_code: str | None = None,
    unit: str = "м.п.",
) -> dict:
    return {
        "status": "parsed",
        "discovered_card": {
            "article": manufacturer_article,
            "name": name,
            "source_url": source_url,
            "image_url": image_url,
            "source": "viyar",
        },
        "canonical_candidate": {
            "manufacturer": "Rehau",
            "manufacturer_article": manufacturer_article,
            "name": name,
            "decor_code": None,
            "color": "Смарагд зелений",
            "material_type": "ABS",
            "technology_code": technology_code,
            "width_mm": width_mm,
            "thickness_mm": thickness_mm,
            "finish": "Без напрямку",
            "image_url": image_url,
        },
        "supplier_offer_candidate": {
            "supplier": supplier_code,
            "article": supplier_article,
            "external_product_id": None,
            "source_url": source_url,
            "unit": unit,
            "availability": availability,
            "price": price,
            "currency": "UAH",
            "package_length": "300 м.п.",
            "source_payload": {
                "title": name,
                "brand": "Rehau",
                "characteristics": {
                    "Тип товару": "ABS",
                    "Ширина": f"{width_mm} мм" if width_mm is not None else None,
                    "Товщина": f"{thickness_mm} мм" if thickness_mm is not None else None,
                },
                "image_url": image_url,
                "price_text": f"{price} UAH / {unit}",
            },
        },
        "raw_characteristics": {
            "Тип товару": "ABS",
            "Ширина": f"{width_mm} мм" if width_mm is not None else None,
            "Товщина": f"{thickness_mm} мм" if thickness_mm is not None else None,
        },
    }


class EdgeFoundationPersistenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database_path = Path(self._tmpdir.name) / "edges.db"

        with sqlite3.connect(self.database_path) as connection:
            connection.executescript(
                """
                CREATE TABLE materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT NOT NULL UNIQUE,
                    name TEXT
                );
                CREATE TABLE material_manufacturers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL UNIQUE,
                    code TEXT,
                    website_url TEXT,
                    logo_url TEXT,
                    owner_user_id TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_system BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL
                );
                INSERT INTO materials (article, name) VALUES ('K520', 'K520 PD');
                INSERT INTO material_manufacturers (name, normalized_name) VALUES ('Rehau', 'rehau');
                INSERT INTO suppliers (code, name) VALUES ('viyar', 'VIYAR');
                INSERT INTO suppliers (code, name) VALUES ('kronas', 'KRONAS');
                """
            )
            migration.ensure_edge_foundation_schema(connection)
            ensure_edge_lifecycle_schema(connection)

        self.engine = create_engine(
            f"sqlite:///{self.database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        event.listen(self.engine, "connect", _enable_foreign_keys)
        self.session_maker = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def tearDown(self) -> None:
        self.engine.dispose()
        self._tmpdir.cleanup()

    def _counts(self, session) -> dict[str, int]:
        return {
            "canonical_edges": session.execute(text("SELECT COUNT(*) FROM canonical_edges")).fetchone()[0],
            "edge_supplier_offers": session.execute(text("SELECT COUNT(*) FROM edge_supplier_offers")).fetchone()[0],
            "material_edge_relations": session.execute(text("SELECT COUNT(*) FROM material_edge_relations")).fetchone()[0],
            "edge_supplier_offer_prices": session.execute(text("SELECT COUNT(*) FROM edge_supplier_offer_prices")).fetchone()[0],
        }

    def test_canonical_preflight_isolates_local_conflict(self) -> None:
        session = self.session_maker()
        try:
            first = _edge_preview_item(
                source_url="https://viyar.ua/first",
                manufacturer_article="6240",
                supplier_code="viyar",
                supplier_article="23651",
                name="First",
                width_mm=22.0,
                thickness_mm=0.4,
                price=10.0,
                availability="В наявності",
            )
            second = copy.deepcopy(first)
            second["supplier_offer_candidate"]["article"] = "87189"
            second["canonical_candidate"]["color"] = "Інший колір"
            clean = _edge_preview_item(
                source_url="https://viyar.ua/clean",
                manufacturer_article="6240",
                supplier_code="viyar",
                supplier_article="clean",
                name="Clean",
                width_mm=23.0,
                thickness_mm=0.8,
                price=10.0,
                availability="В наявності",
            )

            service = EdgeFoundationPersistenceService(session=session)
            result = service.preflight_preview_result(
                material_id=1,
                preview_result={"items": [first, second, clean]},
                request_id="preflight-test",
            )

            self.assertTrue(result["success"])
            self.assertEqual(
                [item["status"] for item in result["items"]],
                ["needs_review", "needs_review", "parsed"],
            )
            self.assertEqual(len(result["ready_items"]), 1)
            self.assertEqual(self._counts(session), {
                "canonical_edges": 0,
                "edge_supplier_offers": 0,
                "material_edge_relations": 0,
                "edge_supplier_offer_prices": 0,
            })
        finally:
            session.close()

    def _base_preview_result(self) -> dict:
        name = "141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU"
        return {
            "success": True,
            "items": [
                _edge_preview_item(
                    source_url="https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                    manufacturer_article="141342",
                    supplier_code="viyar",
                    supplier_article="185187",
                    name=name,
                    width_mm=22.0,
                    thickness_mm=0.4,
                    price=19.26,
                    availability="Скоро у продажу",
                    image_url="https://viyar.ua/store/Items/photos/ph185187.jpg",
                ),
                _edge_preview_item(
                    source_url="https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh0_8mm_150_m_p_rehau/",
                    manufacturer_article="141342",
                    supplier_code="viyar",
                    supplier_article="152444",
                    name="141342 Kromka ABS Izumrud Zelenyy 23x0,8mm 150 m.p. REHAU",
                    width_mm=23.0,
                    thickness_mm=0.8,
                    price=17.10,
                    availability="В наявності",
                    image_url="https://viyar.ua/store/Items/photos/ph152444.jpg",
                ),
                _edge_preview_item(
                    source_url="https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh2mm_100_m_p_rehau/",
                    manufacturer_article="141342",
                    supplier_code="viyar",
                    supplier_article="152482",
                    name="141342 Kromka ABS Izumrud Zelenyy 23x2mm 100 m.p. REHAU",
                    width_mm=23.0,
                    thickness_mm=2.0,
                    price=18.20,
                    availability="В наявності",
                    image_url="https://viyar.ua/store/Items/photos/ph152482.jpg",
                ),
                _edge_preview_item(
                    source_url="https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_43kh2mm_100_m_p_rehau/",
                    manufacturer_article="141342",
                    supplier_code="viyar",
                    supplier_article="152565",
                    name="141342 Kromka ABS Izumrud Zelenyy 43x2mm 100 m.p. REHAU",
                    width_mm=43.0,
                    thickness_mm=2.0,
                    price=24.50,
                    availability="В наявності",
                    image_url="https://viyar.ua/store/Items/photos/ph152565.jpg",
                ),
            ],
        }

    def test_manufacturer_lookup_is_normalized_and_case_insensitive(self) -> None:
        session = self.session_maker()
        try:
            repository = EdgeFoundationRepository(session)
            manufacturer = repository.get_manufacturer_by_name("REHAU")
            self.assertIsNotNone(manufacturer)
            self.assertEqual(manufacturer.id, 1)
        finally:
            session.close()

    def test_true_source_missing_manufacturer_uses_system_sentinel(self) -> None:
        session = self.session_maker()
        try:
            session.execute(text(
                "INSERT INTO material_manufacturers "
                "(name, normalized_name, code, owner_user_id, is_active, is_system) "
                "VALUES (:name, :normalized, 'manufacturer_not_specified', NULL, 1, 1)"
            ), {"name": MISSING_MANUFACTURER_NAME, "normalized": MISSING_MANUFACTURER_NAME.casefold()})
            session.commit()
            item = self._base_preview_result()["items"][0]
            item["canonical_candidate"] = dict(item["canonical_candidate"])
            item["canonical_candidate"]["manufacturer"] = MISSING_MANUFACTURER_NAME

            result = EdgeFoundationPersistenceService(session=session).persist_preview_item(
                material_id=1,
                preview_item=item,
                city=None,
            )

            self.assertEqual(result["status"], "persisted")
            self.assertNotEqual(result["manufacturer_id"], 1)
        finally:
            session.close()

    def test_true_source_missing_manufacturer_is_ready_in_preflight(self) -> None:
        session = self.session_maker()
        try:
            session.execute(text(
                "INSERT INTO material_manufacturers "
                "(name, normalized_name, code, owner_user_id, is_active, is_system) "
                "VALUES (:name, :normalized, 'manufacturer_not_specified', NULL, 1, 1)"
            ), {"name": MISSING_MANUFACTURER_NAME, "normalized": MISSING_MANUFACTURER_NAME.casefold()})
            session.commit()
            item = copy.deepcopy(self._base_preview_result()["items"][0])
            item["canonical_candidate"]["manufacturer"] = MISSING_MANUFACTURER_NAME

            result = EdgeFoundationPersistenceService(session=session).preflight_preview_result(
                material_id=1,
                preview_result={"items": [item]},
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["items"][0]["status"], "parsed")
            self.assertEqual(len(result["ready_items"]), 1)
        finally:
            session.close()

    def test_unknown_named_manufacturer_does_not_use_missing_sentinel(self) -> None:
        session = self.session_maker()
        try:
            item = copy.deepcopy(self._base_preview_result()["items"][0])
            item["canonical_candidate"]["manufacturer"] = "Unknown Real Brand"

            result = EdgeFoundationPersistenceService(session=session).preflight_preview_result(
                material_id=1,
                preview_result={"items": [item]},
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["items"][0]["status"], "needs_review")
            self.assertEqual(result["items"][0]["reason"], "manufacturer_not_found:Unknown Real Brand")
        finally:
            session.close()

    def test_supplier_model_is_registered_for_edge_offer_foreign_key(self) -> None:
        self.assertIn("suppliers", Base.metadata.tables)

    def test_material_import_caller_uses_atomic_persistence(self) -> None:
        preview = self._base_preview_result()
        fake_service = Mock()
        fake_service.persist_preview_result.return_value = {
            "success": True,
            "items": [],
            "counts": {"items": 4, "persisted": 4, "reused": 0, "needs_review": 0, "failed": 0},
        }

        async def preview_runner(**kwargs):
            return preview

        async def run():
            with patch.object(persistence_module, "EdgeFoundationPersistenceService", return_value=fake_service):
                return await persistence_module.persist_viyar_recommended_edges_for_material_import(
                    material_id=2093,
                    material_source_url="https://viyar.ua/ua/catalog/material/",
                    selected_city="kyiv",
                    preview_runner=preview_runner,
                )

        asyncio.run(run())
        fake_service.persist_preview_result.assert_called_once()
        self.assertTrue(fake_service.persist_preview_result.call_args.kwargs["atomic"])

    def test_partial_preview_persists_only_parsed_items_and_returns_warnings(self) -> None:
        preview = self._base_preview_result()
        preview["items"][1]["status"] = "failed"
        preview["items"][1]["error"] = "Edge detail page could not be fetched"
        preview["items"][2]["status"] = "needs_review"
        preview["items"][2]["reason"] = "missing_identity_fields"
        preview["items"][2]["missing_fields"] = ["width_mm"]
        fake_service = Mock()
        fake_service.persist_preview_result.return_value = {
            "success": True,
            "items": [],
            "counts": {"persisted": 2, "reused": 0, "needs_review": 0, "failed": 0},
        }

        async def preview_runner(**kwargs):
            return preview

        async def run():
            with patch.object(persistence_module, "EdgeFoundationPersistenceService", return_value=fake_service):
                return await persistence_module.persist_viyar_recommended_edges_for_material_import(
                    material_id=2093,
                    material_source_url="https://viyar.ua/ua/catalog/material/",
                    selected_city="kyiv",
                    preview_runner=preview_runner,
                )

        result = asyncio.run(run())

        fake_service.persist_preview_result.assert_called_once()
        persistence_input = fake_service.persist_preview_result.call_args.kwargs["preview_result"]["items"]
        self.assertEqual(len(persistence_input), 2)
        self.assertTrue(result["success"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["summary"], {
            "total": 4,
            "result_count": 4,
            "parsed": 2,
            "discovered": 4,
            "persisted": 2,
            "needs_review": 1,
            "failed": 1,
            "status": "completed_with_warnings",
            "reason": None,
        })
        self.assertEqual(result["review_items"], [
            {
                "article": "141342",
                "source_url": "https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh2mm_100_m_p_rehau/",
                "reason": "missing_identity_fields",
                "missing_fields": ["width_mm"],
            }
        ])

    def test_result_count_invariant_skips_persistence(self) -> None:
        preview = self._base_preview_result()
        preview["recommended_edges_count"] = 24
        fake_service = Mock()

        async def preview_runner(**kwargs):
            return preview

        async def run():
            with patch.object(persistence_module, "EdgeFoundationPersistenceService", return_value=fake_service):
                return await persistence_module.persist_viyar_recommended_edges_for_material_import(
                    material_id=2093,
                    material_source_url="https://viyar.ua/ua/catalog/material/",
                    preview_runner=preview_runner,
                )

        result = asyncio.run(run())

        fake_service.persist_preview_result.assert_not_called()
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "preview_result_incomplete")
        self.assertEqual(result["summary"]["total"], 24)
        self.assertEqual(result["summary"]["result_count"], 4)
        self.assertEqual(result["summary"]["reason"], "preview_result_incomplete")

    def test_thirty_candidate_preview_persists_exactly_twenty_eight_parsed_items(self) -> None:
        preview = self._base_preview_result()
        source_items = preview["items"]
        preview["items"] = []
        for index in range(30):
            item = copy.deepcopy(source_items[index % len(source_items)])
            item["candidate_index"] = index
            item["canonical_candidate"]["manufacturer_article"] = f"CAN-{index}"
            item["supplier_offer_candidate"]["article"] = f"SUP-{index}"
            if index == 28:
                item["status"] = "failed"
                item["reason"] = "network_timeout"
            elif index == 29:
                item["status"] = "needs_review"
                item["reason"] = "identity_uncertain"
            preview["items"].append(item)
        preview["recommended_edges_count"] = 30
        fake_service = Mock()
        fake_service.persist_preview_result.return_value = {
            "success": True,
            "items": [],
            "counts": {"persisted": 28, "reused": 0, "needs_review": 0, "failed": 0},
        }

        async def preview_runner(**kwargs):
            return preview

        async def run():
            with patch.object(persistence_module, "EdgeFoundationPersistenceService", return_value=fake_service):
                return await persistence_module.persist_viyar_recommended_edges_for_material_import(
                    material_id=2093,
                    material_source_url="https://viyar.ua/ua/catalog/material/",
                    preview_runner=preview_runner,
                )

        result = asyncio.run(run())
        persistence_items = fake_service.persist_preview_result.call_args.kwargs["preview_result"]["items"]
        self.assertEqual(len(persistence_items), 28)
        self.assertTrue(all(item["status"] == "parsed" for item in persistence_items))
        self.assertEqual(result["summary"]["status"], "completed_with_warnings")
        self.assertEqual(result["summary"]["persisted"], 28)
        self.assertEqual(result["summary"]["failed"], 1)
        self.assertEqual(result["summary"]["needs_review"], 1)

    def test_zero_parsed_items_skip_persistence(self) -> None:
        preview = self._base_preview_result()
        for item in preview["items"]:
            item["status"] = "failed"
        fake_service = Mock()

        async def preview_runner(**kwargs):
            return preview

        async def run():
            with patch.object(persistence_module, "EdgeFoundationPersistenceService", return_value=fake_service):
                return await persistence_module.persist_viyar_recommended_edges_for_material_import(
                    material_id=2093,
                    material_source_url="https://viyar.ua/ua/catalog/material/",
                    preview_runner=preview_runner,
                )

        result = asyncio.run(run())
        fake_service.persist_preview_result.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["summary"]["status"], "no_valid_recommended_edges")
        self.assertEqual(result["summary"]["persisted"], 0)

    def test_persists_four_edges_idempotently_without_city_prices(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            preview_result = self._base_preview_result()

            first = service.persist_preview_result(material_id=1, preview_result=preview_result, city=None)
            self.assertEqual(first["counts"], {"items": 4, "persisted": 4, "reused": 0, "needs_review": 0, "failed": 0})
            self.assertEqual(self._counts(session), {
                "canonical_edges": 4,
                "edge_supplier_offers": 4,
                "material_edge_relations": 4,
                "edge_supplier_offer_prices": 0,
            })

            second = service.persist_preview_result(material_id=1, preview_result=preview_result, city=None)
            self.assertEqual(second["counts"], {"items": 4, "persisted": 0, "reused": 4, "needs_review": 0, "failed": 0})
            self.assertEqual(self._counts(session), {
                "canonical_edges": 4,
                "edge_supplier_offers": 4,
                "material_edge_relations": 4,
                "edge_supplier_offer_prices": 0,
            })
        finally:
            session.close()

    def test_persists_city_prices_only_with_explicit_city(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            result = service.persist_preview_result(
                material_id=1,
                preview_result=self._base_preview_result(),
                city="kyiv",
            )
            self.assertEqual(result["counts"]["persisted"], 4)
            self.assertEqual(self._counts(session), {
                "canonical_edges": 4,
                "edge_supplier_offers": 4,
                "material_edge_relations": 4,
                "edge_supplier_offer_prices": 4,
            })
            price_rows = session.execute(
                text("SELECT city, price, currency, availability FROM edge_supplier_offer_prices ORDER BY id")
            ).fetchall()
            self.assertTrue(all(row[0] == "kyiv" for row in price_rows))
            self.assertEqual([row[1] for row in price_rows], [19.26, 17.10, 18.20, 24.50])
        finally:
            session.close()

    def test_same_canonical_edge_can_have_viyar_and_kronas_offers(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            name = "141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU"
            viyar_item = _edge_preview_item(
                source_url="https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                manufacturer_article="141342",
                supplier_code="viyar",
                supplier_article="185187",
                name=name,
                width_mm=22.0,
                thickness_mm=0.4,
                price=19.26,
                availability="Скоро у продажу",
                image_url="https://viyar.ua/store/Items/photos/ph185187.jpg",
            )
            kronas_item = copy.deepcopy(viyar_item)
            kronas_item["supplier_offer_candidate"] = dict(kronas_item["supplier_offer_candidate"])
            kronas_item["supplier_offer_candidate"]["supplier"] = "kronas"
            kronas_item["supplier_offer_candidate"]["article"] = "KR-141342"
            kronas_item["supplier_offer_candidate"]["source_url"] = "https://kronas.ua/catalog/141342/"

            first = service.persist_preview_item(material_id=1, preview_item=viyar_item, city=None)
            second = service.persist_preview_item(material_id=1, preview_item=kronas_item, city=None)

            self.assertEqual(first["status"], "persisted")
            self.assertEqual(second["status"], "persisted")
            self.assertEqual(self._counts(session), {
                "canonical_edges": 1,
                "edge_supplier_offers": 2,
                "material_edge_relations": 2,
                "edge_supplier_offer_prices": 0,
            })
        finally:
            session.close()

    def test_persists_edge_without_image_url_when_identity_fields_are_present(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            item = _edge_preview_item(
                source_url="https://viyar.ua/ua/catalog/2941w_kromka_abs_piniya_temno_korichnevaya_23kh0_8mm_150_m_p_rehau/",
                manufacturer_article="2941W",
                supplier_code="viyar",
                supplier_article="152446",
                name="2941W Крайка ABS Пінія темно-коричнева 23x0,8мм (150 м.п.) REHAU",
                width_mm=23.0,
                thickness_mm=0.8,
                price=12.34,
                availability="В наявності",
                image_url=None,
            )

            result = service.persist_preview_item(material_id=1, preview_item=item, city=None)

            self.assertEqual(result["status"], "persisted")
            self.assertEqual(self._counts(session), {
                "canonical_edges": 1,
                "edge_supplier_offers": 1,
                "material_edge_relations": 1,
                "edge_supplier_offer_prices": 0,
            })
        finally:
            session.close()

    def test_persists_catalog_edges_without_material_relations(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            preview_result = {
                "success": True,
                "items": [
                    _edge_preview_item(
                        source_url="https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                        manufacturer_article="141342",
                        supplier_code="viyar",
                        supplier_article="185187",
                        name="141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU",
                        width_mm=22.0,
                        thickness_mm=0.4,
                        price=19.26,
                        availability="Скоро у продажу",
                        image_url="https://viyar.ua/store/Items/photos/ph185187.jpg",
                    )
                ],
            }

            result = service.persist_preview_result_for_catalog(preview_result=preview_result, city="kyiv")

            self.assertEqual(result["counts"], {"items": 1, "persisted": 1, "reused": 0, "needs_review": 0, "failed": 0})
            self.assertEqual(self._counts(session), {
                "canonical_edges": 1,
                "edge_supplier_offers": 1,
                "material_edge_relations": 0,
                "edge_supplier_offer_prices": 1,
            })
        finally:
            session.close()

    def test_missing_identity_fields_return_needs_review_and_do_not_block_valid_items(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            preview_result = self._base_preview_result()
            preview_result["items"][1]["canonical_candidate"]["width_mm"] = None

            result = service.persist_preview_result(material_id=1, preview_result=preview_result, city=None)
            statuses = [item["status"] for item in result["items"]]
            self.assertEqual(statuses.count("needs_review"), 1)
            self.assertEqual(result["items"][1]["reason"], "missing_identity_fields")
            self.assertEqual(result["items"][1]["missing_fields"], ["width_mm"])
            self.assertEqual(self._counts(session), {
                "canonical_edges": 3,
                "edge_supplier_offers": 3,
                "material_edge_relations": 3,
                "edge_supplier_offer_prices": 0,
            })
        finally:
            session.close()

    def test_missing_manufacturer_returns_needs_review(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            item = self._base_preview_result()["items"][0]
            item["canonical_candidate"] = dict(item["canonical_candidate"])
            item["canonical_candidate"]["manufacturer"] = None
            result = service.persist_preview_item(material_id=1, preview_item=item, city=None)

            self.assertEqual(result["status"], "needs_review")
            self.assertEqual(result["reason"], "missing_identity_fields")
            self.assertEqual(result["missing_fields"], ["manufacturer"])
            self.assertEqual(self._counts(session), {
                "canonical_edges": 0,
                "edge_supplier_offers": 0,
                "material_edge_relations": 0,
                "edge_supplier_offer_prices": 0,
            })
        finally:
            session.close()

    def test_missing_thickness_returns_needs_review(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            item = self._base_preview_result()["items"][0]
            item["canonical_candidate"] = dict(item["canonical_candidate"])
            item["canonical_candidate"]["thickness_mm"] = None
            result = service.persist_preview_item(material_id=1, preview_item=item, city=None)

            self.assertEqual(result["status"], "needs_review")
            self.assertEqual(result["reason"], "missing_identity_fields")
            self.assertEqual(result["missing_fields"], ["thickness_mm"])
        finally:
            session.close()

    def test_atomic_valid_batch_persists_as_one_batch(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            result = service.persist_preview_result(
                material_id=1,
                preview_result=self._base_preview_result(),
                city="kyiv",
                atomic=True,
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "batch_persisted")
            self.assertEqual(result["counts"]["persisted"], 4)
            self.assertFalse(result["rollback_performed"])
            self.assertEqual(self._counts(session), {
                "canonical_edges": 4,
                "edge_supplier_offers": 4,
                "material_edge_relations": 4,
                "edge_supplier_offer_prices": 4,
            })
        finally:
            session.close()

    def test_atomic_validation_failure_writes_zero_rows(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            preview = self._base_preview_result()
            preview["items"][0] = copy.deepcopy(preview["items"][0])
            preview["items"][0]["canonical_candidate"]["manufacturer"] = "Missing Manufacturer"

            result = service.persist_preview_result(
                material_id=1,
                preview_result=preview,
                atomic=True,
            )

            self.assertFalse(result["success"])
            self.assertEqual(result["status"], "batch_failed")
            self.assertTrue(result["rollback_performed"])
            self.assertEqual(result["persisted_count"], 0)
            self.assertEqual(self._counts(session), {
                "canonical_edges": 0,
                "edge_supplier_offers": 0,
                "material_edge_relations": 0,
                "edge_supplier_offer_prices": 0,
            })
        finally:
            session.close()

    def test_true_duplicate_full_identity_normalizes(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            preview = self._base_preview_result()
            preview["items"][1] = copy.deepcopy(preview["items"][0])
            preview["items"][1]["supplier_offer_candidate"]["article"] = "duplicate-supplier-article"
            preview["items"][1]["supplier_offer_candidate"]["source_url"] += "?duplicate=1"

            result = service.persist_preview_result(
                material_id=1,
                preview_result=preview,
                atomic=True,
                request_id="diagnostic-duplicate-test",
            )

            self.assertTrue(result["success"])
            self.assertEqual(self._counts(session)["canonical_edges"], 3)
            self.assertEqual(self._counts(session)["material_edge_relations"], 3)
            self.assertEqual(self._counts(session)["edge_supplier_offers"], 4)
        finally:
            session.close()

    def test_standard_and_laser_same_article_are_separate_edges(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            preview = self._base_preview_result()
            first = copy.deepcopy(preview["items"][0])
            second = copy.deepcopy(first)
            first["canonical_candidate"]["technology_code"] = "standard_abs"
            second["canonical_candidate"]["technology_code"] = "laser_abs_pro"
            second["supplier_offer_candidate"]["article"] = "36602"
            second["supplier_offer_candidate"]["source_url"] += "?laser=1"
            preview["items"] = [first, second]

            result = service.persist_preview_result(material_id=1, preview_result=preview, atomic=True)

            self.assertTrue(result["success"])
            self.assertEqual(self._counts(session)["canonical_edges"], 2)
            self.assertEqual(self._counts(session)["material_edge_relations"], 2)
            self.assertEqual(
                session.execute(text("SELECT technology_code FROM canonical_edges ORDER BY id")).scalars().all(),
                ["standard_abs", "laser_abs_pro"],
            )
        finally:
            session.close()

    def test_unique_identities_do_not_create_duplicate_diagnostic(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            result = service.persist_preview_result(
                material_id=1,
                preview_result=self._base_preview_result(),
                atomic=True,
                request_id="diagnostic-unique-test",
            )

            self.assertTrue(result["success"])
            self.assertIsNone(result.get("diagnostic_snapshot_path"))
        finally:
            session.close()

    def test_duplicate_snapshot_excludes_sensitive_fields_and_keeps_zero_partial_writes(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            preview = self._base_preview_result()
            preview["items"][1] = copy.deepcopy(preview["items"][0])
            preview["items"][1]["supplier_offer_candidate"]["article"] = "duplicate-supplier-article"
            preview["items"][1]["supplier_offer_candidate"]["source_payload"] = {
                "cookie": "must-not-be-captured",
                "password": "must-not-be-captured",
            }
            preview["items"][1]["canonical_candidate"]["color"] = "incompatible-color"

            result = service.persist_preview_result(
                material_id=1,
                preview_result=preview,
                atomic=True,
                request_id="diagnostic-sensitive-test",
            )
            self.assertEqual(result["reason"], "duplicate_canonical_identity_conflict")
            with open(result["diagnostic_snapshot_path"], encoding="utf-8") as snapshot_file:
                snapshot_text = snapshot_file.read().lower()

            self.assertNotIn("must-not-be-captured", snapshot_text)
            self.assertNotIn("cookie", snapshot_text)
            self.assertNotIn("password", snapshot_text)
            self.assertEqual(result["persisted_count"], 0)
            self.assertTrue(result["rollback_performed"])
            self.assertEqual(self._counts(session), {
                "canonical_edges": 0,
                "edge_supplier_offers": 0,
                "material_edge_relations": 0,
                "edge_supplier_offer_prices": 0,
            })
        finally:
            session.close()

    def test_atomic_mid_write_exception_rolls_back_complete_batch(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            original = service.persist_preview_item
            calls = 0

            def fail_on_third(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise RuntimeError("forced atomic failure")
                return original(*args, **kwargs)

            service.persist_preview_item = fail_on_third
            result = service.persist_preview_result(
                material_id=1,
                preview_result=self._base_preview_result(),
                atomic=True,
            )

            self.assertFalse(result["success"])
            self.assertEqual(result["status"], "batch_failed")
            self.assertEqual(result["reason"], "forced atomic failure")
            self.assertEqual(result["exception_type"], "RuntimeError")
            self.assertEqual(result["failed_index"], 3)
            self.assertEqual(result["failed_supplier_article"], "152482")
            self.assertEqual(result["failed_manufacturer_article"], "141342")
            self.assertEqual(result["failed_phase"], "unknown")
            self.assertTrue(result["rollback_performed"])
            self.assertEqual(result["persisted_count"], 0)
            self.assertEqual(self._counts(session), {
                "canonical_edges": 0,
                "edge_supplier_offers": 0,
                "material_edge_relations": 0,
                "edge_supplier_offer_prices": 0,
            })
        finally:
            session.close()

    def test_atomic_reuses_existing_edge_and_is_idempotent_on_retry(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            preview = self._base_preview_result()
            first = service.persist_preview_result(material_id=1, preview_result=preview, atomic=True)
            second = service.persist_preview_result(material_id=1, preview_result=preview, atomic=True)

            self.assertEqual(first["counts"]["persisted"], 4)
            self.assertEqual(second["counts"]["reused"], 4)
            self.assertEqual(self._counts(session), {
                "canonical_edges": 4,
                "edge_supplier_offers": 4,
                "material_edge_relations": 4,
                "edge_supplier_offer_prices": 0,
            })
        finally:
            session.close()

    def test_atomic_identity_conflict_writes_zero_rows(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            existing = self._base_preview_result()["items"][0]
            service.persist_preview_item(material_id=1, preview_item=existing)
            session.commit()
            before = self._counts(session)
            session.rollback()

            conflicting = copy.deepcopy(self._base_preview_result())
            conflicting["items"][0]["canonical_candidate"]["width_mm"] = 23.0
            result = service.persist_preview_result(
                material_id=1,
                preview_result=conflicting,
                atomic=True,
            )

            self.assertFalse(result["success"])
            self.assertIn("canonical_identity_conflict", result["reason"])
            self.assertTrue(result["rollback_performed"])
            self.assertEqual(self._counts(session), before)
        finally:
            session.close()

    def test_atomic_false_preserves_legacy_partial_behavior(self) -> None:
        session = self.session_maker()
        try:
            service = EdgeFoundationPersistenceService(session=session)
            preview = self._base_preview_result()
            preview["items"][1] = copy.deepcopy(preview["items"][1])
            preview["items"][1]["canonical_candidate"]["width_mm"] = None

            result = service.persist_preview_result(
                material_id=1,
                preview_result=preview,
                atomic=False,
            )

            self.assertEqual(result["counts"]["needs_review"], 1)
            self.assertEqual(result["counts"]["persisted"], 3)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
