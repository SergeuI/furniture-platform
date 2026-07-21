from __future__ import annotations

import unittest

from services.entitlement_registry import (
    EntitlementRegistryFeature,
    SYSTEM_ENTITLEMENT_REGISTRY,
    get_system_entitlement_registry_keys,
)


class EntitlementRegistryTests(unittest.TestCase):
    def test_registry_contains_expected_system_features(self) -> None:
        expected_keys = {
            "materials.view",
            "materials.create",
            "materials.edit",
            "materials.delete",
            "fittings.view",
            "fittings.create",
            "fittings.edit",
            "fittings.delete",
            "projects.view",
            "projects.create",
            "projects.edit",
            "projects.delete",
            "cutting.use",
            "ai.image_analysis",
        }

        self.assertEqual(len(SYSTEM_ENTITLEMENT_REGISTRY), len(expected_keys))
        self.assertEqual(set(get_system_entitlement_registry_keys()), expected_keys)
        self.assertTrue(all(feature.value_type == "boolean" for feature in SYSTEM_ENTITLEMENT_REGISTRY))

    def test_registry_validation_rejects_invalid_definitions(self) -> None:
        with self.assertRaises(ValueError):
            EntitlementRegistryFeature(
                feature_key="Bad Key",
                name_uk="Невалідне право",
                description_uk="Опис",
                category="test",
                value_type="boolean",
            )

        with self.assertRaises(ValueError):
            EntitlementRegistryFeature(
                feature_key="test.enum",
                name_uk="Enum",
                description_uk="Опис",
                category="test",
                value_type="enum",
                enum_options_json=(),
            )

        with self.assertRaises(ValueError):
            EntitlementRegistryFeature(
                feature_key="test.non_enum",
                name_uk="Boolean",
                description_uk="Опис",
                category="test",
                value_type="boolean",
                enum_options_json=("unexpected",),
            )


if __name__ == "__main__":
    unittest.main()
