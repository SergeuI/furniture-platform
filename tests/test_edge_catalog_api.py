from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from api.routes import catalog
from database.base import Base
from database.models.canonical_edge import (
    CanonicalEdgeModel,
    EdgeSupplierOfferModel,
    EdgeSupplierOfferPriceModel,
    MaterialEdgeRelationModel,
)
from database.models.fitting import SupplierModel
from database.models.material import MaterialModel
from database.models.material_taxonomy import MaterialManufacturerModel
from database.models.service_drilling_rule import ServiceDrillingRuleModel
from services import upload_service


def _make_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (1, 1), (255, 0, 0, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@dataclass
class UserStub:
    id: str
    email: str
    role: str
    city: str = "kyiv"


class EdgeCatalogApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(self.engine, "connect", _enable_foreign_keys)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.session = self.Session()

        manufacturer = MaterialManufacturerModel(
            name="REHAU",
            normalized_name="rehau",
            code="rehau",
            logo_url="https://example.com/rehau.png",
            is_active=True,
            is_system=True,
        )
        supplier_viyar = SupplierModel(
            code="viyar",
            name="VIYAR",
            logo_url="https://example.com/viyar.png",
            is_active=True,
            is_system=True,
        )
        supplier_kronas = SupplierModel(
            code="kronas",
            name="KRONAS",
            logo_url="https://example.com/kronas.png",
            is_active=True,
            is_system=True,
        )
        self.session.add_all([manufacturer, supplier_viyar, supplier_kronas])
        self.session.flush()
        self.manufacturer_id = manufacturer.id
        self.supplier_viyar_id = supplier_viyar.id
        self.supplier_kronas_id = supplier_kronas.id

        material = MaterialModel(
            article="M-001",
            name="Material 1",
        )
        self.session.add(material)
        self.session.flush()
        self.material_id = material.id

        edge = CanonicalEdgeModel(
            manufacturer_id=manufacturer.id,
            manufacturer_article="2941W",
            name="2941W Крайка ABS Пінія темно-коричнева 23х0,8мм (150 м.п.) REHAU",
            color="H (Деревоподібні)",
            material_type="ABS",
            width_mm=23.0,
            thickness_mm=0.8,
            image_url="https://example.com/edge.jpg",
            is_active=True,
        )
        self.session.add(edge)
        self.session.flush()
        self.existing_edge_id = edge.id

        offer_viyar = EdgeSupplierOfferModel(
            edge_id=edge.id,
            supplier_id=supplier_viyar.id,
            article="152446",
            source_url="https://example.com/viyar/2941w",
            unit="м.п.",
            is_active=True,
            priority=0,
        )
        offer_kronas = EdgeSupplierOfferModel(
            edge_id=edge.id,
            supplier_id=supplier_kronas.id,
            article="K-152446",
            source_url="https://example.com/kronas/2941w",
            unit="м.п.",
            is_active=True,
            priority=1,
        )
        self.session.add_all([offer_viyar, offer_kronas])
        self.session.flush()

        self.session.add_all([
            EdgeSupplierOfferPriceModel(
                offer_id=offer_viyar.id,
                city="Kyiv",
                price=11.5,
                currency="UAH",
                availability="in_stock",
            ),
            EdgeSupplierOfferPriceModel(
                offer_id=offer_kronas.id,
                city="Kyiv",
                price=12.25,
                currency="UAH",
                availability="in_stock",
            ),
        ])
        self.session.commit()

        self._original_session_local = catalog.SessionLocal
        self._original_feature_access = catalog._ensure_material_feature_access
        catalog.SessionLocal = self.Session
        catalog._ensure_material_feature_access = lambda *args, **kwargs: None

    def tearDown(self) -> None:
        catalog.SessionLocal = self._original_session_local
        catalog._ensure_material_feature_access = self._original_feature_access
        self.session.close()
        self.engine.dispose()

    def _build_app(self) -> FastAPI:
        app = FastAPI()
        app.include_router(catalog.router, prefix="/catalog")
        app.dependency_overrides[catalog.require_catalog_reader] = lambda: UserStub(
            id="user-1",
            email="admin@example.com",
            role="admin",
        )
        return app

    def test_list_edges_returns_one_canonical_card_with_supplier_summary(self) -> None:
        app = self._build_app()

        with TestClient(app) as client:
            response = client.get("/catalog/edges")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["success"])
            self.assertEqual(len(payload["items"]), 1)

            item = payload["items"][0]
            self.assertEqual(item["manufacturer_name"], "REHAU")
            self.assertEqual(item["manufacturer_logo_url"], "https://example.com/rehau.png")
            self.assertEqual(item["manufacturer_article"], "2941W")
            self.assertEqual(item["name"], "2941W Крайка ABS Пінія темно-коричнева 23х0,8мм (150 м.п.) REHAU")
            self.assertEqual(len(item["supplier_summary"]), 2)
            self.assertEqual(len(item["supplier_offers"]), 2)
            self.assertEqual(len(item["price_summary"]), 1)
            self.assertEqual(item["price_summary"][0]["min_price"], 11.5)
            self.assertEqual(item["price_summary"][0]["max_price"], 12.25)
            self.assertEqual(item["price_summary"][0]["offer_count"], 2)

            supplier_filtered = client.get(f"/catalog/edges?supplier_id={item['supplier_offers'][0]['supplier_id']}")
            self.assertEqual(supplier_filtered.status_code, 200)
            supplier_payload = supplier_filtered.json()
            self.assertTrue(supplier_payload["success"])
            self.assertEqual(len(supplier_payload["items"]), 1)
            self.assertEqual(supplier_payload["items"][0]["id"], item["id"])

    def test_create_edge_uses_shared_manufacturer_directory_and_preserves_relations(self) -> None:
        app = self._build_app()

        with TestClient(app) as client:
            create_response = client.post(
                "/catalog/edges",
                json={
                    "manufacturer_id": self.manufacturer_id,
                    "name": "ABS 23x0.8",
                    "manufacturer_article": "ABS-23-08",
                    "decor_code": "D123",
                    "color": "White",
                    "material_type": "ABS",
                    "width_mm": 23,
                    "thickness_mm": 0.8,
                    "finish": "matte",
                    "image_url": "https://example.com/new-edge.jpg",
                },
            )

            self.assertEqual(create_response.status_code, 200)
            payload = create_response.json()
            self.assertTrue(payload["success"])
            self.assertIsNotNone(payload["item"])
            self.assertEqual(payload["item"]["manufacturer_name"], "REHAU")
            self.assertEqual(payload["item"]["manufacturer_article"], "ABS-23-08")
            self.assertEqual(payload["item"]["price_summary"], [])
            self.assertEqual(payload["item"]["supplier_summary"], [])
            self.assertEqual(payload["item"]["supplier_offers"], [])

            list_response = client.get("/catalog/edges")
            self.assertEqual(list_response.status_code, 200)
            list_payload = list_response.json()
            self.assertTrue(list_payload["success"])
            self.assertEqual(len(list_payload["items"]), 2)
            self.assertTrue(any(item["id"] == payload["item"]["id"] for item in list_payload["items"]))

            validation_response = client.post(
                "/catalog/edges",
                json={
                    "manufacturer_id": self.manufacturer_id,
                    "width_mm": 23,
                    "thickness_mm": 0.8,
                },
            )
            self.assertEqual(validation_response.status_code, 422)
            self.assertEqual(self.session.query(MaterialEdgeRelationModel).count(), 0)

    def test_create_edge_allows_minimal_manual_payload_without_optional_fields(self) -> None:
        app = self._build_app()

        with TestClient(app) as client:
            create_response = client.post(
                "/catalog/edges",
                json={
                    "manufacturer_id": self.manufacturer_id,
                    "name": "ABS 23x0.8",
                    "width_mm": 23,
                    "thickness_mm": 0.8,
                },
            )

        self.assertEqual(create_response.status_code, 200)
        payload = create_response.json()
        self.assertTrue(payload["success"])
        self.assertIsNotNone(payload["item"])
        self.assertEqual(payload["item"]["manufacturer_article"], None)
        self.assertEqual(payload["item"]["image_url"], None)
        self.assertEqual(self.session.query(MaterialEdgeRelationModel).count(), 0)

    def test_get_edge_detail_returns_canonical_data_and_dependencies(self) -> None:
        app = self._build_app()

        with TestClient(app) as client:
            response = client.get(f"/catalog/edges/{self.existing_edge_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        item = payload["item"]
        self.assertEqual(item["id"], self.existing_edge_id)
        self.assertEqual(item["manufacturer_name"], "REHAU")
        self.assertEqual(len(item["supplier_offers"]), 2)
        self.assertEqual(len(item["price_summary"]), 1)
        self.assertEqual(item["material_relations"], [])

    def test_get_edge_detail_includes_material_cards_with_material_metadata(self) -> None:
        material = self.session.get(MaterialModel, self.material_id)
        assert material is not None
        material.manufacturer_id = self.manufacturer_id
        material.image = "https://example.com/material.jpg"
        material.category = "Panels"
        material.product_type = "MDF"
        material.dimensions = "2800x2070"
        material.thickness = "18 mm"
        material.is_default = True
        material.owner_user_id = "owner-1"

        relation = MaterialEdgeRelationModel(
            material_id=self.material_id,
            edge_id=self.existing_edge_id,
            relation_type="recommended",
            source_supplier_id=self.supplier_viyar_id,
            source_url="https://example.com/material/edge",
        )
        self.session.add(relation)
        self.session.commit()

        app = self._build_app()

        with TestClient(app) as client:
            response = client.get(f"/catalog/edges/{self.existing_edge_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        item = payload["item"]
        self.assertEqual(len(item["material_relations"]), 1)
        relation_payload = item["material_relations"][0]
        self.assertEqual(relation_payload["material_id"], self.material_id)
        self.assertEqual(relation_payload["material_article"], "M-001")
        self.assertEqual(relation_payload["material_name"], "Material 1")
        self.assertEqual(relation_payload["material_image"], "https://example.com/material.jpg")
        self.assertEqual(relation_payload["material_category"], "Panels")
        self.assertEqual(relation_payload["material_product_type"], "MDF")
        self.assertEqual(relation_payload["material_dimensions"], "2800x2070")
        self.assertEqual(relation_payload["material_thickness"], "18 mm")
        self.assertEqual(relation_payload["material_manufacturer_id"], self.manufacturer_id)
        self.assertEqual(relation_payload["material_manufacturer_name"], "REHAU")
        self.assertEqual(relation_payload["material_manufacturer_logo_url"], "https://example.com/rehau.png")
        self.assertTrue(relation_payload["material_is_default"])
        self.assertEqual(relation_payload["material_owner_user_id"], "owner-1")

    def test_get_edge_detail_returns_404_for_missing_edge(self) -> None:
        app = self._build_app()

        with TestClient(app) as client:
            response = client.get("/catalog/edges/999999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Edge not found")

    def test_update_edge_patch_updates_canonical_fields_without_touching_relations(self) -> None:
        app = self._build_app()

        with TestClient(app) as client:
            response = client.patch(
                f"/catalog/edges/{self.existing_edge_id}",
                json={
                    "name": "Updated edge name",
                    "width_mm": 24.0,
                    "thickness_mm": 0.9,
                    "image_url": "https://example.com/updated-edge.jpg",
                    "is_active": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        item = payload["item"]
        self.assertEqual(item["name"], "Updated edge name")
        self.assertEqual(item["width_mm"], 24.0)
        self.assertEqual(item["thickness_mm"], 0.9)
        self.assertEqual(item["image_url"], "https://example.com/updated-edge.jpg")
        self.assertFalse(item["is_active"])
        self.assertEqual(self.session.query(MaterialEdgeRelationModel).count(), 0)

    def test_delete_edge_blocks_when_material_relations_exist(self) -> None:
        relation = MaterialEdgeRelationModel(
            material_id=self.material_id,
            edge_id=self.existing_edge_id,
            relation_type="recommended",
            source_supplier_id=self.supplier_viyar_id,
            source_url="https://example.com/material/edge",
        )
        self.session.add(relation)
        self.session.commit()

        app = self._build_app()

        with TestClient(app) as client:
            response = client.delete(f"/catalog/edges/{self.existing_edge_id}")

        self.assertEqual(response.status_code, 409)
        payload = response.json()["detail"]
        self.assertFalse(payload["success"])
        self.assertIn("неможливо видалити крайку", payload["error"].lower())
        self.assertEqual(self.session.query(CanonicalEdgeModel).count(), 1)
        self.assertEqual(self.session.query(EdgeSupplierOfferModel).count(), 2)
        self.assertEqual(self.session.query(EdgeSupplierOfferPriceModel).count(), 2)
        self.assertEqual(self.session.query(MaterialEdgeRelationModel).count(), 1)

    def test_delete_edge_removes_canonical_edge_and_child_offers(self) -> None:
        app = self._build_app()

        with TestClient(app) as client:
            response = client.delete(f"/catalog/edges/{self.existing_edge_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(self.session.query(CanonicalEdgeModel).count(), 0)
        self.assertEqual(self.session.query(EdgeSupplierOfferModel).count(), 0)
        self.assertEqual(self.session.query(EdgeSupplierOfferPriceModel).count(), 0)
        self.assertEqual(self.session.query(MaterialEdgeRelationModel).count(), 0)

    def test_preview_edge_source_uses_product_parser_only(self) -> None:
        app = self._build_app()
        preview_payload = {
            "success": True,
            "source_url": "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
            "preview_count": 1,
            "items": [
                {
                    "status": "parsed",
                    "discovered_card": {
                        "article": "141342",
                        "name": "141342 edge",
                        "source_url": "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                    },
                    "canonical_candidate": {
                        "manufacturer": "REHAU",
                        "manufacturer_article": "141342",
                        "name": "141342 edge",
                        "decor_code": None,
                        "color": "Green",
                        "material_type": "ABS",
                        "width_mm": 22.0,
                        "thickness_mm": 0.4,
                        "finish": "matte",
                        "image_url": None,
                    },
                    "supplier_offer_candidate": {
                        "supplier": "viyar",
                        "article": "185187",
                        "external_product_id": None,
                        "source_url": "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                        "unit": "м.п.",
                        "availability": "in stock",
                        "price": 19.26,
                        "currency": "UAH",
                    },
                }
            ],
        }

        with patch.object(catalog, "_ensure_material_feature_access", autospec=True) as access_mock, \
            patch.object(catalog, "detect_material_source_site", return_value="viyar"), \
            patch.object(catalog, "preview_viyar_edge_product_for_catalog", new=AsyncMock(return_value=preview_payload)), \
            patch.object(catalog, "_resolve_viyar_cookie_for_user", new=AsyncMock(return_value=None)):
            access_mock.return_value = None
            app = self._build_app()
            with TestClient(app) as client:
                response = client.post(
                    "/catalog/edges/source-preview",
                    json={"source_url": "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["source_site"], "viyar")
        self.assertEqual(payload["recommended_edges_count"], 1)
        self.assertEqual(payload["preview_count"], 1)

    def test_preview_edge_source_rejects_empty_product_preview(self) -> None:
        app = self._build_app()

        with patch.object(catalog, "_ensure_material_feature_access", autospec=True) as access_mock, \
            patch.object(catalog, "detect_material_source_site", return_value="viyar"), \
            patch.object(catalog, "preview_viyar_edge_product_for_catalog", new=AsyncMock(return_value={
                "success": False,
                "error": "Edge candidate could not be parsed",
                "source_url": "https://viyar.ua/ua/catalog/broken-edge/",
                "items": [],
                "preview_count": 0,
            })), \
            patch.object(catalog, "_resolve_viyar_cookie_for_user", new=AsyncMock(return_value=None)):
            access_mock.return_value = None
            with TestClient(app) as client:
                response = client.post(
                    "/catalog/edges/source-preview",
                    json={"source_url": "https://viyar.ua/ua/catalog/broken-edge/"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"], "Edge candidate could not be parsed")

    def test_preview_edge_source_rejects_unsupported_sites(self) -> None:
        app = self._build_app()

        with patch.object(catalog, "_ensure_material_feature_access", autospec=True) as access_mock, \
            patch.object(catalog, "detect_material_source_site", return_value="generic"):
            access_mock.return_value = None
            with TestClient(app) as client:
                response = client.post(
                    "/catalog/edges/source-preview",
                    json={"source_url": "https://example.com/edge"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"], "Unsupported edge source URL")

    def test_create_edge_from_preview_persists_without_relations(self) -> None:
        app = self._build_app()
        preview_result = {
            "success": True,
            "items": [
                {
                    "status": "parsed",
                    "discovered_card": {
                        "article": "141342",
                        "name": "141342 edge",
                        "source_url": "https://viyar.ua/ua/catalog/edge/",
                    },
                    "canonical_candidate": {
                        "manufacturer": "REHAU",
                        "manufacturer_article": "141342",
                        "name": "141342 edge",
                        "decor_code": None,
                        "color": "Green",
                        "material_type": "ABS",
                        "width_mm": 22.0,
                        "thickness_mm": 0.4,
                        "finish": "matte",
                        "image_url": None,
                    },
                    "supplier_offer_candidate": {
                        "supplier": "viyar",
                        "article": "185187",
                        "external_product_id": None,
                        "source_url": "https://viyar.ua/ua/catalog/edge/",
                        "unit": "м.п.",
                        "availability": "in stock",
                        "price": 19.26,
                        "currency": "UAH",
                    },
                }
            ],
        }
        persistence_result = {
            "success": True,
            "city": "kyiv",
            "items": [
                {
                    "status": "persisted",
                    "reason": None,
                }
            ],
            "counts": {
                "items": 1,
                "persisted": 1,
                "reused": 0,
                "needs_review": 0,
                "failed": 0,
            },
        }

        fake_service = Mock()
        fake_service.persist_preview_result_for_catalog.return_value = persistence_result

        with patch.object(catalog, "_ensure_material_feature_access", autospec=True) as access_mock, \
            patch.object(catalog, "EdgeFoundationPersistenceService", return_value=fake_service), \
            patch.object(catalog, "SessionLocal", return_value=Mock(close=Mock())):
            access_mock.return_value = None
            with TestClient(app) as client:
                response = client.post(
                    "/catalog/edges/source-create",
                    json={
                        "preview_result": preview_result,
                        "city": "kyiv",
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["summary"], persistence_result["counts"])
        self.assertEqual(payload["persistence_result"]["counts"]["persisted"], 1)
        fake_service.persist_preview_result_for_catalog.assert_called_once()

    def test_create_edge_from_preview_persists_canonical_edge_and_offer(self) -> None:
        app = self._build_app()
        preview_result = {
            "success": True,
            "source_url": "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
            "preview_count": 1,
            "items": [
                {
                    "status": "parsed",
                    "discovered_card": {
                        "article": "141342",
                        "name": "141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU",
                        "source_url": "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                    },
                    "canonical_candidate": {
                        "manufacturer": "Rehau",
                        "manufacturer_article": "141342",
                        "name": "141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU",
                        "decor_code": None,
                        "color": "Смарагд зелений",
                        "material_type": "ABS",
                        "width_mm": 22.0,
                        "thickness_mm": 0.4,
                        "finish": "Без напрямку",
                        "image_url": "https://viyar.ua/store/Items/photos/ph185187.jpg",
                    },
                    "supplier_offer_candidate": {
                        "supplier": "viyar",
                        "article": "185187",
                        "external_product_id": None,
                        "source_url": "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                        "unit": "м.п.",
                        "availability": "В наявності",
                        "price": 19.26,
                        "currency": "UAH",
                    },
                    "raw_characteristics": {},
                }
            ],
        }

        with TestClient(app) as client:
            response = client.post(
                "/catalog/edges/source-create",
                json={
                    "preview_result": preview_result,
                    "city": "Kyiv",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["summary"]["persisted"], 1)
        self.assertEqual(self.session.query(CanonicalEdgeModel).count(), 2)
        self.assertEqual(self.session.query(EdgeSupplierOfferModel).count(), 3)
        self.assertEqual(self.session.query(EdgeSupplierOfferPriceModel).count(), 3)
        self.assertEqual(self.session.query(MaterialEdgeRelationModel).count(), 0)

        with TestClient(app) as client:
            repeat_response = client.post(
                "/catalog/edges/source-create",
                json={
                    "preview_result": preview_result,
                    "city": "Kyiv",
                },
            )

        self.assertEqual(repeat_response.status_code, 200)
        repeat_payload = repeat_response.json()
        self.assertTrue(repeat_payload["success"])
        self.assertEqual(self.session.query(CanonicalEdgeModel).count(), 2)
        self.assertEqual(self.session.query(EdgeSupplierOfferModel).count(), 3)
        self.assertEqual(self.session.query(EdgeSupplierOfferPriceModel).count(), 3)
        self.assertEqual(self.session.query(MaterialEdgeRelationModel).count(), 0)

    def test_create_edge_from_preview_rejects_empty_candidate(self) -> None:
        app = self._build_app()

        with TestClient(app) as client:
            response = client.post(
                "/catalog/edges/source-create",
                json={
                    "preview_result": {
                        "success": True,
                        "source_url": "https://viyar.ua/ua/catalog/broken-edge/",
                        "preview_count": 0,
                        "items": [],
                    },
                    "city": "Kyiv",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertIn("canonical edge", payload["error"])
        self.assertEqual(self.session.query(CanonicalEdgeModel).count(), 1)
        self.assertEqual(self.session.query(EdgeSupplierOfferModel).count(), 2)
        self.assertEqual(self.session.query(MaterialEdgeRelationModel).count(), 0)

    def test_upload_edge_image_returns_url_and_saves_file(self) -> None:
        app = self._build_app()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as uploads_dir:
            upload_root = Path(uploads_dir) / "edge-images"
            with patch.object(upload_service, "EDGE_IMAGE_UPLOAD_ROOT", upload_root):
                with TestClient(app) as client:
                    response = client.post(
                        "/catalog/edges/image",
                        files={
                            "file": ("edge.png", _make_png_bytes(), "image/png"),
                        },
                    )

                    self.assertEqual(response.status_code, 200)
                    payload = response.json()
                    self.assertTrue(payload["success"])
                    self.assertTrue(payload["image_url"].startswith("/uploads/edge-images/"))
                    self.assertTrue((upload_root / Path(payload["image_url"]).name).exists())


if __name__ == "__main__":
    unittest.main()
