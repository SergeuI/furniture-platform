from __future__ import annotations

import unittest

from services.processing_operation_registry import list_processing_operation_types


class ProcessingOperationRegistryTests(unittest.TestCase):
    def test_registry_contains_nine_stable_types(self) -> None:
        items = list_processing_operation_types()

        self.assertEqual(len(items), 9)
        self.assertEqual(
            [item["key"] for item in items],
            [
                "hole",
                "groove",
                "quarter",
                "pocket",
                "rectangular_cutout",
                "contour_cutout",
                "radius",
                "milling",
                "manual_operation",
            ],
        )
        self.assertEqual(items[0]["status"], "available")
        self.assertEqual(items[0]["version"], 1)
        self.assertTrue(items[0]["capabilities"]["template_editor"])
        self.assertTrue(items[0]["capabilities"]["operations_preview"])
        self.assertTrue(items[0]["capabilities"]["preview_3d"])
        self.assertTrue(items[0]["capabilities"]["service_mapping"])
        self.assertFalse(items[0]["capabilities"]["estimate_export"])
        self.assertFalse(items[0]["capabilities"]["cutting_effect"])

        for item in items[1:]:
            self.assertEqual(item["status"], "planned")
            self.assertEqual(item["version"], 1)
            self.assertFalse(any(item["capabilities"].values()))

    def test_registry_fields_are_stable_and_non_overlapping(self) -> None:
        items = list_processing_operation_types()

        for item in items:
            required_fields = item["required_fields"]
            optional_fields = item["optional_fields"]

            self.assertEqual(len(required_fields), len(set(required_fields)))
            self.assertEqual(len(optional_fields), len(set(optional_fields)))
            self.assertEqual(set(required_fields).intersection(optional_fields), set())
            self.assertGreater(len(required_fields), 0)
            self.assertGreaterEqual(len(optional_fields), 0)
