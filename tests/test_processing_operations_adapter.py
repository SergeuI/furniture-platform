from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.processing_operation_adapter import ProcessingOperationAdapter


class ProcessingOperationAdapterTests(unittest.TestCase):
    def test_point_is_converted_to_hole_operation_without_mutating_geometry(self) -> None:
        template = SimpleNamespace(
            id=10,
            coordinate_system="2d",
            mounting_variant_key="surface_mount",
            notes="template note",
            bundle_key="bundle-a",
            bundle_name="Bundle A",
            fitting=SimpleNamespace(
                code="H1",
                article="ART-1",
                fitting_type="hinge",
                fitting_group="hardware",
            ),
        )
        points = [
            SimpleNamespace(
                id=2,
                template_id=10,
                label="Lower hole",
                x_mm=15.0,
                y_mm=25.0,
                z_mm=35.0,
                target_panel="left",
                target_surface="inside",
                target_side="front",
                diameter_mm=5.0,
                depth_mm=12.5,
                side="A",
                operation="drill",
                order_index=7,
                quantity=3,
                mirrored=True,
                service_drilling_rule_id=99,
                notes="point note",
            )
        ]

        with patch(
            "services.processing_operation_adapter.build_fitting_hole_service_preview",
            return_value={
                "groups": [
                    {
                        "operation": "drill",
                        "diameter_mm": 5.0,
                        "depth_mm": 12.5,
                        "matched_service_id": "svc-10",
                        "match_source": "rule",
                    }
                ]
            },
        ) as preview_mock:
            operations = ProcessingOperationAdapter().build_operations(
                template,
                points,
                current_user_id="user-1",
            )

        self.assertEqual(preview_mock.call_count, 1)
        self.assertEqual(len(operations), 1)
        operation = operations[0]
        self.assertEqual(operation["operation_type"], "hole")
        self.assertEqual(operation["source_type"], "fitting_hole_point")
        self.assertEqual(operation["source_id"], 2)
        self.assertEqual(operation["template_id"], 10)
        self.assertEqual(operation["label"], "Lower hole")
        self.assertEqual(operation["placement"]["x_mm"], 15.0)
        self.assertEqual(operation["placement"]["y_mm"], 25.0)
        self.assertEqual(operation["placement"]["z_mm"], 35.0)
        self.assertEqual(operation["placement"]["target_panel"], "left")
        self.assertEqual(operation["placement"]["target_surface"], "inside")
        self.assertEqual(operation["placement"]["target_side"], "front")
        self.assertEqual(operation["placement"]["side"], "A")
        self.assertEqual(operation["placement"]["coordinate_system"], "2d")
        self.assertEqual(operation["placement"]["mounting_variant_key"], "surface_mount")
        self.assertEqual(operation["geometry"]["diameter_mm"], 5.0)
        self.assertEqual(operation["geometry"]["depth_mm"], 12.5)
        self.assertFalse(operation["geometry"]["is_through"])
        self.assertEqual(operation["geometry"]["operation"], "drill")
        self.assertEqual(operation["quantity"], 3)
        self.assertTrue(operation["mirrored"])
        self.assertEqual(operation["order_index"], 7)
        self.assertEqual(operation["service_mapping"]["service_drilling_rule_id"], 99)
        self.assertEqual(operation["service_mapping"]["resolved_service_catalog_item_id"], "svc-10")
        self.assertEqual(operation["service_mapping"]["resolution_source"], "rule")
        self.assertTrue(operation["service_mapping"]["found"])
        self.assertFalse(operation["production_effects"]["affects_cutting"])
        self.assertFalse(operation["production_effects"]["affects_finished_contour"])
        self.assertFalse(operation["production_effects"]["affects_edge_banding"])
        self.assertFalse(operation["production_effects"]["requires_cnc"])
        self.assertTrue(operation["production_effects"]["include_in_estimate"])
        self.assertEqual(operation["metadata"]["source_label"], "Lower hole")
        self.assertEqual(operation["metadata"]["point_notes"], "point note")

    def test_operations_are_sorted_by_order_index_and_missing_service_is_safe(self) -> None:
        template = SimpleNamespace(
            id=11,
            coordinate_system="2d",
            mounting_variant_key="surface_mount",
            notes=None,
            bundle_key=None,
            bundle_name=None,
            fitting=None,
        )
        points = [
            SimpleNamespace(
                id=20,
                template_id=11,
                label="Second",
                x_mm=1.0,
                y_mm=2.0,
                z_mm=3.0,
                target_panel=None,
                target_surface=None,
                target_side=None,
                diameter_mm=6.0,
                depth_mm=None,
                side=None,
                operation="through_drill",
                order_index=20,
                quantity=1,
                mirrored=False,
                service_drilling_rule_id=None,
                notes=None,
            ),
            SimpleNamespace(
                id=10,
                template_id=11,
                label="First",
                x_mm=4.0,
                y_mm=5.0,
                z_mm=6.0,
                target_panel=None,
                target_surface=None,
                target_side=None,
                diameter_mm=6.0,
                depth_mm=8.0,
                side=None,
                operation="drill",
                order_index=10,
                quantity=2,
                mirrored=False,
                service_drilling_rule_id=None,
                notes=None,
            ),
        ]

        with patch(
            "services.processing_operation_adapter.build_fitting_hole_service_preview",
            return_value={"groups": []},
        ):
            operations = ProcessingOperationAdapter().build_operations(
                template,
                points,
                current_user_id=None,
            )

        self.assertEqual([item["id"] for item in operations], [10, 20])
        self.assertEqual(operations[0]["geometry"]["diameter_mm"], 6.0)
        self.assertEqual(operations[0]["geometry"]["depth_mm"], 8.0)
        self.assertFalse(operations[0]["geometry"]["is_through"])
        self.assertTrue(operations[1]["geometry"]["is_through"])
        self.assertFalse(operations[0]["service_mapping"]["found"])
        self.assertIsNone(operations[0]["service_mapping"]["resolved_service_catalog_item_id"])
        self.assertEqual(operations[0]["service_mapping"]["resolution_source"], "none")
