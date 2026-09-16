from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import auth as auth_dependencies
from api.routes import processing as processing_route
from database.base import Base
from database.models.hole_library import HoleLibraryTypeModel
from database.models.service_catalog_item import ServiceCatalogItemModel
from database.models.service_drilling_rule import ServiceDrillingRuleModel
from database.models.user import UserModel
import database.session as database_session
from database.repositories import hole_library_repository as repository_module
from database.repositories.hole_library_repository import seed_default_hole_library


class HoleLibraryApiTests(unittest.TestCase):
    def test_list_and_toggle_active(self) -> None:
        app, session_factory = self._build_app()
        self._seed_service_catalog(session_factory)

        with patch.object(repository_module, "SessionLocal", session_factory):
            seed_default_hole_library()

        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin", email="admin@example.com")

        with patch.object(repository_module, "SessionLocal", session_factory), patch.object(database_session, "SessionLocal", session_factory):
            with TestClient(app) as client:
                response = client.get("/processing/hole-library", headers={"Authorization": "Bearer token"})
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertTrue(body["success"])
                self.assertEqual(body["count"], 28)
                self.assertIn("primary_mapping", body["items"][0])

                create_response = client.post(
                    "/processing/hole-library",
                    json={
                        "name": "Глухий отвір Ø3",
                        "operation_type": "blind",
                        "surface_type": "plane",
                        "diameter_mm": 3,
                        "depth_mode": "fixed",
                        "fixed_depth_mm": 8,
                        "is_system": False,
                        "is_active": True,
                    },
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(create_response.status_code, 200)
                created_item = create_response.json()["item"]
                self.assertTrue(created_item["code"].startswith("CUSTOM_BLIND_PLANE_D3"))

                through_response = client.post(
                    "/processing/hole-library",
                    json={
                        "name": "Тест",
                        "operation_type": "through",
                        "surface_type": "plane",
                        "diameter_mm": 15,
                        "depth_mode": "through",
                        "is_system": False,
                        "is_active": True,
                    },
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(through_response.status_code, 200)
                through_item = through_response.json()["item"]
                self.assertTrue(through_item["code"].startswith("CUSTOM_THROUGH_PLANE_D15"))
                self.assertIsNone(through_item["fixed_depth_mm"])
                self.assertIsNone(through_item["min_depth_mm"])
                self.assertIsNone(through_item["max_depth_mm"])

                refreshed_list = client.get(
                    "/processing/hole-library?include_inactive=true",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(refreshed_list.status_code, 200)
                self.assertEqual(refreshed_list.json()["count"], 30)
                self.assertTrue(any(item["id"] == through_item["id"] for item in refreshed_list.json()["items"]))

                first_item = body["items"][0]
                toggle_response = client.patch(
                    f"/processing/hole-library/{first_item['id']}",
                    json={"is_active": False},
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(toggle_response.status_code, 200)
                self.assertFalse(toggle_response.json()["item"]["is_active"])

                detail_response = client.get(
                    f"/processing/hole-library/{first_item['id']}",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(detail_response.status_code, 200)
                self.assertEqual(detail_response.json()["item"]["id"], first_item["id"])

    @staticmethod
    def _build_app():
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
        app = FastAPI()
        app.include_router(processing_route.router, prefix="/processing")
        return app, Session

    @staticmethod
    def _seed_service_catalog(session_factory) -> None:
        with session_factory() as session:
            session.add(
                UserModel(
                    id="user-1",
                    email="user@example.com",
                    role="admin",
                    password_hash="hashed-password",
                )
            )
            session.add_all(
                [
                    ServiceCatalogItemModel(
                        id="svc-00011",
                        source="viyar",
                        external_code="viyar-service-drilling-main-00011",
                        name="Стандартне свердління",
                        slug="standard-drilling",
                        item_type="service",
                        folder_path="viyar-services/prisadka",
                        article="00011",
                        is_active=True,
                    ),
                    ServiceCatalogItemModel(
                        id="svc-98175",
                        source="viyar",
                        external_code="viyar-service-drilling-main-98175",
                        name="Глибоке торцеве свердління",
                        slug="deep-edge-drilling",
                        item_type="service",
                        folder_path="viyar-services/prisadka",
                        article="98175",
                        is_active=True,
                    ),
                    ServiceCatalogItemModel(
                        id="svc-51203",
                        source="viyar",
                        external_code="viyar-service-drilling-main-51203",
                        name="Чашка завіси D35",
                        slug="hinge-cup-d35",
                        item_type="service",
                        folder_path="viyar-services/prisadka",
                        article="51203",
                        is_active=True,
                    ),
                ]
            )
            session.add(
                ServiceDrillingRuleModel(
                    service_catalog_item_id="svc-00011",
                    rule_name="Standard drilling",
                    operation_type="drilling",
                    hole_type="blind",
                    allowed_diameters=[8],
                    allowed_depths=[10, 12, 15],
                    max_blind_depth_mm=13.0,
                    min_edge_offset_mm=7.0,
                    is_active=True,
                )
            )
            session.commit()
