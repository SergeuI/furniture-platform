from __future__ import annotations

from copy import deepcopy
import unittest

from services.project_processing_operation_adapter import ProjectProcessingOperationAdapter


class ProjectProcessingOperationAdapterTests(unittest.TestCase):
    def test_build_operations_maps_project_part_groups_without_mutation(self) -> None:
        part_detail = {
            "part": {
                "export_code": "DRW-FRONT",
                "part_name": "Drawer front",
                "category": "drawers",
            },
            "holes": [
                {
                    "number": 2,
                    "side": "front",
                    "x": 24,
                    "y": 40,
                    "z": 0,
                    "diameter": 5,
                    "depth": 12,
                    "type": "handle",
                },
                {
                    "number": 1,
                    "side": "front",
                    "x": 48,
                    "y": 40,
                    "z": 0,
                    "diameter": 5,
                    "depth": 12,
                    "type": "confirmat_face",
                },
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
        original = deepcopy(part_detail)

        operations = ProjectProcessingOperationAdapter().build_operations(
            project_id="project-1",
            part_identifier="DRW-FRONT",
            part_detail=part_detail,
        )

        self.assertEqual(len(operations), 4)
        self.assertEqual([item["operation_type"] for item in operations], ["hole", "hole", "groove", "quarter"])
        self.assertEqual([item["source_type"] for item in operations], [
            "project_part_hole",
            "project_part_hole",
            "project_part_groove",
            "project_part_quarter",
        ])
        self.assertEqual([item["order_index"] for item in operations], [1, 2, 3, 4])
        self.assertEqual([item["metadata"]["source_index"] for item in operations], [2, 1, 1, 1])
        self.assertEqual([item["label"] for item in operations], ["handle", "confirmat_face", "bottom_groove", "bottom_quarter"])
        self.assertEqual(operations[0]["id"], None)
        self.assertEqual(operations[0]["source_id"], None)
        self.assertEqual(operations[0]["template_id"], None)
        self.assertEqual(operations[0]["placement"]["x_mm"], 24)
        self.assertEqual(operations[0]["placement"]["y_mm"], 40)
        self.assertEqual(operations[0]["placement"]["z_mm"], 0)
        self.assertEqual(operations[0]["placement"]["side"], "front")
        self.assertIsNone(operations[0]["placement"]["target_panel"])
        self.assertIsNone(operations[0]["placement"]["coordinate_system"])
        self.assertEqual(operations[0]["geometry"]["diameter_mm"], 5.0)
        self.assertEqual(operations[0]["geometry"]["depth_mm"], 12.0)
        self.assertIsNone(operations[0]["geometry"]["is_through"])
        self.assertEqual(operations[2]["geometry"]["length_mm"], 450.0)
        self.assertEqual(operations[2]["geometry"]["width_mm"], 4.0)
        self.assertEqual(operations[2]["geometry"]["depth_mm"], 8.0)
        self.assertEqual(operations[3]["geometry"]["width_mm"], 2.0)
        self.assertEqual(operations[3]["geometry"]["depth_mm"], 12.0)
        self.assertEqual(operations[3]["geometry"]["length_mm"], 450.0)
        self.assertEqual(operations[3]["geometry"]["radius_mm"], 0.0)
        self.assertEqual(operations[0]["service_mapping"]["found"], False)
        self.assertEqual(operations[0]["production_effects"]["include_in_estimate"], False)
        self.assertEqual(operations[0]["metadata"]["project_id"], "project-1")
        self.assertEqual(operations[0]["metadata"]["part_identifier"], "DRW-FRONT")
        self.assertEqual(operations[0]["metadata"]["part_key"], "DRW-FRONT")
        self.assertEqual(operations[0]["metadata"]["part_type"], "drawers")
        self.assertEqual(operations[0]["metadata"]["part_name"], "Drawer front")
        self.assertEqual(operations[0]["metadata"]["source_data"]["type"], "handle")

        operations[0]["metadata"]["source_data"]["x"] = 999
        self.assertEqual(part_detail, original)

    def test_build_operations_supports_empty_groups(self) -> None:
        operations = ProjectProcessingOperationAdapter().build_operations(
            project_id=None,
            part_identifier=None,
            part_detail={
                "part": {},
                "holes": [],
                "grooves": [],
                "quarters": [],
            },
        )

        self.assertEqual(operations, [])
