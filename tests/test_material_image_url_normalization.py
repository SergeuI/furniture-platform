from __future__ import annotations

import unittest

from services.material_catalog_service import normalize_material_gallery_image_url


class MaterialImageUrlNormalizationTests(unittest.TestCase):
    def test_unwraps_viyar_fit_contain_target(self) -> None:
        self.assertEqual(
            normalize_material_gallery_image_url(
                "https://www.viyar.ua/fit=contain/https://cdn.example.com/a.jpg"
            ),
            "https://cdn.example.com/a.jpg",
        )

    def test_unwraps_viyar_target_on_viyar_host(self) -> None:
        self.assertEqual(
            normalize_material_gallery_image_url(
                "https://www.viyar.ua/fit=contain/https://www.viyar.ua/upload/photos/a.jpg"
            ),
            "https://viyar.ua/upload/photos/a.jpg",
        )

    def test_keeps_direct_url_and_rejects_empty_value(self) -> None:
        direct_url = "https://cdn.example.com/a.jpg"
        self.assertEqual(normalize_material_gallery_image_url(direct_url), direct_url)
        self.assertIsNone(normalize_material_gallery_image_url(""))


if __name__ == "__main__":
    unittest.main()
