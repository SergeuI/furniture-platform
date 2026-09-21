from __future__ import annotations

import unittest

from services.material_identity_validation_service import (
    validate_material_supplier_offer_identity,
)


class MaterialIdentityValidationServiceTests(unittest.TestCase):
    def test_validation_classifies_key_material_identity_scenarios(self) -> None:
        cases = [
            (
                "same_material_different_text",
                {
                    "name": "ДСП лам. Kronospan 5994 PD Синій Альбі 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "manufacturer_name": "Kronospan",
                    "category": "dsp",
                },
                {
                    "name": "ЛДСП KRONOSPAN 5994 PD СИНИЙ АЛЬБІ 2800X2070X18",
                    "dimensions": "2800X2070",
                    "thickness": "18 мм",
                    "brand": "KRONOSPAN",
                    "category": "dsp",
                },
                "compatible",
            ),
            (
                "k520_same_material_compatible",
                {
                    "name": "Kronospan K520 PD Смарагд Темний 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "manufacturer_name": "Kronospan",
                    "category": "dsp",
                },
                {
                    "name": "Kronospan K520 PD Смарагд Темний 2800x2070x18мм",
                    "dimensions": "2800X2070",
                    "thickness": "18 мм",
                    "category": "dsp",
                },
                "compatible",
            ),
            (
                "structure_conflict",
                {
                    "name": "Kronospan 5994 PD Синій Альбі 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "manufacturer_name": "Kronospan",
                    "category": "dsp",
                },
                {
                    "name": "Kronospan 5994 SU Синій Альбі 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "brand": "Kronospan",
                    "category": "dsp",
                },
                "conflict",
            ),
            (
                "k520_structure_conflict",
                {
                    "name": "Kronospan K520 PD Смарагд Темний 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "manufacturer_name": "Kronospan",
                    "category": "dsp",
                },
                {
                    "name": "Kronospan K520 SU Смарагд Темний 2800x2070x18мм",
                    "dimensions": "2800X2070",
                    "thickness": "18 мм",
                    "category": "dsp",
                },
                "conflict",
            ),
            (
                "thickness_conflict",
                {
                    "name": "Kronospan 5994 PD Синій Альбі 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "manufacturer_name": "Kronospan",
                    "category": "dsp",
                },
                {
                    "name": "Kronospan 5994 PD Синій Альбі 2800x2070x16",
                    "dimensions": "2800x2070",
                    "thickness": "16 мм",
                    "brand": "Kronospan",
                    "category": "dsp",
                },
                "conflict",
            ),
            (
                "dimension_conflict",
                {
                    "name": "Kronospan 5994 PD Синій Альбі 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "manufacturer_name": "Kronospan",
                    "category": "dsp",
                },
                {
                    "name": "Kronospan 5994 PD Синій Альбі 2750x1830x18",
                    "dimensions": "2750x1830",
                    "thickness": "18 мм",
                    "brand": "Kronospan",
                    "category": "dsp",
                },
                "conflict",
            ),
            (
                "manufacturer_conflict",
                {
                    "name": "Kronospan 5994 PD Синій Альбі 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "manufacturer_name": "Kronospan",
                    "category": "dsp",
                },
                {
                    "name": "Egger 5994 PD Синій Альбі 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "brand": "Egger",
                    "category": "dsp",
                },
                "conflict",
            ),
            (
                "decor_conflict",
                {
                    "name": "Kronospan 5994 PD Синій Альбі 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "manufacturer_name": "Kronospan",
                    "category": "dsp",
                },
                {
                    "name": "Kronospan 5981 PD Синій Альбі 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "brand": "Kronospan",
                    "category": "dsp",
                },
                "conflict",
            ),
            (
                "missing_structure_needs_review",
                {
                    "name": "Kronospan 5994 PD Синій Альбі 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "manufacturer_name": "Kronospan",
                    "category": "dsp",
                },
                {
                    "name": "Kronospan 5994 Синій Альбі 2800x2070x18",
                    "dimensions": "2800x2070",
                    "thickness": "18 мм",
                    "brand": "Kronospan",
                    "category": "dsp",
                },
                "compatible",
            ),
        ]

        for case_name, existing, incoming, expected_status in cases:
            with self.subTest(case=case_name):
                result = validate_material_supplier_offer_identity(existing, incoming, expected_category="dsp")
                self.assertEqual(result["status"], expected_status)

        conflict = validate_material_supplier_offer_identity(
            {
                "name": "Kronospan 5994 PD Синій Альбі 2800x2070x18",
                "dimensions": "2800x2070",
                "thickness": "18 мм",
                "manufacturer_name": "Kronospan",
                "category": "dsp",
            },
            {
                "name": "Kronospan 5994 SU Синій Альбі 2800x2070x18",
                "dimensions": "2800x2070",
                "thickness": "18 мм",
                "brand": "Kronospan",
                "category": "dsp",
            },
            expected_category="dsp",
        )
        self.assertEqual(conflict["status"], "conflict")
        self.assertTrue(any(item["field"] == "structure" for item in conflict["conflicts"]))

        needs_review = validate_material_supplier_offer_identity(
            {
                "name": "Kronospan 5994 PD Синій Альбі 2800x2070x18",
                "dimensions": "2800x2070",
                "thickness": "18 мм",
                "manufacturer_name": "Kronospan",
                "category": "dsp",
            },
            {
                "name": "Kronospan 5994 Синій Альбі 2800x2070x18",
                "dimensions": "2800x2070",
                "thickness": "18 мм",
                "brand": "Kronospan",
                "category": "dsp",
            },
            expected_category="dsp",
        )
        self.assertEqual(needs_review["status"], "compatible")
        self.assertIn("structure", needs_review["missing_fields"])

    def test_viyar_texture_is_enrichment_not_structure_conflict(self) -> None:
        result = validate_material_supplier_offer_identity(
            {
                "article": "69962",
                "name": "ДСП лам. Kronospan K351 RT Іржавий камінь",
                "dimensions": None,
                "thickness": "18 мм",
                "source": "viyar",
                "category": "dsp",
            },
            {
                "article": "69962",
                "name": "ДСП Kronospan K351 RT Іржавий камінь 2800x2070x18 мм",
                "dimensions": "2800x2070x18 мм",
                "thickness": "18 мм",
                "brand": "Kronospan",
                "category": "dsp",
                "characteristics": {
                    "Текстура поверхні (лицьова)": "SN",
                    "Товщина, мм": "18",
                    "Ширина, мм": "2070",
                    "Довжина, мм": "2800",
                },
            },
            expected_category="dsp",
        )

        self.assertEqual(result["status"], "compatible")
        self.assertNotIn("structure", {item["field"] for item in result["conflicts"]})

    def test_explicit_structure_conflict_remains_blocked(self) -> None:
        result = validate_material_supplier_offer_identity(
            {
                "name": "ДСП лам. Kronospan K351 RT Іржавий камінь",
                "thickness": "18 мм",
                "dimensions": "2800x2070",
                "category": "dsp",
            },
            {
                "name": "ДСП Kronospan K351 RT Іржавий камінь 2800x2070x18 мм",
                "thickness": "18 мм",
                "dimensions": "2800x2070x18 мм",
                "brand": "Kronospan",
                "category": "dsp",
                "characteristics": {"Structure": "DIFFERENT"},
            },
            expected_category="dsp",
        )

        self.assertEqual(result["status"], "conflict")
        self.assertEqual(
            [item["field"] for item in result["conflicts"]],
            ["structure"],
        )


if __name__ == "__main__":
    unittest.main()
