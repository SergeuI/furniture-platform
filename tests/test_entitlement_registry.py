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
            "fitting_holes.use",
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

        registry_by_key = {feature.feature_key: feature for feature in SYSTEM_ENTITLEMENT_REGISTRY}
        expected_names = {
            "materials.view": "Доступ до каталогу матеріалів",
            "materials.create": "Додавання власних матеріалів",
            "materials.edit": "Редагування власних матеріалів",
            "materials.delete": "Видалення власних матеріалів",
            "fittings.view": "Доступ до каталогу фурнітури",
            "fittings.create": "Додавання власної фурнітури",
            "fittings.edit": "Редагування власної фурнітури",
            "fittings.delete": "Видалення власної фурнітури",
            "fitting_holes.use": "Доступ до присадки фурнітури",
        }
        for feature_key, expected_name in expected_names.items():
            self.assertEqual(registry_by_key[feature_key].name_uk, expected_name)

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
