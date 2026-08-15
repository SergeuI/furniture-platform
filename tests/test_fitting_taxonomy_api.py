from __future__ import annotations

import unittest
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import auth as auth_dependencies
from api.routes import catalog as catalog_route
from database.base import Base
from database.models import audit_log  # noqa: F401
from database.models import catalog_item  # noqa: F401
from database.models import entitlement_feature  # noqa: F401
from database.models import fitting  # noqa: F401
from database.models import fitting_hole_service_rule  # noqa: F401
from database.models import fitting_image  # noqa: F401
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
from database.models.fitting import (
    FittingCategoryModel,
    FittingModel,
    FittingManufacturerModel,
    FittingProductModel,
    FittingSeriesModel,
)
from database.models.mounting_node import (
    MountingNodeItemModel,
    MountingNodeModel,
)
from database.repositories import fitting_taxonomy_repository
from database.repositories import inventory_repository
from services.fitting_image_gallery_service import PreparedFittingGalleryImage


class FittingTaxonomyApiTests(unittest.TestCase):
    def test_taxonomy_endpoints_list_and_detail(self) -> None:
        app, session_maker = self._build_app()
        self._set_session_locals(session_maker)
        self._seed_data(session_maker)

        with patch.object(catalog_route, "_ensure_fitting_feature_access", return_value=None):
            with TestClient(app) as client:
                manufacturers_response = client.get(
                    "/catalog/fitting-manufacturers",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(manufacturers_response.status_code, 200)
                manufacturers_payload = manufacturers_response.json()
                self.assertTrue(manufacturers_payload["success"])
                self.assertEqual(len(manufacturers_payload["items"]), 2)

                manufacturer_id = manufacturers_payload["items"][0]["id"]
                series_response = client.get(
                    f"/catalog/fitting-series?manufacturer_id={manufacturer_id}",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(series_response.status_code, 200)
                series_payload = series_response.json()
                self.assertTrue(series_payload["success"])
                self.assertEqual(len(series_payload["items"]), 1)
                self.assertEqual(series_payload["items"][0]["manufacturer_id"], manufacturer_id)

                categories_response = client.get(
                    "/catalog/fitting-categories?parent_id=1",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(categories_response.status_code, 200)
                categories_payload = categories_response.json()
                self.assertTrue(categories_payload["success"])
                self.assertEqual(len(categories_payload["items"]), 1)

                products_response = client.get(
                    "/catalog/fitting-products?manufacturer_id=1",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(products_response.status_code, 200)
                products_payload = products_response.json()
                self.assertTrue(products_payload["success"])
                self.assertEqual(len(products_payload["items"]), 1)
                product = products_payload["items"][0]
                self.assertEqual(product["manufacturer_id"], 1)
                self.assertEqual(product["series_id"], 1)
                self.assertEqual(product["category_id"], 2)

                all_products_response = client.get(
                    "/catalog/fitting-products?manufacturer_id=1&active_only=false",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(all_products_response.status_code, 200)
                all_products_payload = all_products_response.json()
                self.assertTrue(all_products_payload["success"])
                self.assertEqual(len(all_products_payload["items"]), 2)

                detail_response = client.get(
                    "/catalog/fitting-products/1",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(detail_response.status_code, 200)
                self.assertEqual(detail_response.json()["item"]["category_id"], 2)

    def test_taxonomy_admin_crud_routes_and_product_taxonomy_patch(self) -> None:
        app, session_maker = self._build_app()
        self._set_session_locals(session_maker)
        self._seed_data(session_maker)

        with patch.object(catalog_route, "_ensure_fitting_feature_access", return_value=None):
            with TestClient(app) as client:
                headers = {"Authorization": "Bearer token"}

                manufacturer_response = client.post(
                    "/catalog/fitting-manufacturers",
                    json={
                        "code": "blum",
                        "name": "Blum",
                        "description": "Hidden hinge manufacturer",
                        "country_code": "AT",
                        "is_active": True,
                        "sort_order": 3,
                    },
                    headers=headers,
                )
                self.assertEqual(manufacturer_response.status_code, 200)
                manufacturer_payload = manufacturer_response.json()
                self.assertTrue(manufacturer_payload["success"])
                manufacturer_id = int(manufacturer_payload["item"]["id"])

                update_manufacturer_response = client.patch(
                    f"/catalog/fitting-manufacturers/{manufacturer_id}",
                    json={
                        "code": "blum",
                        "name": "Blum Updated",
                        "description": "Updated description",
                        "country_code": "AT",
                        "logo_url": "https://example.com/logo.svg",
                        "website_url": "https://example.com",
                        "is_active": False,
                        "sort_order": 7,
                    },
                    headers=headers,
                )
                self.assertEqual(update_manufacturer_response.status_code, 200)
                self.assertTrue(update_manufacturer_response.json()["success"])
                self.assertEqual(update_manufacturer_response.json()["item"]["name"], "Blum Updated")

                spare_manufacturer_response = client.post(
                    "/catalog/fitting-manufacturers",
                    json={
                        "code": "spare",
                        "name": "Spare Manufacturer",
                        "country_code": "DE",
                        "is_active": True,
                        "sort_order": 9,
                    },
                    headers=headers,
                )
                self.assertEqual(spare_manufacturer_response.status_code, 200)
                spare_manufacturer_id = int(spare_manufacturer_response.json()["item"]["id"])

                series_response = client.post(
                    "/catalog/fitting-series",
                    json={
                        "manufacturer_id": manufacturer_id,
                        "code": "clip-top",
                        "name": "CLIP top",
                        "description": "Series for hidden hinges",
                        "is_active": True,
                        "sort_order": 2,
                    },
                    headers=headers,
                )
                self.assertEqual(series_response.status_code, 200)
                series_payload = series_response.json()
                self.assertTrue(series_payload["success"])
                series_id = int(series_payload["item"]["id"])

                update_series_response = client.patch(
                    f"/catalog/fitting-series/{series_id}",
                    json={
                        "manufacturer_id": manufacturer_id,
                        "code": "clip-top",
                        "name": "CLIP top updated",
                        "description": "Updated series",
                        "is_active": False,
                        "sort_order": 4,
                    },
                    headers=headers,
                )
                self.assertEqual(update_series_response.status_code, 200)
                self.assertTrue(update_series_response.json()["success"])
                self.assertEqual(update_series_response.json()["item"]["name"], "CLIP top updated")

                category_response = client.post(
                    "/catalog/fitting-categories",
                    json={
                        "code": "blum-hinges",
                        "name": "Hinges",
                        "description": "Hidden hinge category",
                        "parent_id": None,
                        "is_active": True,
                        "sort_order": 1,
                    },
                    headers=headers,
                )
                self.assertEqual(category_response.status_code, 200)
                category_payload = category_response.json()
                self.assertTrue(category_payload["success"])
                category_id = int(category_payload["item"]["id"])

                update_category_response = client.patch(
                    f"/catalog/fitting-categories/{category_id}",
                    json={
                        "code": "blum-hinges-updated",
                        "name": "Hinges Updated",
                        "description": "Updated category",
                        "parent_id": None,
                        "is_active": False,
                        "sort_order": 2,
                    },
                    headers=headers,
                )
                self.assertEqual(update_category_response.status_code, 200)
                self.assertTrue(update_category_response.json()["success"])
                self.assertEqual(update_category_response.json()["item"]["code"], "blum-hinges-updated")

                taxonomy_patch_response = client.patch(
                    "/catalog/fitting-products/1/taxonomy",
                    json={
                        "manufacturer_id": manufacturer_id,
                        "series_id": series_id,
                        "category_id": category_id,
                        "is_active": False,
                    },
                    headers=headers,
                )
                self.assertEqual(taxonomy_patch_response.status_code, 200)
                taxonomy_patch_payload = taxonomy_patch_response.json()
                self.assertTrue(taxonomy_patch_payload["success"])
                self.assertEqual(taxonomy_patch_payload["item"]["manufacturer_id"], manufacturer_id)
                self.assertEqual(taxonomy_patch_payload["item"]["series_id"], series_id)
                self.assertEqual(taxonomy_patch_payload["item"]["category_id"], category_id)
                self.assertFalse(taxonomy_patch_payload["item"]["is_active"])

                taxonomy_detail_response = client.get(
                    "/catalog/fitting-products/1",
                    headers=headers,
                )
                self.assertEqual(taxonomy_detail_response.status_code, 200)
                taxonomy_detail_payload = taxonomy_detail_response.json()
                self.assertEqual(taxonomy_detail_payload["item"]["manufacturer_id"], manufacturer_id)
                self.assertEqual(taxonomy_detail_payload["item"]["series_id"], series_id)
                self.assertEqual(taxonomy_detail_payload["item"]["category_id"], category_id)
                self.assertFalse(taxonomy_detail_payload["item"]["is_active"])

                delete_manufacturer_blocked_response = client.delete(
                    f"/catalog/fitting-manufacturers/{manufacturer_id}",
                    headers=headers,
                )
                self.assertEqual(delete_manufacturer_blocked_response.status_code, 200)
                self.assertFalse(delete_manufacturer_blocked_response.json()["success"])
                self.assertTrue(delete_manufacturer_blocked_response.json()["error"])

                delete_series_blocked_response = client.delete(
                    f"/catalog/fitting-series/{series_id}",
                    headers=headers,
                )
                self.assertEqual(delete_series_blocked_response.status_code, 200)
                self.assertFalse(delete_series_blocked_response.json()["success"])
                self.assertTrue(delete_series_blocked_response.json()["error"])

                delete_category_blocked_response = client.delete(
                    f"/catalog/fitting-categories/{category_id}",
                    headers=headers,
                )
                self.assertEqual(delete_category_blocked_response.status_code, 200)
                self.assertFalse(delete_category_blocked_response.json()["success"])
                self.assertTrue(delete_category_blocked_response.json()["error"])

                delete_spare_manufacturer_response = client.delete(
                    f"/catalog/fitting-manufacturers/{spare_manufacturer_id}",
                    headers=headers,
                )
                self.assertEqual(delete_spare_manufacturer_response.status_code, 200)
                self.assertTrue(delete_spare_manufacturer_response.json()["success"])
                self.assertEqual(int(delete_spare_manufacturer_response.json()["item"]["id"]), spare_manufacturer_id)

    def test_delete_fitting_product_route_hard_deletes_linked_rows(self) -> None:
        app, session_maker = self._build_app()
        self._set_session_locals(session_maker)

        with patch.object(catalog_route, "_ensure_fitting_feature_access", return_value=None):
            with TestClient(app) as client:
                headers = {"Authorization": "Bearer token"}

                with session_maker() as db:
                    manufacturer = FittingManufacturerModel(code="hettich", name="Hettich", is_active=True, sort_order=1)
                    category = FittingCategoryModel(code="hinges", name="Hinges", is_active=True, sort_order=1)
                    db.add_all([manufacturer, category])
                    db.flush()

                    product = FittingProductModel(
                        article="TP-100",
                        code="TP-100",
                        name="Canonical product",
                        brand="Hettich",
                        manufacturer_id=manufacturer.id,
                        category_id=category.id,
                        is_active=True,
                    )
                    db.add(product)
                    db.flush()

                    linked_fitting = FittingModel(
                        article="TP-100",
                        name="Linked fitting",
                        city="Kyiv",
                        source="viyar",
                        is_system=False,
                        owner_user_id="user-1",
                        is_active=True,
                        technical_product_id=product.id,
                    )
                    db.add(linked_fitting)
                    db.commit()
                    product_id = int(product.id)

                delete_response = client.delete(
                    f"/catalog/fitting-products/{product_id}",
                    headers=headers,
                )
                self.assertEqual(delete_response.status_code, 200)
                delete_payload = delete_response.json()
                self.assertTrue(delete_payload["success"])
                self.assertEqual(int(delete_payload["item"]["id"]), product_id)

                with session_maker() as db:
                    self.assertEqual(db.query(FittingProductModel).count(), 0)
                    self.assertEqual(db.query(FittingModel).count(), 0)
                    self.assertEqual(db.query(MountingNodeItemModel).count(), 0)

                second_delete_response = client.delete(
                    f"/catalog/fitting-products/{product_id}",
                    headers=headers,
                )
                self.assertEqual(second_delete_response.status_code, 200)
                self.assertFalse(second_delete_response.json()["success"])
                self.assertTrue(second_delete_response.json()["error"])

    def test_source_create_route_assigns_taxonomy_ids_to_canonical_product(self) -> None:
        app, session_maker = self._build_app()
        self._set_session_locals(session_maker)

        image_bytes = b"canonical-image-bytes"
        prepared_gallery_image = PreparedFittingGalleryImage(
            sort_order=0,
            is_primary=True,
            source_url="https://cdn.example.com/fittings/main.jpg",
            image_bytes=image_bytes,
            content_type="image/jpeg",
            sha256=sha256(image_bytes).hexdigest(),
        )

        metadata = {
            "success": True,
            "source_site": "viyar",
            "final_url": "https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
            "name": "Дюбель під стяжку VB DU 321 (9021847) Hettich",
            "article": "61136",
            "brand": "Hettich",
            "description": "Parsed from source",
            "price": 5.22,
            "availability": "В наявності",
            "currency": "UAH",
            "unit": "шт",
            "image_urls": ["https://cdn.example.com/fittings/main.jpg"],
            "image_url": "https://cdn.example.com/fittings/main.jpg",
        }

        with patch.object(catalog_route, "_ensure_fitting_feature_access", return_value=None):
            with patch.object(catalog_route, "_parse_fitting_source_or_error", return_value=(metadata, None)):
                with patch.object(catalog_route, "prepare_fitting_gallery_images", return_value=[prepared_gallery_image]):
                    with TestClient(app) as client:
                        headers = {"Authorization": "Bearer token"}

                        with session_maker() as db:
                            manufacturer = FittingManufacturerModel(code="hettich", name="Hettich", is_active=True, sort_order=1)
                            category = FittingCategoryModel(code="connectors_fasteners", name="Connectors and fasteners", is_active=True, sort_order=1)
                            supplier = fitting.SupplierModel(code="viyar", name="VIYAR", is_active=True)
                            db.add_all([manufacturer, category, supplier])
                            db.commit()
                            manufacturer_id = int(manufacturer.id)
                            category_id = int(category.id)
                            supplier_id = int(supplier.id)

                        response = client.post(
                            "/catalog/fittings",
                            json={
                                "article": "61136",
                                "brand": "Hettich",
                                "city": "Kyiv",
                                "code": None,
                                "fitting_group": "fasteners",
                                "fitting_type": "connectors_fasteners",
                                "image_url": None,
                                "is_active": True,
                                "name": "https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                                "price": None,
                                "sort_order": 0,
                                "source_url": "https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                                "stock": None,
                                "supplier_offer": {
                                    "supplier_id": supplier_id,
                                    "article": "61136",
                                    "external_product_id": None,
                                    "source_url": "https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                                    "price": 5.22,
                                    "currency": "UAH",
                                    "unit": "шт",
                                    "stock": "В наявності",
                                    "is_active": True,
                                    "priority": 100,
                                },
                            },
                            headers=headers,
                        )

                        self.assertEqual(response.status_code, 200)
                        payload = response.json()
                        self.assertTrue(payload["success"])
                        self.assertEqual(payload["operation"], "created")

                        with session_maker() as db:
                            product = db.query(FittingProductModel).one()
                            fitting_item = db.query(FittingModel).one()

                        self.assertEqual(product.manufacturer_id, manufacturer_id)
                        self.assertEqual(product.category_id, category_id)
                        self.assertEqual(fitting_item.technical_product_id, product.id)
                        self.assertEqual(fitting_item.article, "61136")
                        self.assertEqual(fitting_item.source_url, metadata["final_url"])
                        self.assertEqual(fitting_item.source, "viyar")
    def test_delete_fitting_product_route_blocks_when_linked_fitting_is_used_in_mounting_node(self) -> None:
        app, session_maker = self._build_app()
        self._set_session_locals(session_maker)

        with patch.object(catalog_route, "_ensure_fitting_feature_access", return_value=None):
            with TestClient(app) as client:
                headers = {"Authorization": "Bearer token"}

                with session_maker() as db:
                    manufacturer = FittingManufacturerModel(code="hettich", name="Hettich", is_active=True, sort_order=1)
                    db.add(manufacturer)
                    db.flush()
                    product = FittingProductModel(
                        article="TP-200",
                        code="TP-200",
                        name="Blocked product",
                        brand="Hettich",
                        manufacturer_id=manufacturer.id,
                        is_active=True,
                    )
                    fitting = FittingModel(
                        article="TP-200",
                        name="Blocked fitting",
                        city="Kyiv",
                        source="viyar",
                        is_system=False,
                        owner_user_id="user-1",
                        is_active=True,
                        technical_product_id=None,
                    )
                    node = MountingNodeModel(
                        code="node-2",
                        name="Node 2",
                        is_active=True,
                    )
                    db.add_all([product, fitting, node])
                    db.flush()
                    fitting.technical_product_id = product.id
                    db.add(
                        MountingNodeItemModel(
                            node_id=node.id,
                            fitting_id=fitting.id,
                            role="primary",
                            quantity=1,
                            is_required=True,
                            affects_processing=True,
                            order_index=0,
                        )
                    )
                    db.commit()
                    product_id = int(product.id)

                delete_response = client.delete(
                    f"/catalog/fitting-products/{product_id}",
                    headers=headers,
                )
                self.assertEqual(delete_response.status_code, 200)
                delete_payload = delete_response.json()
                self.assertFalse(delete_payload["success"])
                self.assertTrue(delete_payload["dependent_nodes"])
                self.assertEqual(delete_payload["dependent_nodes"][0]["name"], "Node 2")

                with session_maker() as db:
                    self.assertEqual(db.query(FittingProductModel).count(), 1)
                    self.assertEqual(db.query(FittingModel).count(), 1)
                    self.assertEqual(db.query(MountingNodeItemModel).count(), 1)
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
        fitting_taxonomy_repository.SessionLocal = session_maker

    @staticmethod
    def _seed_data(session_maker) -> None:
        db = session_maker()
        try:
            manufacturer = FittingManufacturerModel(code="hettich", name="Hettich", is_active=True, sort_order=1)
            other_manufacturer = FittingManufacturerModel(code="muller", name="Muller", is_active=True, sort_order=2)
            db.add_all([manufacturer, other_manufacturer])
            db.flush()

            series = FittingSeriesModel(
                manufacturer_id=manufacturer.id,
                code="quadro",
                name="Quadro",
                is_active=True,
                sort_order=1,
            )
            root_category = FittingCategoryModel(
                code="fittings",
                name="Furnitura",
                parent_id=None,
                is_active=True,
                sort_order=1,
            )
            child_category = FittingCategoryModel(
                code="hinges",
                name="Hinges",
                parent=root_category,
                is_active=True,
                sort_order=1,
            )
            db.add_all([series, root_category, child_category])
            db.flush()

            db.add_all(
                [
                    FittingProductModel(
                        article="A1",
                        code="A1",
                        name="Hettich Quadro",
                        brand="Hettich",
                        manufacturer_id=manufacturer.id,
                        series_id=series.id,
                        category_id=child_category.id,
                        is_active=True,
                    ),
                    FittingProductModel(
                        article="A0",
                        code="A0",
                        name="Hidden Hettich item",
                        brand="Hettich",
                        manufacturer_id=manufacturer.id,
                        series_id=series.id,
                        category_id=child_category.id,
                        is_active=False,
                    ),
                    FittingProductModel(
                        article="A2",
                        code="A2",
                        name="Muller item",
                        brand="Muller",
                        manufacturer_id=other_manufacturer.id,
                        series_id=None,
                        category_id=None,
                        is_active=True,
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
