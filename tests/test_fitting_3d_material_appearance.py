import unittest

from pydantic import ValidationError

from schemas.catalog import Fitting3DAppearanceUpdateSchema


class Fitting3DMaterialAppearanceTests(unittest.TestCase):
    def test_one_material_override(self):
        payload = Fitting3DAppearanceUpdateSchema(material_overrides=[
            {"material_index": 0, "material_name": "Білий", "color": "#FFFFFF"},
        ])
        self.assertEqual(payload.material_overrides[0].material_index, 0)

    def test_two_material_overrides(self):
        payload = Fitting3DAppearanceUpdateSchema(material_overrides=[
            {"material_index": 0, "material_name": "Білий", "color": "#FFFFFF"},
            {"material_index": 1, "material_name": "Метал никель", "color": "#555555"},
        ])
        self.assertEqual(len(payload.material_overrides), 2)

    def test_reset_accepts_null_and_empty(self):
        self.assertIsNone(Fitting3DAppearanceUpdateSchema().material_overrides)
        self.assertEqual(Fitting3DAppearanceUpdateSchema(material_overrides=[]).material_overrides, [])

    def test_invalid_color_is_rejected(self):
        with self.assertRaises(ValidationError):
            Fitting3DAppearanceUpdateSchema(material_overrides=[
                {"material_index": 0, "material_name": "Білий", "color": "white"},
            ])

    def test_duplicate_material_identity_is_rejected(self):
        with self.assertRaises(ValidationError):
            Fitting3DAppearanceUpdateSchema(material_overrides=[
                {"material_index": 0, "material_name": "Білий", "color": "#FFFFFF"},
                {"material_index": 0, "material_name": "Білий", "color": "#111111"},
            ])

    def test_legacy_global_override_remains_supported(self):
        payload = Fitting3DAppearanceUpdateSchema(material_color_override="#FFFFFF")
        self.assertEqual(payload.material_color_override, "#FFFFFF")


if __name__ == "__main__":
    unittest.main()
