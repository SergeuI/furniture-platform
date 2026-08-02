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

from api.dependencies import auth as auth_dependencies
from api.routes import mounting_nodes as mounting_nodes_route
from database.base import Base
from database.models.fitting import FittingHoleTemplateModel, FittingModel
from database.models.mounting_node import MountingNodeModel
from database.models.user import UserModel
from services.mounting_node_service import MountingNodeService


class _AllowedEntitlementService:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def has_feature(self, current_user, feature_key: str) -> bool:
        return feature_key == "fitting_holes.use"


class _DeniedEntitlementService:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def has_feature(self, current_user, feature_key: str) -> bool:
        return False


class MountingNodesApiTests(unittest.TestCase):
    def test_list_route_requires_fitting_holes_access(self) -> None:
        app = self._build_app()

        with patch.object(mounting_nodes_route, "EntitlementService", _DeniedEntitlementService):
            with TestClient(app) as client:
                response = client.get(
                    "/mounting-nodes",
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "Insufficient permissions")

    def test_get_route_returns_404_for_missing_node(self) -> None:
        app = self._build_app()

        class MissingService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def get_mounting_node(self, node_id, **kwargs):
                return None

        with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
            with patch.object(mounting_nodes_route, "MountingNodeService", return_value=MissingService()):
                with TestClient(app) as client:
                    response = client.get(
                        "/mounting-nodes/999",
                        headers={"Authorization": "Bearer token"},
                    )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Mounting node with id=999 does not exist")

    def test_create_route_returns_node_for_admin(self) -> None:
        app = self._build_app()
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")

        class CreateService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def create_mounting_node(self, payload):
                return {
                    "id": 1,
                    "code": "mounting-node-confirmat-7x50",
                    "name": payload["name"],
                    "description": None,
                    "owner_user_id": None,
                    "is_active": True,
                    "created_by_user_id": "user-1",
                    "updated_by_user_id": "user-1",
                    "created_at": None,
                    "updated_at": None,
                    "items_count": 1,
                    "templates_count": 0,
                    "items": [],
                    "templates": [],
                }

        with patch.object(mounting_nodes_route, "MountingNodeService", return_value=CreateService()):
            with TestClient(app) as client:
                response = client.post(
                    "/mounting-nodes",
                    json={
                        "name": "Confirmat node",
                        "items": [{"fitting_id": 1, "quantity": 1}],
                    },
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["node"]["name"], "Confirmat node")

    def test_create_route_returns_nested_template_and_point_ids_for_admin(self) -> None:
        app = self._build_app()
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")

        class CreateService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def create_mounting_node(self, payload):
                return {
                    "id": 1,
                    "code": "mounting-node-confirmat-7x50",
                    "name": payload["name"],
                    "description": None,
                    "owner_user_id": None,
                    "is_active": True,
                    "created_by_user_id": "user-1",
                    "updated_by_user_id": "user-1",
                    "created_at": None,
                    "updated_at": None,
                    "items_count": 1,
                    "templates_count": 1,
                    "items": [],
                    "templates": [
                        {
                            "id": 11,
                            "node_id": 1,
                            "template_id": 7428,
                            "template_name": "Main template",
                            "fitting_id": 1,
                            "fitting_code": "confirmat_7x50",
                            "fitting_article": "190106",
                            "mounting_variant_key": "face_to_edge",
                            "is_default": True,
                            "order_index": 0,
                            "points_count": 2,
                            "is_active": True,
                            "template": {
                                "id": 7428,
                                "fitting_id": 1,
                                "name": "Main template",
                                "bundle_key": None,
                                "bundle_name": None,
                                "bundle_order_index": 0,
                                "template_type": "manual",
                                "side": None,
                                "coordinate_system": "2d",
                                "mounting_variant_key": "face_to_edge",
                                "is_default": True,
                                "notes": None,
                                "is_active": True,
                                "points": [
                                    {
                                        "id": 29,
                                        "template_id": 7428,
                                        "label": None,
                                        "x_mm": 0.0,
                                        "y_mm": 0.0,
                                        "z_mm": 0.0,
                                        "target_panel": "vertical_panel",
                                        "target_surface": "plane",
                                        "target_side": "inner_face",
                                        "diameter_mm": 7.0,
                                        "service_drilling_rule_id": None,
                                        "depth_mm": None,
                                        "side": "inner_face",
                                        "operation": "drill",
                                        "order_index": 0,
                                        "quantity": 1,
                                        "mirrored": False,
                                        "notes": None,
                                    },
                                    {
                                        "id": 30,
                                        "template_id": 7428,
                                        "label": None,
                                        "x_mm": 0.0,
                                        "y_mm": 0.0,
                                        "z_mm": 0.0,
                                        "target_panel": "horizontal_panel",
                                        "target_surface": "edge",
                                        "target_side": "edge_near_vertical",
                                        "diameter_mm": 4.5,
                                        "service_drilling_rule_id": None,
                                        "depth_mm": 34.0,
                                        "side": "edge_near_vertical",
                                        "operation": "drill",
                                        "order_index": 1,
                                        "quantity": 1,
                                        "mirrored": False,
                                        "notes": None,
                                    },
                                ],
                            },
                        }
                    ],
                }

        with patch.object(mounting_nodes_route, "MountingNodeService", return_value=CreateService()):
            with TestClient(app) as client:
                response = client.post(
                    "/mounting-nodes",
                    json={
                        "name": "Confirmat node",
                        "items": [{"fitting_id": 1, "quantity": 1}],
                    },
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["node"]["templates"][0]["template"]["id"], 7428)
        self.assertEqual(body["node"]["templates"][0]["template"]["points"][0]["id"], 29)
        self.assertEqual(body["node"]["templates"][0]["template"]["points"][1]["id"], 30)

    def test_update_route_returns_nested_template_and_point_ids_for_admin(self) -> None:
        app = self._build_app()
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")

        class PatchService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def update_mounting_node(self, node_id, payload):
                return {
                    "id": node_id,
                    "code": "mounting-node-confirmat-7x50",
                    "name": "Confirmat node",
                    "description": None,
                    "owner_user_id": None,
                    "is_active": True,
                    "created_by_user_id": "user-1",
                    "updated_by_user_id": "user-1",
                    "created_at": None,
                    "updated_at": None,
                    "items_count": 1,
                    "templates_count": 1,
                    "items": [],
                    "templates": [
                        {
                            "id": 11,
                            "node_id": node_id,
                            "template_id": 7428,
                            "template_name": "Main template updated",
                            "fitting_id": 1,
                            "fitting_code": "confirmat_7x50",
                            "fitting_article": "190106",
                            "mounting_variant_key": "face_to_edge",
                            "is_default": True,
                            "order_index": 0,
                            "points_count": 2,
                            "is_active": True,
                            "template": {
                                "id": 7428,
                                "fitting_id": 1,
                                "name": "Main template updated",
                                "bundle_key": None,
                                "bundle_name": None,
                                "bundle_order_index": 0,
                                "template_type": "manual",
                                "side": None,
                                "coordinate_system": "2d",
                                "mounting_variant_key": "face_to_edge",
                                "is_default": True,
                                "notes": None,
                                "is_active": True,
                                "points": [
                                    {
                                        "id": 29,
                                        "template_id": 7428,
                                        "label": None,
                                        "x_mm": 0.0,
                                        "y_mm": 0.0,
                                        "z_mm": 0.0,
                                        "target_panel": "vertical_panel",
                                        "target_surface": "plane",
                                        "target_side": "inner_face",
                                        "diameter_mm": 7.0,
                                        "service_drilling_rule_id": None,
                                        "depth_mm": None,
                                        "side": "inner_face",
                                        "operation": "drill",
                                        "order_index": 0,
                                        "quantity": 1,
                                        "mirrored": False,
                                        "notes": None,
                                    },
                                    {
                                        "id": 31,
                                        "template_id": 7428,
                                        "label": None,
                                        "x_mm": 0.0,
                                        "y_mm": 0.0,
                                        "z_mm": 0.0,
                                        "target_panel": "horizontal_panel",
                                        "target_surface": "edge",
                                        "target_side": "edge_near_vertical",
                                        "diameter_mm": 4.5,
                                        "service_drilling_rule_id": None,
                                        "depth_mm": 34.0,
                                        "side": "edge_near_vertical",
                                        "operation": "drill",
                                        "order_index": 1,
                                        "quantity": 1,
                                        "mirrored": False,
                                        "notes": None,
                                    },
                                ],
                            },
                        }
                    ],
                }

        with patch.object(mounting_nodes_route, "MountingNodeService", return_value=PatchService()):
            with TestClient(app) as client:
                response = client.patch(
                    "/mounting-nodes/1",
                    json={
                        "templates": [
                            {
                                "template_id": 7428,
                                "template": {
                                    "template_id": 7428,
                                    "fitting_id": 1,
                                    "name": "Main template updated",
                                    "template_type": "manual",
                                    "mounting_variant_key": "face_to_edge",
                                    "is_default": True,
                                    "points": [
                                        {"id": 29, "diameter_mm": 7.0, "order_index": 0, "quantity": 1},
                                        {"id": 31, "diameter_mm": 4.5, "depth_mm": 34.0, "order_index": 1, "quantity": 1},
                                    ],
                                },
                            }
                        ]
                    },
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["node"]["templates"][0]["template"]["id"], 7428)
        self.assertEqual(body["node"]["templates"][0]["template"]["points"][0]["id"], 29)
        self.assertEqual(body["node"]["templates"][0]["template"]["points"][1]["id"], 31)

    def test_list_and_detail_route_apply_owner_visibility_and_snapshot(self) -> None:
        session, engine = self._build_session()
        try:
            app = self._build_app()
            admin = self._create_user(session, email="admin@example.com", role="admin")
            user_a = self._create_user(session, email="user-a@example.com", role="free")
            user_b = self._create_user(session, email="user-b@example.com", role="free")
            fitting = self._create_fitting(session, name="Fit A", code="fit-a", article="A")
            system_template = self._create_template(session, fitting.id, name="System Template")
            own_template = self._create_template(session, fitting.id, name="Own Template")
            private_template = self._create_template(session, fitting.id, name="Private Template")
            service = MountingNodeService(session=session)

            system_node = service.create_mounting_node(
                {
                    "name": "System node",
                    "items": [{"fitting_id": fitting.id, "quantity": 1}],
                    "templates": [{"template_id": system_template.id, "is_default": True}],
                },
            )
            own_node = service.create_mounting_node(
                {
                    "name": "Own node",
                    "owner_user_id": user_a.id,
                    "items": [{"fitting_id": fitting.id, "quantity": 1}],
                    "templates": [{"template_id": own_template.id, "is_default": True}],
                },
            )
            private_node = service.create_mounting_node(
                {
                    "name": "Private node",
                    "owner_user_id": user_b.id,
                    "items": [{"fitting_id": fitting.id, "quantity": 1}],
                    "templates": [{"template_id": private_template.id, "is_default": True}],
                },
            )

            app.dependency_overrides[auth_dependencies.require_current_user] = lambda: user_a

            with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
                with patch.object(mounting_nodes_route, "MountingNodeService", return_value=service):
                    with TestClient(app) as client:
                        list_response = client.get(
                            "/mounting-nodes",
                            headers={"Authorization": "Bearer token"},
                        )
                        own_detail_response = client.get(
                            f"/mounting-nodes/{own_node['id']}",
                            headers={"Authorization": "Bearer token"},
                        )
                        foreign_detail_response = client.get(
                            f"/mounting-nodes/{system_node['id'] + 2}",
                            headers={"Authorization": "Bearer token"},
                        )

            self.assertEqual(list_response.status_code, 200)
            list_nodes = list_response.json()["nodes"]
            self.assertEqual({node["name"] for node in list_nodes}, {"System node", "Own node"})
            self.assertEqual({node["name"]: node["ownership_type"] for node in list_nodes}, {"System node": "system", "Own node": "mine"})

            own_detail = own_detail_response.json()["node"]
            self.assertEqual(own_detail_response.status_code, 200)
            self.assertEqual(own_detail["ownership_type"], "mine")
            self.assertTrue(own_detail["is_owner"])
            self.assertFalse(own_detail["is_system"])

            self.assertEqual(foreign_detail_response.status_code, 404)
            self.assertEqual(foreign_detail_response.json()["detail"], f"Mounting node with id={private_node['id']} does not exist")
        finally:
            session.close()
            engine.dispose()

    def _build_app(self) -> FastAPI:
        app = FastAPI()
        app.include_router(mounting_nodes_route.router, prefix="/mounting-nodes")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="free")
        return app

    def _build_session(self):
        tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tempdir.cleanup)
        database_path = Path(tempdir.name) / "test.db"
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        return Session(), engine

    @staticmethod
    def _create_user(session, email: str, role: str) -> UserModel:
        user = UserModel(
            email=email,
            password_hash="hashed-password",
            role=role,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def _create_fitting(session, name: str, code: str, article: str) -> FittingModel:
        fitting = FittingModel(
            name=name,
            code=code,
            article=article,
            is_system=True,
            is_active=True,
            sort_order=0,
        )
        session.add(fitting)
        session.commit()
        session.refresh(fitting)
        return fitting

    @staticmethod
    def _create_template(session, fitting_id: int, name: str) -> FittingHoleTemplateModel:
        template = FittingHoleTemplateModel(
            fitting_id=fitting_id,
            name=name,
            template_type="manual",
            side="left",
            coordinate_system="2d",
            mounting_variant_key="surface_mount",
            is_default=True,
            is_active=True,
        )
        session.add(template)
        session.commit()
        session.refresh(template)
        return template


if __name__ == "__main__":
    unittest.main()
