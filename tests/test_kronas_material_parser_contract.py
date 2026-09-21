from __future__ import annotations

from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from services import fitting_source_parser as parser
from services import material_catalog_service


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "kronas_material.html"
SOURCE_URL = "https://kronas.com.ua/catalog/materials/139610"
FINAL_URL = SOURCE_URL


class KronasMaterialParserContractTests(IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_html = FIXTURE_PATH.read_text(encoding="utf-8")

    def test_parse_kronas_html_contract(self) -> None:
        result = parser._parse_kronas_html(self.fixture_html, FINAL_URL)

        self.assertTrue(result["success"])
        self.assertEqual(result["article"], "139610")
        self.assertEqual(
            result["name"],
            "ДСП лам. Kronospan K520 PD Смарагд Темний 2800х2070х18мм",
        )
        self.assertEqual(result["brand"], "Kronospan")
        self.assertEqual(result["price"], 4220.0)
        self.assertEqual(result["currency"], "UAH")
        self.assertEqual(result["unit"], "лист")
        self.assertEqual(result["availability"], "В наявності")
        self.assertEqual(
            result["characteristics"],
            {
                "Производитель": "Kronospan",
                "Одиниця виміру": "лист",
                "Колір": "Смарагд Темний",
            },
        )
        self.assertEqual(
            result["image_url"],
            "https://kronas.com.ua/Media/images/catalog/original/139610.jpg",
        )
        self.assertEqual(
            result["image_urls"],
            [
                "https://kronas.com.ua/Media/images/catalog/original/139610.jpg",
                "https://cdn.example.test/kronas/139610-2.jpg",
                "https://kronas.com.ua/Media/images/catalog/original/139610-3.jpg",
            ],
        )
        self.assertEqual(result["final_url"], SOURCE_URL)

    async def test_fetch_material_by_source_url_live_traced_is_offline_and_preserves_contract(self) -> None:
        with patch.object(
            parser,
            "_fetch_html",
            new=AsyncMock(return_value=(200, FINAL_URL, self.fixture_html)),
        ) as fetch_mock:
            material, debug = await material_catalog_service.fetch_material_by_source_url_live_traced(
                SOURCE_URL,
                city="Київ",
            )

        fetch_mock.assert_awaited_once_with(SOURCE_URL)
        self.assertEqual(material["article"], "139610")
        self.assertEqual(
            material["name"],
            "ДСП лам. Kronospan K520 PD Смарагд Темний 2800х2070х18мм",
        )
        self.assertEqual(material["brand"], "Kronospan")
        self.assertEqual(material["price"], 4220.0)
        self.assertEqual(material["currency"], "UAH")
        self.assertEqual(material["unit"], "лист")
        self.assertEqual(material["availability"], "В наявності")
        self.assertEqual(material["characteristics"]["Колір"], "Смарагд Темний")
        self.assertEqual(
            material["image"],
            "https://kronas.com.ua/Media/images/catalog/original/139610.jpg",
        )
        self.assertEqual(material["image_urls"], [
            "https://kronas.com.ua/Media/images/catalog/original/139610.jpg",
            "https://cdn.example.test/kronas/139610-2.jpg",
            "https://kronas.com.ua/Media/images/catalog/original/139610-3.jpg",
        ])
        self.assertEqual(material["source_url"], SOURCE_URL)
        self.assertEqual(debug["source_url"], SOURCE_URL)
        self.assertEqual(debug["strategy"], "kronas_product_page")

    def _material_with_images(self, image_url: str | None, image_urls: list[str]) -> dict:
        return material_catalog_service._material_from_source_metadata(
            {
                "name": "Kronas material",
                "price": 1.0,
                "image_url": image_url,
                "image_urls": image_urls,
            },
            article="139610",
            source_url=SOURCE_URL,
        )

    def test_generic_material_image_urls_put_primary_first_without_duplicates(self) -> None:
        self.assertEqual(
            self._material_with_images("https://cdn.example.test/a.jpg", [
                "https://cdn.example.test/a.jpg",
                "https://cdn.example.test/b.jpg",
            ])["image_urls"],
            [
                "https://cdn.example.test/a.jpg",
                "https://cdn.example.test/b.jpg",
            ],
        )
        self.assertEqual(
            self._material_with_images("https://cdn.example.test/a.jpg", [
                "https://cdn.example.test/b.jpg",
                "https://cdn.example.test/c.jpg",
            ])["image_urls"],
            [
                "https://cdn.example.test/a.jpg",
                "https://cdn.example.test/b.jpg",
                "https://cdn.example.test/c.jpg",
            ],
        )
        self.assertEqual(
            self._material_with_images("https://cdn.example.test/a.jpg", [
                "https://cdn.example.test/b.jpg",
                "https://cdn.example.test/b.jpg",
                "https://cdn.example.test/c.jpg",
            ])["image_urls"],
            [
                "https://cdn.example.test/a.jpg",
                "https://cdn.example.test/b.jpg",
                "https://cdn.example.test/c.jpg",
            ],
        )
