from __future__ import annotations

import asyncio
import unittest

from services import viyar_parser


VIYAR_EDGE_PRODUCT_HTML = """
<html>
  <head>
    <title>141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU</title>
    <meta property="og:image" content="/store/Items/photos/ph185187.jpg">
  </head>
  <body>
    <h1>141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU</h1>
    <div data-owner-id="185187" data-brand="Rehau"></div>
    <div class="productLabel">В наявності</div>
    <div id="product_price">19.26 UAH / м.п.</div>
    <span class="text-unit">м.п.</span>
    <div class="productImageBlock__slider">
      <div class="js-productImage" data-src="/store/Items/photos/ph185187.jpg"></div>
    </div>
    <table>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Тип товару:</td>
        <td class="vr-block-char__value">ABS</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Ширина:</td>
        <td class="vr-block-char__value">22 мм</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Товщина:</td>
        <td class="vr-block-char__value">0.4 мм</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Колір:</td>
        <td class="vr-block-char__value">Смарагд зелений</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Напрямок текстури:</td>
        <td class="vr-block-char__value">Без напрямку</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Довжина рулону:</td>
        <td class="vr-block-char__value">300 м.п.</td>
      </tr>
    </table>
  </body>
</html>
"""


class ViyarEdgeProductPreviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_viyar_edge_product_returns_one_valid_candidate(self) -> None:
        async def fake_fetcher(page, url):
            self.assertEqual(url, "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/")
            return VIYAR_EDGE_PRODUCT_HTML

        result = await viyar_parser.preview_viyar_edge_product(
            "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/?from=card",
            page=object(),
            fetcher=fake_fetcher,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["preview_count"], 1)
        self.assertEqual(len(result["items"]), 1)
        item = result["items"][0]
        self.assertEqual(item["status"], "parsed")
        self.assertEqual(item["discovered_card"]["source_url"], "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/")
        self.assertEqual(item["canonical_candidate"]["manufacturer"], "Rehau")
        self.assertEqual(item["canonical_candidate"]["manufacturer_article"], "141342")
        self.assertEqual(item["canonical_candidate"]["width_mm"], 22.0)
        self.assertEqual(item["canonical_candidate"]["thickness_mm"], 0.4)
        self.assertEqual(item["supplier_offer_candidate"]["supplier"], "viyar")
        self.assertEqual(item["supplier_offer_candidate"]["source_url"], "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/")

    async def test_preview_viyar_edge_product_returns_controlled_error_when_parse_fails(self) -> None:
        async def fake_fetcher(page, url):
            return "<html><body><h1>Broken edge</h1></body></html>"

        result = await viyar_parser.preview_viyar_edge_product(
            "https://viyar.ua/ua/catalog/broken-edge/",
            page=object(),
            fetcher=fake_fetcher,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["preview_count"], 0)
        self.assertEqual(result["items"], [])
        self.assertIn("parsed", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
