from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import auth as auth_dependencies
from api.routes import mounting_nodes as mounting_nodes_route


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

            def get_mounting_node(self, node_id):
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

    def _build_app(self) -> FastAPI:
        app = FastAPI()
        app.include_router(mounting_nodes_route.router, prefix="/mounting-nodes")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="free")
        return app


if __name__ == "__main__":
    unittest.main()
