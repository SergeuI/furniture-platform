from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.maintenance_preview import (
    HERO_IMAGE_PATH,
    TEMPLATE_PATH,
    create_preview_file,
    load_hero_data_uri,
    load_template,
    render_maintenance_preview_html,
)


class MaintenancePreviewTests(unittest.TestCase):
    def test_template_loads(self) -> None:
        template = load_template()
        self.assertIn("{{hero_src}}", template)
        self.assertIn("{{maintenance_message}}", template)
        self.assertIn("{{eta}}", template)
        self.assertNotIn("{{message}}", template)
        self.assertNotIn("footer-note", template)

    def test_hero_data_uri_uses_local_asset(self) -> None:
        hero_uri = load_hero_data_uri()
        self.assertTrue(HERO_IMAGE_PATH.exists())
        self.assertTrue(hero_uri.startswith("data:image/png;base64,"))
        self.assertGreater(len(hero_uri), 100)

    def test_render_escapes_user_input_and_keeps_template_unchanged(self) -> None:
        before = TEMPLATE_PATH.read_text(encoding="utf-8")
        rendered = render_maintenance_preview_html(
            message="<script>alert(1)</script>",
            eta="5 < 6",
        )
        after = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertEqual(before, after)
        self.assertIn("Ведуться технічні роботи", rendered)
        self.assertIn("MP Furniture Calculator", rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)
        self.assertIn("5 &lt; 6", rendered)
        self.assertIn("data:image/png;base64,", rendered)
        self.assertNotIn("{{hero_src}}", rendered)
        self.assertNotIn("стабільнішою та зручнішою", rendered)
        self.assertNotIn("<script>alert(1)</script>", rendered)

    def test_preview_file_is_created_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "maintenance-preview.html"
            preview_path = create_preview_file(
                message="Готово",
                eta="Скоро",
                output_path=output,
                open_in_browser=False,
            )

            self.assertEqual(preview_path, output)
            self.assertTrue(preview_path.exists())
            self.assertGreater(preview_path.stat().st_size, 0)
            preview_text = preview_path.read_text(encoding="utf-8")
            self.assertIn("Готово", preview_text)
            self.assertIn("Скоро", preview_text)
            self.assertIn("Оновити сторінку", preview_text)
            self.assertNotIn("Дякуємо за розуміння", preview_text)


if __name__ == "__main__":
    unittest.main()
