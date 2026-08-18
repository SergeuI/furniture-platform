import tempfile
import unittest
import json
from io import BytesIO
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import auth as auth_dependencies
from api.routes import catalog as catalog_route
from database.base import Base
from database.models import catalog_item  # noqa: F401
from database.models import audit_log  # noqa: F401
from database.models import entitlement_feature  # noqa: F401
from database.models import fitting  # noqa: F401
from database.models import fitting_image  # noqa: F401
from database.models import fitting_hole_service_rule  # noqa: F401
from database.models import material  # noqa: F401
from database.models import material_edge  # noqa: F401
from database.models import material_edge_price  # noqa: F401
from database.models import material_import_job  # noqa: F401
from database.models import material_price  # noqa: F401
from database.models import material_user_link  # noqa: F401
from database.models import plan_entitlement  # noqa: F401
from database.models import project  # noqa: F401
from database.models import project_scan_session  # noqa: F401
from database.models import project_version  # noqa: F401
from database.models import registration_identity  # noqa: F401
from database.models import service_catalog_item  # noqa: F401
from database.models import service_drilling_rule  # noqa: F401
from database.models import user  # noqa: F401
from database.models import user_change_request  # noqa: F401
from database.models import user_service_catalog_price  # noqa: F401
from database.models.fitting import FittingModel, FittingProductModel, FittingSupplierOfferModel, SupplierModel
from database.repositories import inventory_repository
from database.repositories import fitting_taxonomy_repository
from PIL import Image


class FittingCanonicalFlowApiTests(unittest.TestCase):
    def test_create_update_and_offer_routes_support_canonical_flow(self) -> None:
        app, session_maker = self._build_app()
        self._set_session_locals(session_maker)

        with patch.object(auth_dependencies, "require_current_user", return_value=SimpleNamespace(
            id="user-1",
            email="admin@example.com",
            role="admin",
            city="Kyiv",
        )):
            with TestClient(app) as client:
                active_supplier = self._create_supplier(session_maker, code="viyar", name="VIYAR", is_active=True)
                second_active_supplier = self._create_supplier(session_maker, code="hafele", name="Hafele", is_active=True)
                inactive_supplier = self._create_supplier(session_maker, code="legacy", name="Legacy", is_active=False)

                create_response = client.post(
                    "/catalog/fittings",
                    json={
                        "name": "Canonical fitting",
                        "brand": "BLUM",
                        "city": "Kyiv",
                        "fitting_type": "drawer_slides",
                        "fitting_group": "fittings",
                        "is_active": True,
                        "sort_order": 4,
                        "supplier_offer": {
                            "supplier_id": active_supplier.id,
                            "article": "190106",
                            "price": 1.14,
                            "currency": "UAH",
                            "unit": "шт",
                            "stock": "in stock",
                            "is_active": True,
                            "priority": 100,
                        },
                    },
                    headers={"Authorization": "Bearer token"},
                )

                self.assertEqual(create_response.status_code, 200)
                create_payload = create_response.json()
                self.assertTrue(create_payload["success"])
                self.assertEqual(len(create_payload["item"]["supplier_offers"]), 1)
                created_offer = create_payload["item"]["supplier_offers"][0]
                self.assertEqual(created_offer["supplier_code"], "viyar")
                self.assertEqual(created_offer["article"], "190106")
                fitting_id = create_payload["item"]["id"]
                offer_id = created_offer["id"]

                detail_response = client.get(
                    f"/catalog/fittings/{fitting_id}",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(detail_response.status_code, 200)
                self.assertEqual(detail_response.json()["item"]["supplier_offers"][0]["supplier_name"], "VIYAR")

                suppliers_response = client.get(
                    "/catalog/suppliers",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(suppliers_response.status_code, 200)
                supplier_ids = [item["id"] for item in suppliers_response.json()["items"]]
                self.assertIn(active_supplier.id, supplier_ids)
                self.assertNotIn(inactive_supplier.id, supplier_ids)

                offers_response = client.get(
                    f"/catalog/fittings/{fitting_id}/supplier-offers",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(offers_response.status_code, 200)
                self.assertEqual(offers_response.json()["items"][0]["supplier_code"], "viyar")

                update_response = client.put(
                    f"/catalog/fittings/{fitting_id}",
                    json={
                        "name": "Canonical fitting updated",
                        "brand": "Hettich",
                        "city": "Kyiv",
                        "fitting_type": "drawer_slides",
                        "fitting_group": "fittings",
                        "is_active": False,
                        "sort_order": 5,
                        "supplier_offer": {
                            "offer_id": offer_id,
                            "supplier_id": active_supplier.id,
                            "article": "190106-A",
                            "price": 1.25,
                            "currency": "UAH",
                            "unit": "шт",
                            "stock": "limited",
                            "is_active": False,
                            "priority": 50,
                        },
                    },
                    headers={"Authorization": "Bearer token"},
                )

                self.assertEqual(update_response.status_code, 200)
                update_payload = update_response.json()
                self.assertTrue(update_payload["success"])
                self.assertFalse(update_payload["item"]["is_active"])
                self.assertEqual(update_payload["item"]["supplier_offers"][0]["article"], "190106-A")
                self.assertFalse(update_payload["item"]["supplier_offers"][0]["is_active"])

                second_offer_response = client.post(
                    f"/catalog/fittings/{fitting_id}/supplier-offers",
                    json={
                        "supplier_id": second_active_supplier.id,
                        "article": "LEG-200",
                        "price": 2.0,
                        "currency": "UAH",
                        "unit": "шт",
                        "stock": "preorder",
                        "priority": 200,
                    },
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(second_offer_response.status_code, 200)
                self.assertTrue(second_offer_response.json()["success"])

                db = session_maker()
                try:
                    fitting_row = db.execute(
                        text("SELECT is_active, catalog_key FROM fittings WHERE id = :id"),
                        {"id": int(fitting_id)},
                    ).fetchone()
                    self.assertIsNotNone(fitting_row)
                    fitting_row_map = fitting_row._mapping
                    self.assertEqual(fitting_row_map["is_active"], 0)
                    self.assertTrue(str(fitting_row_map["catalog_key"]).strip())

                    offer_rows = db.execute(
                        text("SELECT fitting_id, supplier_id, article, is_active FROM fitting_supplier_offers ORDER BY id"),
                    ).fetchall()
                    self.assertEqual(
                        [(row._mapping["fitting_id"], row._mapping["supplier_id"], row._mapping["article"], row._mapping["is_active"]) for row in offer_rows],
                        [
                            (int(fitting_id), int(active_supplier.id), "190106-A", 0),
                            (int(fitting_id), int(second_active_supplier.id), "LEG-200", 1),
                        ],
                    )
                finally:
                    db.close()

    def test_update_existing_system_fitting_route_persists_reordered_gallery_primary(self) -> None:
        app, session_maker = self._build_app()
        self._set_session_locals(session_maker)

        source_url = "https://viyar.ua/ua/catalog/dyubel_pod_zpressovku_pod_mfix_muller/"
        image_a = "https://cdn.example.com/fittings/a.png"
        image_b = "https://cdn.example.com/fittings/b.png"
        image_c = "https://cdn.example.com/fittings/c.png"
        image_bytes_map = {
            image_a: self._make_png_bytes((220, 40, 40)),
            image_b: self._make_png_bytes((40, 220, 40)),
            image_c: self._make_png_bytes((40, 40, 220)),
        }

        def fake_fetch_remote_image_payload(url: str, city: str | None = None):
            payload = image_bytes_map.get(url)
            if payload is None:
                return None
            return {
                "bytes": payload,
                "content_type": "image/png",
            }

        create_metadata = {
            "success": True,
            "final_url": source_url,
            "source_site": "viyar",
            "name": "Дюбель під запресовку під Mfix Muller",
            "article": "86494",
            "brand": "Muller",
            "image_url": image_a,
            "image_urls": [image_a, image_b, image_c],
            "price": 3.12,
            "availability": "in stock",
            "currency": "UAH",
            "unit": "шт",
            "characteristics": {
                "Тип товару": "Дюбелі",
                "Виробник": "Muller",
                "Країна виробник": "Італія",
            },
        }
        update_result = {
            "name": "Дюбель під запресовку під Mfix Muller",
            "article": "86494",
            "image": image_a,
            "source_url": source_url,
            "price": 3.12,
            "description": "Parsed from source",
        }

        async def fake_parse_fitting_source_metadata(url: str):
            return create_metadata

        async def fake_fetch_viyar_product_details_by_url_traced(url: str, city: str | None = None):
            return update_result, {}

        with patch.object(auth_dependencies, "require_current_user", return_value=SimpleNamespace(
            id="user-1",
            email="admin@example.com",
            role="admin",
            city="Kyiv",
        )):
            with patch.object(catalog_route, "parse_fitting_source_metadata", side_effect=fake_parse_fitting_source_metadata):
                with patch.object(catalog_route, "fetch_viyar_product_details_by_url_traced", side_effect=fake_fetch_viyar_product_details_by_url_traced):
                    with patch.object(catalog_route, "fetch_remote_image_payload", side_effect=fake_fetch_remote_image_payload):
                        with session_maker() as db:
                            supplier = SupplierModel(
                                code="viyar",
                                name="VIYAR",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                            )
                            product = FittingProductModel(
                                article="86494",
                                name="Дюбель під запресовку під Mfix Muller",
                                brand="Muller",
                                is_active=True,
                            )
                            db.add_all([supplier, product])
                            db.flush()
                            fitting_row = FittingModel(
                                name="Дюбель під запресовку під Mfix Muller",
                                article="86494",
                                technical_product_id=product.id,
                                city="Kyiv",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                                source="viyar",
                                source_url=source_url,
                                brand="Muller",
                                price=3.12,
                                stock="in stock",
                                image_url=image_a,
                            )
                            db.add(fitting_row)
                            db.flush()
                            db.add_all(
                                [
                                    fitting_image.FittingImageModel(
                                        fitting_id=fitting_row.id,
                                        source_url=image_a,
                                        sort_order=0,
                                        is_primary=True,
                                        image_cached_bytes=image_bytes_map[image_a],
                                        image_cached_content_type="image/png",
                                        image_sha256=sha256(image_bytes_map[image_a]).hexdigest(),
                                    ),
                                    fitting_image.FittingImageModel(
                                        fitting_id=fitting_row.id,
                                        source_url=image_b,
                                        sort_order=1,
                                        is_primary=False,
                                        image_cached_bytes=image_bytes_map[image_b],
                                        image_cached_content_type="image/png",
                                        image_sha256=sha256(image_bytes_map[image_b]).hexdigest(),
                                    ),
                                    fitting_image.FittingImageModel(
                                        fitting_id=fitting_row.id,
                                        source_url=image_c,
                                        sort_order=2,
                                        is_primary=False,
                                        image_cached_bytes=image_bytes_map[image_c],
                                        image_cached_content_type="image/png",
                                        image_sha256=sha256(image_bytes_map[image_c]).hexdigest(),
                                    ),
                                ]
                            )
                            db.commit()
                            fitting_id = str(fitting_row.id)
                            supplier_id = int(supplier.id)
                            product_id = int(product.id)

                        with TestClient(app) as client:
                            update_response = client.put(
                                f"/catalog/fittings/{fitting_id}",
                                json={
                                    "name": "Дюбель під запресовку під Mfix Muller",
                                    "source_url": source_url,
                                    "fitting_type": "drawer_slides",
                                    "fitting_group": "fittings",
                                    "is_active": True,
                                    "image_urls": [image_b, image_a, image_c],
                                    "supplier_offer": {
                                        "supplier_id": supplier_id,
                                        "article": "86494",
                                        "price": 3.12,
                                        "currency": "UAH",
                                        "unit": "шт",
                                        "stock": "in stock",
                                        "is_active": True,
                                        "priority": 100,
                                    },
                                },
                                headers={"Authorization": "Bearer token"},
                            )

                            self.assertEqual(update_response.status_code, 200)
                            update_payload = update_response.json()
                            self.assertTrue(update_payload["success"])
                            self.assertEqual(update_payload["item"]["image_url"], image_b)

                            detail_response = client.get(
                                f"/catalog/fittings/{fitting_id}",
                                headers={"Authorization": "Bearer token"},
                            )
                            self.assertEqual(detail_response.status_code, 200)
                            detail_payload = detail_response.json()
                            self.assertTrue(detail_payload["success"])
                            self.assertEqual(detail_payload["item"]["image_url"], image_b)

                        with session_maker() as db:
                            fitting_db_row = db.execute(
                                text("SELECT image_url, is_system, technical_product_id FROM fittings WHERE id = :id"),
                                {"id": int(fitting_id)},
                            ).fetchone()
                            self.assertIsNotNone(fitting_db_row)
                            self.assertEqual(fitting_db_row._mapping["image_url"], image_b)
                            self.assertTrue(fitting_db_row._mapping["is_system"])
                            self.assertEqual(int(fitting_db_row._mapping["technical_product_id"]), product_id)

                            image_rows = db.execute(
                                text(
                                    "SELECT source_url, sort_order, is_primary "
                                    "FROM fitting_images WHERE fitting_id = :fitting_id ORDER BY sort_order",
                                ),
                                {"fitting_id": int(fitting_id)},
                            ).fetchall()

                        self.assertEqual(
                            [
                                (
                                    row._mapping["source_url"],
                                    row._mapping["sort_order"],
                                    row._mapping["is_primary"],
                                )
                                for row in image_rows
                            ],
                            [
                                (image_b, 0, 1),
                                (image_a, 1, 0),
                                (image_c, 2, 0),
                            ],
                        )

    def test_update_fitting_route_persists_reordered_gallery_primary(self) -> None:
        app, session_maker = self._build_app()
        self._set_session_locals(session_maker)

        source_url = "https://viyar.ua/ua/catalog/dyubel_pod_zpressovku_pod_mfix_muller/"
        image_a = "https://cdn.example.com/fittings/a.png"
        image_b = "https://cdn.example.com/fittings/b.png"
        image_c = "https://cdn.example.com/fittings/c.png"
        image_bytes_map = {
            image_a: self._make_png_bytes((220, 40, 40)),
            image_b: self._make_png_bytes((40, 220, 40)),
            image_c: self._make_png_bytes((40, 40, 220)),
        }

        def fake_fetch_remote_image_payload(url: str, city: str | None = None):
            payload = image_bytes_map.get(url)
            if payload is None:
                return None
            return {
                "bytes": payload,
                "content_type": "image/png",
            }

        create_metadata = {
            "success": True,
            "final_url": source_url,
            "source_site": "viyar",
            "name": "Дюбель під запресовку під Mfix Muller",
            "article": "86494",
            "brand": "Muller",
            "image_url": image_a,
            "image_urls": [image_a, image_b, image_c],
            "price": 3.12,
            "availability": "in stock",
            "currency": "UAH",
            "unit": "шт",
            "characteristics": {
                "Тип товару": "Дюбелі",
                "Виробник": "Muller",
                "Країна виробник": "Італія",
            },
        }
        update_result = {
            "name": "Дюбель під запресовку під Mfix Muller",
            "article": "86494",
            "image": image_a,
            "source_url": source_url,
            "price": 3.12,
            "description": "Parsed from source",
        }

        async def fake_parse_fitting_source_metadata(url: str):
            return create_metadata

        async def fake_fetch_viyar_product_details_by_url_traced(url: str, city: str | None = None):
            return update_result, {}

        with patch.object(auth_dependencies, "require_current_user", return_value=SimpleNamespace(
            id="user-1",
            email="admin@example.com",
            role="admin",
            city="Kyiv",
        )):
            with patch.object(catalog_route, "parse_fitting_source_metadata", side_effect=fake_parse_fitting_source_metadata):
                with patch.object(catalog_route, "fetch_viyar_product_details_by_url_traced", side_effect=fake_fetch_viyar_product_details_by_url_traced):
                    with patch.object(catalog_route, "fetch_remote_image_payload", side_effect=fake_fetch_remote_image_payload):
                        with TestClient(app) as client:
                            supplier = self._create_supplier(session_maker, code="viyar", name="VIYAR", is_active=True)

                            create_response = client.post(
                                "/catalog/fittings",
                                json={
                                    "name": "Дюбель під запресовку під Mfix Muller",
                                    "source_url": source_url,
                                    "fitting_type": "drawer_slides",
                                    "fitting_group": "fittings",
                                    "is_active": True,
                                    "image_urls": [image_a, image_b, image_c],
                                    "supplier_offer": {
                                        "supplier_id": supplier.id,
                                        "article": "86494",
                                        "price": 3.12,
                                        "currency": "UAH",
                                        "unit": "шт",
                                        "stock": "in stock",
                                        "is_active": True,
                                        "priority": 100,
                                    },
                                },
                                headers={"Authorization": "Bearer token"},
                            )

                            self.assertEqual(create_response.status_code, 200)
                            self.assertTrue(create_response.json()["success"])
                            fitting_id = create_response.json()["item"]["id"]
                            self.assertEqual(create_response.json()["item"]["image_url"], image_a)

                            update_response = client.put(
                                f"/catalog/fittings/{fitting_id}",
                                json={
                                    "name": "Дюбель під запресовку під Mfix Muller",
                                    "source_url": source_url,
                                    "fitting_type": "drawer_slides",
                                    "fitting_group": "fittings",
                                    "is_active": True,
                                    "image_urls": [image_b, image_a, image_c],
                                    "supplier_offer": {
                                        "supplier_id": supplier.id,
                                        "article": "86494",
                                        "price": 3.12,
                                        "currency": "UAH",
                                        "unit": "шт",
                                        "stock": "in stock",
                                        "is_active": True,
                                        "priority": 100,
                                    },
                                },
                                headers={"Authorization": "Bearer token"},
                            )

                            self.assertEqual(update_response.status_code, 200)
                            update_payload = update_response.json()
                            self.assertTrue(update_payload["success"])
                            self.assertEqual(update_payload["item"]["image_url"], image_b)
                            self.assertIn("characteristics", update_payload["item"])
                            self.assertEqual(len(update_payload["item"]["characteristics"]), 3)

                            with session_maker() as db:
                                source_payload_row = db.execute(
                                    text("SELECT source_payload_json FROM fittings WHERE id = :id"),
                                    {"id": int(fitting_id)},
                                ).fetchone()
                                image_rows = db.execute(
                                    text(
                                        "SELECT source_url, sort_order, is_primary "
                                        "FROM fitting_images WHERE fitting_id = :fitting_id ORDER BY sort_order",
                                    ),
                                    {"fitting_id": int(fitting_id)},
                                ).fetchall()

                            self.assertIsNotNone(source_payload_row)
                            source_payload = json.loads(source_payload_row._mapping["source_payload_json"])
                            self.assertIn("parsed_item", source_payload)
                            self.assertIn("characteristics", source_payload["parsed_item"])
                            self.assertEqual(len(source_payload["parsed_item"]["characteristics"]), 3)

                            self.assertEqual(
                                [
                                    (
                                        row._mapping["source_url"],
                                        row._mapping["sort_order"],
                                        row._mapping["is_primary"],
                                    )
                                    for row in image_rows
                                ],
                                [
                                    (image_b, 0, 1),
                                    (image_a, 1, 0),
                                    (image_c, 2, 0),
                                ],
                            )

    @staticmethod
    def _make_png_bytes(color: tuple[int, int, int]) -> bytes:
        buffer = BytesIO()
        Image.new("RGB", (1, 1), color).save(buffer, format="PNG")
        return buffer.getvalue()

    def test_delete_fitting_product_route_removes_linked_fitting_without_stale_data_error(self) -> None:
        app, session_maker = self._build_app()
        self._set_session_locals(session_maker)

        with patch.object(auth_dependencies, "require_current_user", return_value=SimpleNamespace(
            id="user-1",
            email="admin@example.com",
            role="admin",
            city="Kyiv",
        )):
            with TestClient(app) as client:
                with session_maker() as db:
                    supplier = SupplierModel(
                        code="delete-test-supplier",
                        name="Delete Test Supplier",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    product = FittingProductModel(
                        id=38,
                        article="0010",
                        name="DELETE TEST product",
                        brand="Test",
                        is_active=True,
                    )
                    fitting = FittingModel(
                        name="DELETE TEST",
                        article="0010",
                        technical_product_id=38,
                        city="Kyiv",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    db.add_all([supplier, product, fitting])
                    db.flush()
                    db.add(
                        FittingSupplierOfferModel(
                            fitting_id=fitting.id,
                            supplier_id=supplier.id,
                            article="0010",
                            source_url=None,
                            price=80.0,
                            currency="UAH",
                            unit="шт",
                            stock="in stock",
                            is_active=True,
                            priority=100,
                        )
                    )
                    db.commit()

                    fitting_id = int(fitting.id)
                    product_id = int(product.id)
                    supplier_id = int(supplier.id)

                response = client.delete(
                    f"/catalog/fitting-products/{product_id}",
                    headers={"Authorization": "Bearer token"},
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(int(payload["item"]["id"]), product_id)

                with session_maker() as db:
                    self.assertIsNotNone(db.get(SupplierModel, supplier_id))
                    self.assertIsNone(db.get(FittingModel, fitting_id))
                    self.assertIsNone(db.get(FittingProductModel, product_id))
                    self.assertEqual(
                        db.query(FittingSupplierOfferModel).filter(FittingSupplierOfferModel.fitting_id == fitting_id).count(),
                        0,
                    )

    def test_update_fitting_route_syncs_canonical_product_article_for_mt_source(self) -> None:
        app, session_maker = self._build_app()
        self._set_session_locals(session_maker)

        source_url = "https://mt.ua/products/petlya-clip-top-blumotion-110-nakladnaya-specialnaya-chernyj-61148"
        image_a = "https://cdn.example.com/fittings/a.png"

        def fake_fetch_remote_image_payload(url: str, city: str | None = None):
            if url != image_a:
                return None
            return {
                "bytes": self._make_png_bytes((220, 40, 40)),
                "content_type": "image/png",
            }

        create_metadata = {
            "success": True,
            "final_url": source_url,
            "source_site": "mt",
            "name": "CLIP top BLUMOTION спеціальна завіса 110°",
            "article": "61148",
            "brand": "BLUM",
            "image_url": image_a,
            "image_urls": [image_a],
            "price": 175.7,
            "availability": "in stock",
            "currency": "UAH",
            "unit": "шт",
            "characteristics": {
                "Система завіс": "CLIP top BLUMOTION",
                "Кут відкривання завіси, °": "110",
            },
        }
        update_metadata = {
            "success": True,
            "final_url": source_url,
            "source_site": "mt",
            "name": "CLIP top BLUMOTION спеціальна завіса 110°",
            "article": "092799",
            "brand": "BLUM",
            "image_url": image_a,
            "image_urls": [image_a],
            "price": 175.7,
            "availability": "in stock",
            "currency": "UAH",
            "unit": "шт",
            "characteristics": {
                "Система завіс": "CLIP top BLUMOTION",
                "Кут відкривання завіси, °": "110",
            },
        }

        parse_results = [create_metadata, update_metadata]

        async def fake_parse_fitting_source_metadata(url: str):
            return parse_results.pop(0)

        with patch.object(auth_dependencies, "require_current_user", return_value=SimpleNamespace(
            id="user-1",
            email="admin@example.com",
            role="admin",
            city="Kyiv",
        )):
            with patch.object(catalog_route, "parse_fitting_source_metadata", side_effect=fake_parse_fitting_source_metadata):
                with patch.object(catalog_route, "fetch_remote_image_payload", side_effect=fake_fetch_remote_image_payload):
                    with TestClient(app) as client:
                        supplier = self._create_supplier(session_maker, code="mt", name="MT", is_active=True)

                        create_response = client.post(
                            "/catalog/fittings",
                            json={
                                "name": "CLIP top BLUMOTION спеціальна завіса 110°",
                                "source_url": source_url,
                                "fitting_type": "drawer_slides",
                                "fitting_group": "fittings",
                                "is_active": True,
                                "image_urls": [image_a],
                                "supplier_offer": {
                                    "supplier_id": supplier.id,
                                    "article": "61148",
                                    "price": 175.7,
                                    "currency": "UAH",
                                    "unit": "шт",
                                    "stock": "in stock",
                                    "is_active": True,
                                    "priority": 100,
                                },
                            },
                            headers={"Authorization": "Bearer token"},
                        )

                        self.assertEqual(create_response.status_code, 200)
                        self.assertTrue(create_response.json()["success"])
                        fitting_id = create_response.json()["item"]["id"]
                        self.assertEqual(create_response.json()["item"]["article"], "61148")

                        update_response = client.put(
                            f"/catalog/fittings/{fitting_id}",
                            json={
                                "name": "CLIP top BLUMOTION спеціальна завіса 110°",
                                "source_url": source_url,
                                "fitting_type": "drawer_slides",
                                "fitting_group": "fittings",
                                "is_active": True,
                                "image_urls": [image_a],
                                "supplier_offer": {
                                    "supplier_id": supplier.id,
                                    "article": "092799",
                                    "price": 175.7,
                                    "currency": "UAH",
                                    "unit": "шт",
                                    "stock": "in stock",
                                    "is_active": True,
                                    "priority": 100,
                                },
                            },
                            headers={"Authorization": "Bearer token"},
                        )

                        self.assertEqual(update_response.status_code, 200)
                        update_payload = update_response.json()
                        self.assertTrue(update_payload["success"])
                        self.assertEqual(update_payload["item"]["article"], "092799")

                        with session_maker() as db:
                            fitting_row = db.execute(
                                text("SELECT article, technical_product_id FROM fittings WHERE id = :id"),
                                {"id": int(fitting_id)},
                            ).fetchone()
                            self.assertIsNotNone(fitting_row)
                            self.assertIsNotNone(fitting_row._mapping["technical_product_id"])
                            product_row = db.execute(
                                text("SELECT article, code FROM fitting_products WHERE id = :id"),
                                {"id": int(fitting_row._mapping["technical_product_id"])},
                            ).fetchone()

                        self.assertIsNotNone(product_row)
                        self.assertEqual(fitting_row._mapping["article"], "092799")
                        self.assertEqual(product_row._mapping["article"], "092799")
                        self.assertEqual(product_row._mapping["code"], "092799")

                        detail_response = client.get(
                            f"/catalog/fittings/{fitting_id}",
                            headers={"Authorization": "Bearer token"},
                        )
                        self.assertEqual(detail_response.status_code, 200)
                        self.assertTrue(detail_response.json()["success"])
                        self.assertEqual(detail_response.json()["item"]["article"], "092799")

                        list_response = client.get(
                            "/catalog/fitting-products",
                            headers={"Authorization": "Bearer token"},
                        )
                        self.assertEqual(list_response.status_code, 200)
                        self.assertTrue(list_response.json()["success"])
                        list_items = list_response.json()["items"]
                        self.assertTrue(any(item["article"] == "092799" for item in list_items))

                        with session_maker() as db:
                            fitting_row = db.execute(
                                text("SELECT article, technical_product_id FROM fittings WHERE id = :id"),
                                {"id": int(fitting_id)},
                            ).fetchone()
                            self.assertIsNotNone(fitting_row)
                            self.assertIsNotNone(fitting_row._mapping["technical_product_id"])
                            product_row = db.execute(
                                text("SELECT article, code FROM fitting_products WHERE id = :id"),
                                {"id": int(fitting_row._mapping["technical_product_id"])},
                            ).fetchone()

                        self.assertIsNotNone(product_row)
                        self.assertEqual(fitting_row._mapping["article"], "092799")
                        self.assertEqual(product_row._mapping["article"], "092799")
                        self.assertEqual(product_row._mapping["code"], "092799")

    @staticmethod
    def _build_app():
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        session_maker = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        app = FastAPI()
        app.include_router(catalog_route.router, prefix="/catalog")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(
            id="user-1",
            email="admin@example.com",
            role="admin",
            city="Kyiv",
        )

        return app, session_maker

    @staticmethod
    def _set_session_locals(session_maker) -> None:
        catalog_route.SessionLocal = session_maker
        inventory_repository.SessionLocal = session_maker
        fitting_taxonomy_repository.SessionLocal = session_maker

    @staticmethod
    def _create_supplier(session_maker, code: str, name: str, is_active: bool = True) -> SupplierModel:
        db = session_maker()
        try:
            supplier = SupplierModel(
                code=code,
                name=name,
                owner_user_id=None,
                is_system=True,
                is_active=is_active,
            )
            db.add(supplier)
            db.commit()
            db.refresh(supplier)
            return supplier
        finally:
            db.close()
