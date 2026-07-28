from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import auth as auth_dependencies
from api.routes import processing as processing_route


class _AllowedProjectEntitlementService:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def has_feature(self, current_user, feature_key: str) -> bool:
        return feature_key == "projects.view"


class _DeniedProjectEntitlementService:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def has_feature(self, current_user, feature_key: str) -> bool:
        return False


def _build_part_detail():
    return {
        "part": {
            "export_code": "DRW-FRONT",
            "part_name": "Drawer front",
            "category": "drawers",
            "width": 450,
            "height": 120,
            "quantity": 2,
            "material": "oak",
            "thickness": 18,
            "edge_top": "edge-a",
            "edge_bottom": "edge-a",
            "edge_left": "edge-a",
            "edge_right": "edge-a",
            "grain_direction": "horizontal",
            "notes": None,
        },
        "edges": [],
        "holes": [
            {
                "number": 1,
                "side": "front",
                "x": 24,
                "y": 40,
                "z": 0,
                "diameter": 5,
                "depth": 12,
                "type": "handle",
            }
        ],
        "grooves": [
            {
                "number": 1,
                "side": "front",
                "x": 0,
                "y": 12,
                "depth": 8,
                "width": 4,
                "length": 450,
                "type": "bottom_groove",
            }
        ],
        "quarters": [
            {
                "number": 1,
                "side": "bottom",
                "x": 0,
                "y": 0,
                "depth": 12,
                "width": 2,
                "length": 450,
                "radius": 0,
                "type": "bottom_quarter",
            }
        ],
    }


class ProcessingProjectPartOperationsPreviewApiTests(unittest.TestCase):
    def _build_app(self) -> FastAPI:
        app = FastAPI()
        app.include_router(processing_route.router, prefix="/processing")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="free")
        return app

    def test_operations_preview_returns_project_part_and_operations(self) -> None:
        app = self._build_app()
        project = SimpleNamespace(id="project-1", created_by_user_id="user-1")

        with patch.object(processing_route, "EntitlementService", _AllowedProjectEntitlementService):
            with patch.object(processing_route, "get_project", return_value=project) as get_project_mock:
                with patch.object(processing_route, "build_project_part_detail", return_value=_build_part_detail()) as detail_mock:
                    with TestClient(app) as client:
                        response = client.get(
                            "/processing/projects/project-1/parts/DRW-FRONT/operations-preview",
                            headers={"Authorization": "Bearer token"},
                        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["project"]["id"], "project-1")
        self.assertEqual(body["part"]["export_code"], "DRW-FRONT")
        self.assertEqual(body["count"], 3)
        self.assertEqual([item["source_type"] for item in body["operations"]], [
            "project_part_hole",
            "project_part_groove",
            "project_part_quarter",
        ])
        self.assertEqual(body["operations"][0]["operation_type"], "hole")
        self.assertEqual(body["operations"][0]["service_mapping"]["found"], False)
        self.assertEqual(body["operations"][1]["geometry"]["width_mm"], 4.0)
        self.assertEqual(body["operations"][2]["geometry"]["radius_mm"], 0.0)
        get_project_mock.assert_called_once_with("project-1")
        detail_mock.assert_called_once()

    def test_operations_preview_returns_404_for_missing_project(self) -> None:
        app = self._build_app()

        with patch.object(processing_route, "EntitlementService", _AllowedProjectEntitlementService):
            with patch.object(processing_route, "get_project", return_value=None):
                with TestClient(app) as client:
                    response = client.get(
                        "/processing/projects/project-404/parts/DRW-FRONT/operations-preview",
                        headers={"Authorization": "Bearer token"},
                    )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Project not found")

    def test_operations_preview_returns_404_for_foreign_project(self) -> None:
        app = self._build_app()
        project = SimpleNamespace(id="project-1", created_by_user_id="someone-else")

        with patch.object(processing_route, "EntitlementService", _AllowedProjectEntitlementService):
            with patch.object(processing_route, "get_project", return_value=project) as get_project_mock:
                with patch.object(processing_route, "build_project_part_detail") as detail_mock:
                    with TestClient(app) as client:
                        response = client.get(
                            "/processing/projects/project-1/parts/DRW-FRONT/operations-preview",
                            headers={"Authorization": "Bearer token"},
                        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Project not found")
        get_project_mock.assert_called_once_with("project-1")
        detail_mock.assert_not_called()

    def test_operations_preview_returns_403_without_project_view_access(self) -> None:
        app = self._build_app()

        with patch.object(processing_route, "EntitlementService", _DeniedProjectEntitlementService):
            with TestClient(app) as client:
                response = client.get(
                    "/processing/projects/project-1/parts/DRW-FRONT/operations-preview",
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "Insufficient permissions")
