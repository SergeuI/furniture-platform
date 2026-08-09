from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import auth as auth_dependencies
from api.routes import mounting_schemes as mounting_schemes_route
from database.base import Base
from database.models.fitting import FittingModel
from database.models.mounting_node import MountingNodeModel
from database.models.service_catalog_item import ServiceCatalogItemModel
from database.models.service_drilling_rule import ServiceDrillingRuleModel
from database.models.user import UserModel
from services import mounting_scheme_service as mounting_scheme_service_module


class MountingSchemesApiTests(unittest.TestCase):
    def test_create_list_get_and_patch_routes_work(self) -> None:
        app, session_factory, service_patch = self._build_app()
        service_patch.start()
        try:
            session = session_factory()
            try:
                confirmat = self._create_mounting_node(session, code="confirmat-node", name="Confirmat")
                dowel = self._create_mounting_node(session, code="dowel-node", name="Dowel")
            finally:
                session.close()

            with TestClient(app) as client:
                create_response = client.post(
                    "/mounting-schemes",
                    json={
                        "name": "Confirmat scheme",
                        "nodes": [
                            {
                                "node_id": confirmat.id,
                                "group_key": "primary",
                                "quantity_per_group": 1,
                            }
                        ],
                    },
                )

                self.assertEqual(create_response.status_code, 200)
                created_scheme = create_response.json()["scheme"]
                self.assertEqual(created_scheme["nodes_count"], 1)
                self.assertEqual(created_scheme["nodes"][0]["node_code"], "confirmat-node")

                patch_response = client.patch(
                    f"/mounting-schemes/{created_scheme['id']}",
                    json={
                        "nodes": [
                            {
                                "node_id": confirmat.id,
                                "group_key": "primary",
                                "quantity_per_group": 1,
                            },
                            {
                                "node_id": dowel.id,
                                "group_key": "joint",
                                "quantity_per_group": 1,
                            },
                        ],
                        "placement_rules": [
                            {
                                "group_key": "primary",
                                "distribution_mode": "equal",
                                "min_group_count": 3,
                                "fixed_group_count": 3,
                                "start_offset_mm": 50,
                                "end_offset_mm": 50,
                                "max_spacing_mm": 400,
                            }
                        ],
                    },
                )

                self.assertEqual(patch_response.status_code, 200)
                patched_scheme = patch_response.json()["scheme"]
                self.assertEqual(patched_scheme["nodes_count"], 2)
                self.assertEqual(patched_scheme["placement_rules_count"], 1)

                detail_response = client.get(f"/mounting-schemes/{created_scheme['id']}")
                self.assertEqual(detail_response.status_code, 200)
                detail_scheme = detail_response.json()["scheme"]
                self.assertEqual(detail_scheme["nodes_count"], 2)
                self.assertEqual(detail_scheme["nodes"][1]["node_name"], "Dowel")

                list_response = client.get("/mounting-schemes")
                self.assertEqual(list_response.status_code, 200)
                self.assertEqual(list_response.json()["schemes"][0]["id"], created_scheme["id"])
        finally:
            service_patch.stop()

    def test_list_route_omits_inactive_schemes_by_default(self) -> None:
        app, session_factory, service_patch = self._build_app()
        service_patch.start()
        try:
            session = session_factory()
            try:
                node = self._create_mounting_node(session, code="confirmat-node", name="Confirmat")
            finally:
                session.close()

            service = mounting_scheme_service_module.MountingSchemeService(session=session_factory())
            try:
                service.create_mounting_scheme(
                    {
                        "name": "Active scheme",
                        "nodes": [
                            {
                                "node_id": node.id,
                                "group_key": "primary",
                                "quantity_per_group": 1,
                            }
                        ],
                    }
                )
                service.create_mounting_scheme(
                    {
                        "name": "Inactive scheme",
                        "is_active": False,
                        "nodes": [
                            {
                                "node_id": node.id,
                                "group_key": "primary",
                                "quantity_per_group": 1,
                            }
                        ],
                    }
                )
            finally:
                service.close()

            with TestClient(app) as client:
                response = client.get("/mounting-schemes")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json()["schemes"]), 1)
                self.assertEqual(response.json()["schemes"][0]["name"], "Active scheme")
        finally:
            service_patch.stop()

    @staticmethod
    def _build_app():
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

        app = FastAPI()
        app.include_router(mounting_schemes_route.router, prefix="/mounting-schemes")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")

        service_patch = patch.object(mounting_scheme_service_module, "SessionLocal", session_factory)
        return app, session_factory, service_patch

    @staticmethod
    def _create_mounting_node(session, *, code: str, name: str) -> MountingNodeModel:
        node = MountingNodeModel(code=code, name=name)
        session.add(node)
        session.commit()
        session.refresh(node)
        return node


if __name__ == "__main__":
    unittest.main()
