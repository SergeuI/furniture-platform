from __future__ import annotations

import unittest
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
    FittingManufacturerModel,
    FittingProductModel,
    FittingSeriesModel,
)
from database.repositories import fitting_taxonomy_repository
from database.repositories import inventory_repository


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

                detail_response = client.get(
                    "/catalog/fitting-products/1",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(detail_response.status_code, 200)
                self.assertEqual(detail_response.json()["item"]["category_id"], 2)

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
