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
from database.models.fitting import FittingHolePointModel, FittingHoleTemplateModel, FittingModel
from database.models.mounting_node import MountingNodeModel
from database.models.mounting_node import MountingNodeVersionModel
from database.models.user import UserModel
from services.mounting_node_service import MountingNodeService


class _FeatureEntitlementService:
    allowed_features: frozenset[str] = frozenset()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def has_feature(self, current_user, feature_key: str) -> bool:
        return feature_key in self.allowed_features


class _AllowedEntitlementService(_FeatureEntitlementService):
    allowed_features = frozenset(
        {
            "fitting_holes.use",
            "mounting_nodes.view",
            "mounting_nodes.create",
            "mounting_nodes.edit",
            "mounting_nodes.delete",
        }
    )


class _ViewOnlyEntitlementService(_FeatureEntitlementService):
    allowed_features = frozenset(
        {
            "fitting_holes.use",
            "mounting_nodes.view",
        }
    )


class _CreateOnlyEntitlementService(_FeatureEntitlementService):
    allowed_features = frozenset(
        {
            "fitting_holes.use",
            "mounting_nodes.create",
        }
    )


class _EditOnlyEntitlementService(_FeatureEntitlementService):
    allowed_features = frozenset(
        {
            "fitting_holes.use",
            "mounting_nodes.edit",
        }
    )


class _DeleteOnlyEntitlementService(_FeatureEntitlementService):
    allowed_features = frozenset(
        {
            "fitting_holes.use",
            "mounting_nodes.delete",
        }
    )


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

    def test_list_route_requires_mounting_nodes_view_access(self) -> None:
        app = self._build_app()

        with patch.object(mounting_nodes_route, "EntitlementService", _CreateOnlyEntitlementService):
            with TestClient(app) as client:
                response = client.get(
                    "/mounting-nodes",
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "Insufficient permissions")

    def test_list_route_forwards_category_filter_to_service(self) -> None:
        app = self._build_app()
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")
        test_case = self

        class ListService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def list_mounting_nodes(self, **kwargs):
                test_case.assertEqual(kwargs.get("category_code"), "hinges")
                return [
                    {
                        "id": 1,
                        "code": "node-1",
                        "name": "Node 1",
                        "description": None,
                        "category_code": "hinges",
                        "owner_user_id": None,
                        "ownership_type": "system",
                        "is_system": True,
                        "is_owner": False,
                        "can_edit": False,
                        "can_delete": False,
                        "is_active": True,
                        "created_by_user_id": None,
                        "updated_by_user_id": None,
                        "is_archived": False,
                        "archived_at": None,
                        "archived_by_user_id": None,
                        "created_at": None,
                        "updated_at": None,
                        "items_count": 0,
                        "templates_count": 0,
                    }
                ]

        with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
            with patch.object(mounting_nodes_route, "MountingNodeService", return_value=ListService()):
                with TestClient(app) as client:
                    response = client.get(
                        "/mounting-nodes?category_code=hinges",
                        headers={"Authorization": "Bearer token"},
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["nodes"][0]["category_code"], "hinges")

    def test_list_route_supports_null_category_filter(self) -> None:
        app = self._build_app()
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")
        test_case = self

        class ListService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def list_mounting_nodes(self, **kwargs):
                test_case.assertEqual(kwargs.get("category_code"), "null")
                return []

        with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
            with patch.object(mounting_nodes_route, "MountingNodeService", return_value=ListService()):
                with TestClient(app) as client:
                    response = client.get(
                        "/mounting-nodes?category_code=null",
                        headers={"Authorization": "Bearer token"},
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["nodes"], [])

    def test_create_route_returns_node_for_admin(self) -> None:
        app = self._build_app()
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")
        test_case = self

        class CreateService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def create_mounting_node(self, payload, **kwargs):
                test_case.assertEqual(payload.get("ownership_type"), "mine")
                test_case.assertEqual(payload.get("category_code"), "hinges")
                test_case.assertEqual(payload.get("functional_code"), "door_hinge")
                return {
                    "id": 1,
                    "code": "mounting-node-confirmat-7x50",
                    "name": payload["name"],
                    "description": None,
                    "category_code": "hinges",
                    "functional_code": "door_hinge",
                    "owner_user_id": "user-1",
                    "ownership_type": "mine",
                    "is_system": False,
                    "is_owner": True,
                    "can_edit": True,
                    "can_delete": True,
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

        with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
            with patch.object(mounting_nodes_route, "MountingNodeService", return_value=CreateService()):
                with TestClient(app) as client:
                    response = client.post(
                        "/mounting-nodes",
                        json={
                            "name": "Confirmat node",
                            "category_code": "hinges",
                            "functional_code": "door_hinge",
                            "ownership_type": "mine",
                            "items": [{"fitting_id": 1, "quantity": 1}],
                        },
                        headers={"Authorization": "Bearer token"},
                    )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["node"]["name"], "Confirmat node")
        self.assertTrue(body["node"]["can_edit"])
        self.assertTrue(body["node"]["can_delete"])
        self.assertEqual(body["node"]["owner_user_id"], "user-1")
        self.assertEqual(body["node"]["ownership_type"], "mine")
        self.assertEqual(body["node"]["category_code"], "hinges")
        self.assertEqual(body["node"]["functional_code"], "door_hinge")

    def test_create_route_rejects_invalid_category_code(self) -> None:
        app = self._build_app()
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")

        with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
            with TestClient(app) as client:
                response = client.post(
                    "/mounting-nodes",
                    json={
                        "name": "Confirmat node",
                        "category_code": "something_invalid",
                        "items": [{"fitting_id": 1, "quantity": 1}],
                    },
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 422)

    def test_create_route_rejects_invalid_functional_code(self) -> None:
        app = self._build_app()
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")

        with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
            with TestClient(app) as client:
                response = client.post(
                    "/mounting-nodes",
                    json={
                        "name": "Confirmat node",
                        "functional_code": "something_invalid",
                        "items": [{"fitting_id": 1, "quantity": 1}],
                    },
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 422)

    def test_create_route_assigns_owner_for_regular_user(self) -> None:
        session, engine = self._build_session()
        try:
            app = self._build_app()
            user = self._create_user(session, email="user-a@example.com", role="free")
            fitting = self._create_fitting(session, name="Fit A", code="fit-a", article="A")
            service = MountingNodeService(session=session)
            app.dependency_overrides[auth_dependencies.require_current_user] = lambda: user

            with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
                with patch.object(mounting_nodes_route, "MountingNodeService", return_value=service):
                    with TestClient(app) as client:
                        response = client.post(
                            "/mounting-nodes",
                            json={
                                "name": "User node",
                                "items": [{"fitting_id": fitting.id, "quantity": 1}],
                            },
                            headers={"Authorization": "Bearer token"},
                        )

            self.assertEqual(response.status_code, 200)
            body = response.json()["node"]
            self.assertEqual(body["owner_user_id"], user.id)
            self.assertEqual(body["created_by_user_id"], user.id)
            self.assertEqual(body["updated_by_user_id"], user.id)
            self.assertEqual(body["ownership_type"], "mine")
            self.assertTrue(body["is_owner"])
            self.assertFalse(body["is_system"])
            self.assertTrue(body["can_edit"])
            self.assertTrue(body["can_delete"])
        finally:
            session.close()
            engine.dispose()

    def test_detail_route_includes_version_history(self) -> None:
        session, engine = self._build_session()
        try:
            app = self._build_app()
            user = self._create_user(session, email="user-a@example.com", role="free")
            fitting = self._create_fitting(session, name="Fit A", code="fit-a", article="A")
            template = self._create_template(session, fitting.id, name="Main template")
            service = MountingNodeService(session=session)
            app.dependency_overrides[auth_dependencies.require_current_user] = lambda: user

            with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
                with patch.object(mounting_nodes_route, "MountingNodeService", return_value=service):
                    with TestClient(app) as client:
                        create_response = client.post(
                            "/mounting-nodes",
                            json={
                                "name": "Versioned node",
                                "items": [{"fitting_id": fitting.id, "quantity": 1}],
                                "templates": [{"template_id": template.id, "is_default": True}],
                            },
                            headers={"Authorization": "Bearer token"},
                        )
                        node_id = create_response.json()["node"]["id"]
                        detail_response = client.get(
                            f"/mounting-nodes/{node_id}",
                            headers={"Authorization": "Bearer token"},
                        )

            self.assertEqual(detail_response.status_code, 200)
            body = detail_response.json()["node"]
            self.assertIn("versions", body)
            self.assertEqual(len(body["versions"]), 1)
            self.assertEqual(body["versions"][0]["version_number"], 1)
            self.assertTrue(body["versions"][0]["is_current"])
            self.assertEqual(body["versions"][0]["snapshot"]["name"], "Versioned node")
            self.assertIsNone(body["functional_code"])
        finally:
            session.close()
            engine.dispose()

    def test_create_route_requires_mounting_nodes_create_access(self) -> None:
        app = self._build_app()
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="free")

        with patch.object(mounting_nodes_route, "EntitlementService", _ViewOnlyEntitlementService):
            with TestClient(app) as client:
                response = client.post(
                    "/mounting-nodes",
                    json={
                        "name": "User node",
                        "items": [{"fitting_id": 1, "quantity": 1}],
                    },
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "Insufficient permissions")

    def test_create_route_returns_nested_template_and_point_ids_for_admin(self) -> None:
        app = self._build_app()
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")

        class CreateService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def create_mounting_node(self, payload, **kwargs):
                return {
                    "id": 1,
                    "code": "mounting-node-confirmat-7x50",
                    "name": payload["name"],
                    "description": None,
                    "owner_user_id": None,
                    "ownership_type": "system",
                    "is_system": True,
                    "is_owner": False,
                    "can_edit": True,
                    "can_delete": True,
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

        with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
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
        test_case = self

        class PatchService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def update_mounting_node(self, node_id, payload, **kwargs):
                test_case.assertEqual(payload.get("category_code"), "fastening")
                test_case.assertEqual(payload.get("functional_code"), "cabinet_leg")
                return {
                    "id": node_id,
                    "code": "mounting-node-confirmat-7x50",
                    "name": "Confirmat node",
                    "description": None,
                    "category_code": "fastening",
                    "functional_code": "cabinet_leg",
                    "owner_user_id": None,
                    "ownership_type": "system",
                    "is_system": True,
                    "is_owner": False,
                    "can_edit": True,
                    "can_delete": True,
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

        with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
            with patch.object(mounting_nodes_route, "MountingNodeService", return_value=PatchService()):
                with TestClient(app) as client:
                    response = client.patch(
                        "/mounting-nodes/1",
                        json={
                            "category_code": "fastening",
                            "functional_code": "cabinet_leg",
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
        self.assertEqual(body["node"]["category_code"], "fastening")
        self.assertEqual(body["node"]["functional_code"], "cabinet_leg")

    def test_update_route_requires_mounting_nodes_edit_access(self) -> None:
        app = self._build_app()
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="free")

        with patch.object(mounting_nodes_route, "EntitlementService", _CreateOnlyEntitlementService):
            with TestClient(app) as client:
                response = client.patch(
                    "/mounting-nodes/1",
                    json={"name": "Updated node"},
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "Insufficient permissions")

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
            self.assertEqual({node["name"]: node["can_edit"] for node in list_nodes}, {"System node": False, "Own node": True})
            self.assertEqual({node["name"]: node["can_delete"] for node in list_nodes}, {"System node": False, "Own node": True})

            own_detail = own_detail_response.json()["node"]
            self.assertEqual(own_detail_response.status_code, 200)
            self.assertEqual(own_detail["ownership_type"], "mine")
            self.assertTrue(own_detail["is_owner"])
            self.assertFalse(own_detail["is_system"])
            self.assertTrue(own_detail["can_edit"])
            self.assertTrue(own_detail["can_delete"])

            self.assertEqual(foreign_detail_response.status_code, 404)
            self.assertEqual(foreign_detail_response.json()["detail"], f"Mounting node with id={private_node['id']} does not exist")
        finally:
            session.close()
            engine.dispose()

    def test_list_and_detail_route_respect_edit_and_delete_entitlements(self) -> None:
        session, engine = self._build_session()
        try:
            app = self._build_app()
            user_a = self._create_user(session, email="user-a@example.com", role="free")
            fitting = self._create_fitting(session, name="Fit A", code="fit-a", article="A")
            service = MountingNodeService(session=session)

            own_node = service.create_mounting_node(
                {
                    "name": "Own node",
                    "items": [{"fitting_id": fitting.id, "quantity": 1}],
                },
                viewer_user_id=user_a.id,
                viewer_role=user_a.role,
            )

            app.dependency_overrides[auth_dependencies.require_current_user] = lambda: user_a

            with patch.object(mounting_nodes_route, "EntitlementService", _ViewOnlyEntitlementService):
                with patch.object(mounting_nodes_route, "MountingNodeService", return_value=service):
                    with TestClient(app) as client:
                        list_response = client.get(
                            "/mounting-nodes",
                            headers={"Authorization": "Bearer token"},
                        )
                        detail_response = client.get(
                            f"/mounting-nodes/{own_node['id']}",
                            headers={"Authorization": "Bearer token"},
                        )

            self.assertEqual(list_response.status_code, 200)
            list_nodes = list_response.json()["nodes"]
            self.assertEqual({node["name"]: node["can_edit"] for node in list_nodes}, {"Own node": False})
            self.assertEqual({node["name"]: node["can_delete"] for node in list_nodes}, {"Own node": False})

            self.assertEqual(detail_response.status_code, 200)
            detail_node = detail_response.json()["node"]
            self.assertFalse(detail_node["can_edit"])
            self.assertFalse(detail_node["can_delete"])
        finally:
            session.close()
            engine.dispose()

    def test_delete_route_archives_node_and_keeps_nested_template_records_for_owner(self) -> None:
        session, engine = self._build_session()
        try:
            app = self._build_app()
            admin = self._create_user(session, email="admin@example.com", role="admin")
            owner = self._create_user(session, email="owner@example.com", role="free")
            stranger = self._create_user(session, email="stranger@example.com", role="free")
            fitting = self._create_fitting(session, name="Fit A", code="fit-a", article="A")
            template = self._create_template(session, fitting.id, name="Nested Template")
            self._create_point(session, template.id, x_mm=0, y_mm=0, z_mm=0)
            service = MountingNodeService(session=session)

            system_node = service.create_mounting_node(
                {
                    "name": "System node",
                    "ownership_type": "system",
                    "items": [{"fitting_id": fitting.id, "quantity": 1}],
                },
                viewer_user_id=admin.id,
                viewer_role=admin.role,
            )
            own_node = service.create_mounting_node(
                {
                    "name": "Own node",
                    "items": [{"fitting_id": fitting.id, "quantity": 1}],
                    "templates": [{"template_id": template.id, "is_default": True}],
                },
                viewer_user_id=owner.id,
                viewer_role=owner.role,
            )
            foreign_node = service.create_mounting_node(
                {
                    "name": "Foreign node",
                    "items": [{"fitting_id": fitting.id, "quantity": 1}],
                },
                viewer_user_id=stranger.id,
                viewer_role=stranger.role,
            )

            app.dependency_overrides[auth_dependencies.require_current_user] = lambda: owner

            with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
                with patch.object(mounting_nodes_route, "MountingNodeService", return_value=service):
                    with TestClient(app) as client:
                        foreign_delete = client.delete(
                            f"/mounting-nodes/{foreign_node['id']}",
                            headers={"Authorization": "Bearer token"},
                        )
                        system_delete = client.delete(
                            f"/mounting-nodes/{system_node['id']}",
                            headers={"Authorization": "Bearer token"},
                        )
                        own_delete = client.delete(
                            f"/mounting-nodes/{own_node['id']}",
                            headers={"Authorization": "Bearer token"},
                        )

            self.assertEqual(foreign_delete.status_code, 404)
            self.assertEqual(system_delete.status_code, 403)
            self.assertEqual(own_delete.status_code, 200)
            self.assertIsNone(own_delete.json()["node"])
            archived_node = session.get(MountingNodeModel, own_node["id"])
            self.assertIsNotNone(archived_node)
            self.assertTrue(archived_node.is_archived)
            self.assertEqual(archived_node.archived_by_user_id, owner.id)
            self.assertIsNotNone(session.get(FittingHoleTemplateModel, template.id))
            self.assertEqual(session.query(FittingHolePointModel).count(), 1)

            with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
                with patch.object(mounting_nodes_route, "MountingNodeService", return_value=service):
                    with TestClient(app) as client:
                        list_response = client.get(
                            "/mounting-nodes",
                            headers={"Authorization": "Bearer token"},
                        )

            self.assertEqual(list_response.status_code, 200)
            self.assertTrue(all(node["id"] != own_node["id"] for node in list_response.json()["nodes"]))
        finally:
            session.close()
            engine.dispose()

    def test_version_route_returns_specific_version_snapshot(self) -> None:
        session, engine = self._build_session()
        try:
            app = self._build_app()
            owner = self._create_user(session, email="owner@example.com", role="free")
            fitting = self._create_fitting(session, name="Fit A", code="fit-a", article="A")
            template = self._create_template(session, fitting.id, name="Main template")
            service = MountingNodeService(session=session)

            app.dependency_overrides[auth_dependencies.require_current_user] = lambda: owner

            with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
                with patch.object(mounting_nodes_route, "MountingNodeService", return_value=service):
                    with TestClient(app) as client:
                        create_response = client.post(
                            "/mounting-nodes",
                            json={
                                "name": "Versioned node",
                                "items": [{"fitting_id": fitting.id, "quantity": 1}],
                                "templates": [{"template_id": template.id, "is_default": True}],
                            },
                            headers={"Authorization": "Bearer token"},
                        )
                        node_id = create_response.json()["node"]["id"]

                        update_response = client.patch(
                            f"/mounting-nodes/{node_id}",
                            json={"description": "Updated description"},
                            headers={"Authorization": "Bearer token"},
                        )
                        version_one_id = update_response.json()["node"]["versions"][1]["id"]
                        version_two_id = update_response.json()["node"]["versions"][0]["id"]

                        version_one_response = client.get(
                            f"/mounting-nodes/{node_id}/versions/{version_one_id}",
                            headers={"Authorization": "Bearer token"},
                        )
                        version_two_response = client.get(
                            f"/mounting-nodes/{node_id}/versions/{version_two_id}",
                            headers={"Authorization": "Bearer token"},
                        )

            self.assertEqual(version_one_response.status_code, 200)
            self.assertEqual(version_two_response.status_code, 200)

            version_one = version_one_response.json()["version"]
            version_two = version_two_response.json()["version"]
            self.assertEqual(version_one["version_number"], 1)
            self.assertFalse(version_one["is_current"])
            self.assertEqual(version_one["snapshot"]["name"], "Versioned node")
            self.assertEqual(version_two["version_number"], 2)
            self.assertTrue(version_two["is_current"])
            self.assertEqual(version_two["snapshot"]["description"], "Updated description")
        finally:
            session.close()
            engine.dispose()

    def test_nested_template_point_save_creates_version_two_and_preserves_version_one(self) -> None:
        session, engine = self._build_session()
        try:
            app = self._build_app()
            owner = self._create_user(session, email="owner@example.com", role="free")
            fitting = self._create_fitting(session, name="Fit A", code="fit-a", article="A")
            template = self._create_template(session, fitting.id, name="Main template")
            service = MountingNodeService(session=session)

            app.dependency_overrides[auth_dependencies.require_current_user] = lambda: owner

            with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
                with patch.object(mounting_nodes_route, "MountingNodeService", return_value=service):
                    with TestClient(app) as client:
                        create_response = client.post(
                            "/mounting-nodes",
                            json={
                                "name": "Versioned node",
                                "items": [{"fitting_id": fitting.id, "quantity": 2}],
                                "templates": [{"template_id": template.id, "is_default": True}],
                            },
                            headers={"Authorization": "Bearer token"},
                        )
                        self.assertEqual(create_response.status_code, 200)
                        created_node = create_response.json()["node"]
                        self.assertEqual(created_node["versions"][0]["version_number"], 1)
                        self.assertEqual(created_node["versions"][0]["snapshot"]["templates"][0]["template"]["points"], [])

                        update_response = client.patch(
                            f"/mounting-nodes/{created_node['id']}",
                            json={
                                "templates": [
                                    {
                                        "template_id": created_node["templates"][0]["template_id"],
                                        "is_default": True,
                                        "template": {
                                            "template_id": created_node["templates"][0]["template_id"],
                                            "fitting_id": fitting.id,
                                            "name": "Main template",
                                            "template_type": "manual",
                                            "mounting_variant_key": "surface_mount",
                                            "is_default": True,
                                            "points": [
                                                {
                                                    "label": "P1",
                                                    "x_mm": 0,
                                                    "y_mm": 0,
                                                    "z_mm": 0,
                                                    "diameter_mm": 5,
                                                    "depth_mm": 13,
                                                    "side": "inner_face",
                                                    "target_panel": "vertical_panel",
                                                    "target_surface": "plane",
                                                    "target_side": "inner_face",
                                                    "operation": "drill",
                                                    "order_index": 0,
                                                    "quantity": 1,
                                                    "mirrored": False,
                                                }
                                            ],
                                        },
                                    }
                                ]
                            },
                            headers={"Authorization": "Bearer token"},
                        )

                        self.assertEqual(update_response.status_code, 200)
                        updated_node = update_response.json()["node"]
                        self.assertEqual([version["version_number"] for version in updated_node["versions"]], [2, 1])
                        self.assertEqual(updated_node["versions"][0]["snapshot"]["templates"][0]["template"]["points"][0]["label"], "P1")
                        self.assertEqual(updated_node["templates"][0]["points_count"], 1)

                        version_one_id = updated_node["versions"][1]["id"]
                        version_two_id = updated_node["versions"][0]["id"]
                        version_one_response = client.get(
                            f"/mounting-nodes/{created_node['id']}/versions/{version_one_id}",
                            headers={"Authorization": "Bearer token"},
                        )
                        version_two_response = client.get(
                            f"/mounting-nodes/{created_node['id']}/versions/{version_two_id}",
                            headers={"Authorization": "Bearer token"},
                        )

            self.assertEqual(version_one_response.status_code, 200)
            self.assertEqual(version_two_response.status_code, 200)
            self.assertEqual(version_one_response.json()["version"]["snapshot"]["templates"][0]["template"]["points"], [])
            self.assertEqual(
                len(version_two_response.json()["version"]["snapshot"]["templates"][0]["template"]["points"]),
                1,
            )
            self.assertEqual(
                session.query(MountingNodeVersionModel).filter(MountingNodeVersionModel.node_id == created_node["id"]).count(),
                2,
            )
        finally:
            session.close()
            engine.dispose()

    def test_delete_route_requires_mounting_nodes_delete_access(self) -> None:
        session, engine = self._build_session()
        try:
            app = self._build_app()
            owner = self._create_user(session, email="owner@example.com", role="free")
            fitting = self._create_fitting(session, name="Fit A", code="fit-a", article="A")
            service = MountingNodeService(session=session)
            node = service.create_mounting_node(
                {
                    "name": "Own node",
                    "items": [{"fitting_id": fitting.id, "quantity": 1}],
                },
                viewer_user_id=owner.id,
                viewer_role=owner.role,
            )

            app.dependency_overrides[auth_dependencies.require_current_user] = lambda: owner

            with patch.object(mounting_nodes_route, "EntitlementService", _EditOnlyEntitlementService):
                with patch.object(mounting_nodes_route, "MountingNodeService", return_value=service):
                    with TestClient(app) as client:
                        response = client.delete(
                            f"/mounting-nodes/{node['id']}",
                            headers={"Authorization": "Bearer token"},
                        )

            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["detail"]["error"], "Insufficient permissions")
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

    @staticmethod
    def _create_point(session, template_id: int, x_mm: float, y_mm: float, z_mm: float) -> None:
        point = FittingHolePointModel(
            template_id=template_id,
            label="Point",
            x_mm=x_mm,
            y_mm=y_mm,
            z_mm=z_mm,
            diameter_mm=7.0,
            depth_mm=None,
            side="left",
            operation="drill",
            order_index=0,
            quantity=1,
            mirrored=False,
        )
        session.add(point)
        session.commit()
        session.refresh(point)


if __name__ == "__main__":
    unittest.main()
