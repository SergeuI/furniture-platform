from __future__ import annotations

import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from database.repositories.edge_foundation_repository import EdgeFoundationRepository
from scripts import upgrade_edge_foundation_schema as migration
from services.edge_foundation_persistence_service import EdgeFoundationPersistenceService


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


if __name__ == "__main__":
    unittest.main()
