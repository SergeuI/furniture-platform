from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import auth as auth_dependencies
from api.routes import processing as processing_route


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


class ProcessingOperationTypesApiTests(unittest.TestCase):
    def test_operation_types_returns_nine_items_for_allowed_user(self) -> None:
        app = FastAPI()
        app.include_router(processing_route.router, prefix="/processing")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="free")

        with patch.object(processing_route, "EntitlementService", _AllowedEntitlementService):
            with TestClient(app) as client:
                response = client.get(
                    "/processing/operation-types",
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["count"], 9)
        self.assertEqual([item["key"] for item in body["items"]][0], "hole")
        self.assertEqual([item["key"] for item in body["items"]][-1], "manual_operation")

    def test_operation_types_returns_403_without_access(self) -> None:
        app = FastAPI()
        app.include_router(processing_route.router, prefix="/processing")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-2", role="free")

        with patch.object(processing_route, "EntitlementService", _DeniedEntitlementService):
            with TestClient(app) as client:
                response = client.get(
                    "/processing/operation-types",
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "Insufficient permissions")

