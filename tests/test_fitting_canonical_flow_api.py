import tempfile
import unittest
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
from database.models.fitting import SupplierModel
from database.repositories import inventory_repository


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

    @staticmethod
    def _create_supplier(session_maker, code: str, name: str, is_active: bool = True) -> SupplierModel:
        db = session_maker()
        try:
            supplier = SupplierModel(code=code, name=name, is_active=is_active)
            db.add(supplier)
            db.commit()
            db.refresh(supplier)
            return supplier
        finally:
            db.close()
