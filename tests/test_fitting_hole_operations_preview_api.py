from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import auth as auth_dependencies
from api.routes import fitting_holes as fitting_holes_route


class _AllowedEntitlementService:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def has_feature(self, current_user, feature_key: str) -> bool:
        return feature_key == "fitting_holes.use"


class FittingHoleOperationsPreviewApiTests(unittest.TestCase):
    def test_operations_preview_returns_404_for_missing_template(self) -> None:
        app = FastAPI()
        app.include_router(fitting_holes_route.router, prefix="/fitting-holes")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")

        class MissingTemplateService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def get_template(self, template_id):
                return None

            def list_hole_points(self, template_id):
                raise AssertionError("list_hole_points should not be called for missing templates")

        with patch.object(fitting_holes_route, "EntitlementService", _AllowedEntitlementService):
            with patch.object(fitting_holes_route, "FittingHolesService", return_value=MissingTemplateService()):
                with TestClient(app) as client:
                    response = client.get(
                        "/fitting-holes/templates/999/operations-preview",
                        headers={"Authorization": "Bearer token"},
                    )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Template with id=999 does not exist")

    def test_operations_preview_returns_template_and_operations(self) -> None:
        app = FastAPI()
        app.include_router(fitting_holes_route.router, prefix="/fitting-holes")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")

        template = SimpleNamespace(
            id=22,
            fitting_id=7,
            name="Template",
            fitting=SimpleNamespace(code="F-1", article="A-1", fitting_type="hinge", fitting_group=None),
            bundle_key="bundle-x",
            bundle_name="Bundle X",
            bundle_order_index=1,
            template_type="manual",
            side="left",
            coordinate_system="2d",
            mounting_variant_key="surface_mount",
            is_default=False,
            notes="template note",
            is_active=True,
        )
        points = [
            SimpleNamespace(
                id=1,
                template_id=22,
                label="Point 1",
                x_mm=1.0,
                y_mm=2.0,
                z_mm=3.0,
                target_panel="panel-a",
                target_surface="inside",
                target_side="front",
                diameter_mm=5.0,
                service_drilling_rule_id=None,
                depth_mm=8.0,
                side="A",
                operation="drill",
                order_index=1,
                quantity=1,
                mirrored=False,
                notes=None,
            )
        ]

        class TemplateService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def get_template(self, template_id):
                if template_id == 22:
                    return template
                return None

            def list_hole_points(self, template_id):
                return points

        with patch.object(fitting_holes_route, "EntitlementService", _AllowedEntitlementService):
            with patch.object(fitting_holes_route, "FittingHolesService", return_value=TemplateService()):
                with patch.object(
                    fitting_holes_route.ProcessingOperationAdapter,
                    "build_operations",
                    return_value=[
                        {
                            "id": 1,
                            "operation_type": "hole",
                            "source_type": "fitting_hole_point",
                            "source_id": 1,
                            "template_id": 22,
                            "label": "Point 1",
                            "placement": {
                                "x_mm": 1.0,
                                "y_mm": 2.0,
                                "z_mm": 3.0,
                                "target_panel": "panel-a",
                                "target_surface": "inside",
                                "target_side": "front",
                                "side": "A",
                                "coordinate_system": "2d",
                                "mounting_variant_key": "surface_mount",
                            },
                            "geometry": {
                                "diameter_mm": 5.0,
                                "depth_mm": 8.0,
                                "is_through": False,
                                "operation": "drill",
                            },
                            "quantity": 1,
                            "mirrored": False,
                            "order_index": 1,
                            "service_mapping": {
                                "service_drilling_rule_id": None,
                                "resolved_service_catalog_item_id": None,
                                "resolution_source": "none",
                                "found": False,
                            },
                            "production_effects": {
                                "affects_cutting": False,
                                "affects_finished_contour": False,
                                "affects_edge_banding": False,
                                "requires_cnc": False,
                                "include_in_estimate": True,
                            },
                            "metadata": {
                                "source_label": "Point 1",
                                "template_notes": "template note",
                                "point_notes": None,
                                "fitting_code": "F-1",
                                "fitting_article": "A-1",
                                "fitting_category_code": "hinge",
                                "bundle_key": "bundle-x",
                                "bundle_name": "Bundle X",
                                "target_panel": "panel-a",
                                "target_surface": "inside",
                                "target_side": "front",
                                "source_data": {},
                            },
                        }
                    ],
                ):
                    with TestClient(app) as client:
                        response = client.get(
                            "/fitting-holes/templates/22/operations-preview",
                            headers={"Authorization": "Bearer token"},
                        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["template"]["id"], 22)
        self.assertEqual(len(body["operations"]), 1)
        self.assertEqual(body["operations"][0]["operation_type"], "hole")
        self.assertEqual(body["operations"][0]["placement"]["x_mm"], 1.0)

    def test_old_template_endpoint_contract_is_unchanged(self) -> None:
        app = FastAPI()
        app.include_router(fitting_holes_route.router, prefix="/fitting-holes")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")

        template = SimpleNamespace(
            id=44,
            fitting_id=9,
            name="Existing template",
            fitting=SimpleNamespace(code="F-9", article="A-9", fitting_type="hinge", fitting_group=None),
            bundle_key=None,
            bundle_name=None,
            bundle_order_index=0,
            template_type="manual",
            side=None,
            coordinate_system="2d",
            mounting_variant_key="surface_mount",
            is_default=False,
            notes=None,
            is_active=True,
        )

        class TemplateService:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def get_template(self, template_id):
                if template_id == 44:
                    return template
                return None

        with patch.object(fitting_holes_route, "EntitlementService", _AllowedEntitlementService):
            with patch.object(fitting_holes_route, "FittingHolesService", return_value=TemplateService()):
                with TestClient(app) as client:
                    response = client.get(
                        "/fitting-holes/templates/44",
                        headers={"Authorization": "Bearer token"},
                    )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["template"]["id"], 44)
