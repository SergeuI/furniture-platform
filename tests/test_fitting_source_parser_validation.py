from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from services import fitting_source_parser as parser


class FittingSourceParserValidationTests(IsolatedAsyncioTestCase):
    async def test_source_preview_rejects_error_page(self) -> None:
        error_html = """
            <html>
              <head><title>Error 404</title></head>
              <body>
                <h1>Error 404</h1>
                <p>Not Found</p>
              </body>
            </html>
        """

        with patch.object(
            parser,
            "_fetch_html",
            new=AsyncMock(return_value=(200, "https://viyar.ua/ua/catalog/missing", error_html)),
        ):
            result = await parser.parse_fitting_source_metadata("https://viyar.ua/ua/catalog/missing")

        self.assertFalse(result["success"])
        self.assertIn("не вдалося", result["error"].lower())

    async def test_source_preview_accepts_valid_viyar_product(self) -> None:
        valid_html = """
            <html>
              <head>
                <title>VIYAR Product</title>
                <meta property="og:image" content="https://cdn.example.com/image.jpg">
              </head>
              <body>
                <h1 class="text text-weight-dark">VIYAR Product</h1>
                <span class="text-code text-weight-bolder">123456</span>
                <span id="product_price">99.50</span>
              </body>
            </html>
        """

        with patch.object(
            parser,
            "_fetch_html",
            new=AsyncMock(return_value=(200, "https://viyar.ua/ua/catalog/product", valid_html)),
        ):
            result = await parser.parse_fitting_source_metadata("https://viyar.ua/ua/catalog/product")

        self.assertTrue(result["success"])
        self.assertEqual(result["name"], "VIYAR Product")
        self.assertEqual(result["article"], "123456")
        self.assertEqual(result["image_url"], "https://cdn.example.com/image.jpg")
