from __future__ import annotations

import asyncio
import inspect
import unittest

from services import viyar_parser


VIYAR_EDGE_DETAIL_HTML = """
<html>
  <head>
    <title>141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU</title>
    <meta property="og:image" content="/store/Items/photos/ph185187.jpg">
  </head>
  <body>
    <h1>141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU</h1>
    <div data-owner-id="185187" data-brand="Rehau"></div>
    <div class="productLabel">СКОРО У ПРОДАЖУ</div>
    <div id="product_price">19.26 UAH / м.п.</div>
    <span class="text-unit">м.п.</span>
    <div class="productImageBlock__slider">
      <div class="js-productImage" data-src="/store/Items/photos/ph185187.jpg">
        <img src="/store/Items/photos/ph185187.jpg" alt="141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU">
      </div>
    </div>
    <table>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Тип товару:</td>
        <td class="vr-block-char__value">ABS</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Матеріал:</td>
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
        <td class="vr-block-char__name">Виробник:</td>
        <td class="vr-block-char__value">Rehau</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Країна виробник:</td>
        <td class="vr-block-char__value">Німеччина</td>
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


VIYAR_EDGE_DETAIL_MINIMAL_HTML = """
<html>
  <body>
    <h1>141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU</h1>
    <div data-owner-id="185187" data-brand="Rehau"></div>
    <div class="productImageBlock__slider">
      <div class="js-productImage" data-src="/store/Items/photos/ph185187.jpg"></div>
    </div>
  </body>
</html>
"""


VIYAR_EDGE_DETAIL_K533_LIKE_HTML = """
<html>
  <head>
    <title>2941W Крайка ABS Пінія темно-коричнева 23x0,8мм (150 м.п.) REHAU</title>
    <meta property="og:image" content="/store/Items/photos/ph152446.jpg">
  </head>
  <body>
    <h1>2941W Крайка ABS Пінія темно-коричнева 23x0,8мм (150 м.п.) REHAU</h1>
    <div data-owner-id="152446"></div>
    <div class="productLabel">В наявності</div>
    <div id="product_price">12.34 UAH / м.п.</div>
    <span class="text-unit">м.п.</span>
    <table>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Тип товару:</td>
        <td class="vr-block-char__value">ABS</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Ширина:</td>
        <td class="vr-block-char__value">23 мм</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Товщина:</td>
        <td class="vr-block-char__value">0.8 мм</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Довжина рулону:</td>
        <td class="vr-block-char__value">150 м.п.</td>
      </tr>
    </table>
  </body>
</html>
"""


VIYAR_EDGE_DETAIL_NO_IMAGE_HTML = """
<html>
  <body>
    <h1>2941W Крайка ABS Пінія темно-коричнева 23x0,8мм (150 м.п.) REHAU</h1>
    <div data-owner-id="152446"></div>
    <div class="productLabel">В наявності</div>
    <div id="product_price">12.34 UAH / м.п.</div>
    <span class="text-unit">м.п.</span>
    <table>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Тип товару:</td>
        <td class="vr-block-char__value">ABS</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Ширина:</td>
        <td class="vr-block-char__value">23 мм</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Товщина:</td>
        <td class="vr-block-char__value">0.8 мм</td>
      </tr>
      <tr class="vr-block-char__tr">
        <td class="vr-block-char__name">Довжина рулону:</td>
        <td class="vr-block-char__value">150 м.п.</td>
      </tr>
    </table>
  </body>
</html>
"""


VIYAR_EDGE_DETAIL_TECHNICAL_WIDTH_PRIORITY_HTML = """
<html>
  <body>
    <h1>5000W Крайка ABS Умовний Декор 23x0,8мм (150 м.п.) REHAU</h1>
    <div data-owner-id="999999" data-brand="Rehau"></div>
    <div class="productLabel">В наявності</div>
    <div id="product_price">12.34 UAH / м.п.</div>
    <span class="text-unit">м.п.</span>
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
        <td class="vr-block-char__value">0.8 мм</td>
      </tr>
    </table>
  </body>
</html>
"""


VIYAR_EDGE_DETAIL_184339_IMAGE_FILTER_HTML = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "160520 HU Крайка ABS Зелена темно-смарагдова XK 22х0,45мм (200 м.п.) Hranipe",
        "sku": "184339",
        "image": []
      }
    </script>
  </head>
  <body>
    <h1>160520 HU Крайка ABS Зелена темно-смарагдова XK 22х0,45мм (200 м.п.) Hranipe</h1>
    <div data-owner-id="184339" data-brand="Hranipex"></div>
    <div class="productImageBlock__slider">
      <img src="/svg/bonus.svg" alt="">
      <img src="/upload/photos/ph184339.jpg" alt="160520 HU Крайка ABS Зелена темно-смарагдова XK 22х0,45мм Hranipe">
      <img src="/appImages/photoNotFound.jpg" alt="160520 HU Крайка ABS Зелена темно-смарагдова XK 22х0,45мм Hranipe">
    </div>
    <img src="https://viyar.ua/cdn-cgi/image/w=400/https://viyar.ua/upload/photos/ph184339.jpg" alt="product thumbnail">
  </body>
</html>
"""


class ViyarEdgeDetailParserTests(unittest.TestCase):
    def test_extracts_alphanumeric_manufacturer_articles_from_current_viyar_titles(self) -> None:
        self.assertEqual(viyar_parser._extract_viyar_edge_product_code("D4/34 Крайка ПВХ"), "D4/34")
        self.assertEqual(viyar_parser._extract_viyar_edge_product_code("D4003 CD Крайка ПВХ"), "D4003")
        self.assertEqual(viyar_parser._extract_viyar_edge_product_code("Крайка ПВХ K003 для меблів"), "K003")
        self.assertEqual(viyar_parser._extract_viyar_edge_product_code("k003-dub-kraft-zolotiy"), "k003")

    def test_does_not_treat_dimensions_as_unknown_manufacturer(self) -> None:
        result = viyar_parser.parse_viyar_edge_detail(
            "<html><h1>Крайка ПВХ K003 21x0,45 мм</h1></html>",
            source_url="https://viyar.ua/ua/catalog/k003-dub-kraft-zolotiy/",
        )
        self.assertIsNone(result["canonical_candidate"]["manufacturer"])

    def test_parse_viyar_edge_detail_rejects_bonus_and_selects_article_matching_product_image(self) -> None:
        result = viyar_parser.parse_viyar_edge_detail(
            VIYAR_EDGE_DETAIL_184339_IMAGE_FILTER_HTML,
            source_url="https://viyar.ua/ua/catalog/160520-hu-krayka-abs-zelena-temno-smaragdova-xk-22kh0-45mm-200-m-p-hranipe/",
        )

        canonical = result["canonical_candidate"]
        self.assertEqual(canonical["image_url"], "https://viyar.ua/upload/photos/ph184339.jpg")
        self.assertEqual(canonical["image_urls"], ["https://viyar.ua/upload/photos/ph184339.jpg"])
        self.assertNotIn("bonus.svg", canonical["image_url"])
        self.assertNotIn("photoNotFound", canonical["image_url"])

    def test_image_contract_prefers_article_product_image_over_generic_and_bonus(self) -> None:
        html = """
        <html><body>
          <h1>160520 HU Крайка ABS 22х0,45мм Hranipex</h1>
          <div data-owner-id="184339" data-brand="Hranipex"></div>
          <div class="productImageBlock__slider">
            <img src="/svg/bonus.svg">
            <img src="/upload/iblock/category-random.jpg">
            <img src="/upload/photos/ph184339.jpg">
            <img src="/appImages/photoNotFound.jpg">
          </div>
        </body></html>
        """

        result = viyar_parser.parse_viyar_edge_detail(html)

        self.assertEqual(result["canonical_candidate"]["image_url"], "https://viyar.ua/upload/photos/ph184339.jpg")

    def test_image_contract_returns_no_image_when_only_generic_assets_exist(self) -> None:
        html = """
        <html><body>
          <h1>160520 HU Крайка ABS 22х0,45мм Hranipex</h1>
          <div data-owner-id="184339" data-brand="Hranipex">
            <img src="/upload/iblock/category-random.jpg">
            <img src="/svg/bonus.svg">
            <img src="/appImages/photoNotFound.jpg">
          </div>
        </body></html>
        """

        result = viyar_parser.parse_viyar_edge_detail(html)

        self.assertIsNone(result["canonical_candidate"]["image_url"])
        self.assertEqual(result["canonical_candidate"]["image_urls"], [])

    def test_image_contract_accepts_explicit_matching_recommended_card_fallback(self) -> None:
        html = """
        <html><body>
          <h1>160520 HU Крайка ABS 22х0,45мм Hranipex</h1>
          <div data-owner-id="184339" data-brand="Hranipex"></div>
        </body></html>
        """

        result = viyar_parser.parse_viyar_edge_detail(
            html,
            fallback_image_url="https://viyar.ua/upload/photos/ph184339.jpg",
        )

        self.assertEqual(result["canonical_candidate"]["image_url"], "https://viyar.ua/upload/photos/ph184339.jpg")

    def test_image_contract_rejects_recommended_card_fallback_for_another_article(self) -> None:
        html = """
        <html><body>
          <h1>160520 HU Крайка ABS 22х0,45мм Hranipex</h1>
          <div data-owner-id="184339" data-brand="Hranipex"></div>
        </body></html>
        """

        result = viyar_parser.parse_viyar_edge_detail(
            html,
            fallback_image_url="https://viyar.ua/upload/photos/ph152446.jpg",
        )

        self.assertIsNone(result["canonical_candidate"]["image_url"])

    def test_parse_viyar_edge_detail_extracts_canonical_and_supplier_candidates(self) -> None:
        result = viyar_parser.parse_viyar_edge_detail(
            VIYAR_EDGE_DETAIL_HTML,
            source_url="https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
        )

        canonical = result["canonical_candidate"]
        supplier = result["supplier_offer_candidate"]

        self.assertEqual(canonical["manufacturer"], "Rehau")
        self.assertEqual(canonical["manufacturer_article"], "141342")
        self.assertEqual(canonical["name"], "141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU")
        self.assertEqual(canonical["material_type"], "ABS")
        self.assertIsNone(canonical["technology_code"])
        self.assertEqual(canonical["color"], "Смарагд зелений")
        self.assertEqual(canonical["width_mm"], 22.0)
        self.assertEqual(canonical["thickness_mm"], 0.4)
        self.assertEqual(canonical["finish"], "Без напрямку")
        self.assertEqual(canonical["image_url"], "https://viyar.ua/store/Items/photos/ph185187.jpg")

        self.assertEqual(supplier["supplier"], "viyar")
        self.assertEqual(supplier["article"], "185187")
        self.assertEqual(supplier["external_product_id"], None)
        self.assertEqual(
            supplier["source_url"],
            "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
        )
        self.assertEqual(supplier["unit"], "м.п.")
        self.assertEqual(supplier["availability"], "Скоро у продажу")
        self.assertEqual(supplier["price"], 19.26)
        self.assertEqual(supplier["currency"], "UAH")
        self.assertEqual(supplier["package_length"], "300 м.п.")
        self.assertEqual(supplier["source_payload"]["brand"], "Rehau")
        self.assertIn("characteristics", supplier["source_payload"])

    def test_parse_viyar_edge_detail_extracts_k533_like_candidate_from_title_and_og_image(self) -> None:
        result = viyar_parser.parse_viyar_edge_detail(
            VIYAR_EDGE_DETAIL_K533_LIKE_HTML,
            source_url="https://viyar.ua/ua/catalog/2941w_kromka_abs_piniya_temno_korichnevaya_23kh0_8mm_150_m_p_rehau/",
        )

        canonical = result["canonical_candidate"]
        supplier = result["supplier_offer_candidate"]

        self.assertEqual(canonical["manufacturer"], "Rehau")
        self.assertEqual(canonical["manufacturer_article"], "2941W")
        self.assertEqual(canonical["material_type"], "ABS")
        self.assertEqual(canonical["width_mm"], 23.0)
        self.assertEqual(canonical["thickness_mm"], 0.8)
        self.assertEqual(canonical["image_url"], "https://viyar.ua/store/Items/photos/ph152446.jpg")
        self.assertEqual(supplier["article"], "152446")
        self.assertEqual(supplier["source_url"], "https://viyar.ua/ua/catalog/2941w_kromka_abs_piniya_temno_korichnevaya_23kh0_8mm_150_m_p_rehau/")
        self.assertEqual(supplier["unit"], "м.п.")

    def test_parse_viyar_edge_detail_handles_missing_optional_image_safely(self) -> None:
        result = viyar_parser.parse_viyar_edge_detail(VIYAR_EDGE_DETAIL_NO_IMAGE_HTML)

        canonical = result["canonical_candidate"]
        supplier = result["supplier_offer_candidate"]

        self.assertEqual(canonical["manufacturer"], "Rehau")
        self.assertEqual(canonical["manufacturer_article"], "2941W")
        self.assertEqual(canonical["material_type"], "ABS")
        self.assertEqual(canonical["width_mm"], 23.0)
        self.assertEqual(canonical["thickness_mm"], 0.8)
        self.assertIsNone(canonical["image_url"])
        self.assertEqual(supplier["article"], "152446")
        self.assertEqual(supplier["unit"], "м.п.")

    def test_parse_viyar_edge_detail_prefers_technical_width_over_title_width(self) -> None:
        result = viyar_parser.parse_viyar_edge_detail(VIYAR_EDGE_DETAIL_TECHNICAL_WIDTH_PRIORITY_HTML)

        canonical = result["canonical_candidate"]

        self.assertEqual(canonical["manufacturer"], "Rehau")
        self.assertEqual(canonical["manufacturer_article"], "5000W")
        self.assertEqual(canonical["material_type"], "ABS")
        self.assertEqual(canonical["width_mm"], 22.0)
        self.assertEqual(canonical["thickness_mm"], 0.8)

    def test_parse_viyar_current_markup_uses_json_ld_and_semantic_labels(self) -> None:
        html = """
        <html>
          <head>
            <script type="application/ld+json">
              {
                "@type": "Product",
                "name": "2941W Крайка ABS Пінія темно-коричнева 23x0,8мм (150 м.п.) REHAU",
                "sku": "152446",
                "image": ["https://viyar.ua/upload/photos/ph152446.jpg", "https://viyar.ua/upload/photos/ph152446.jpg"],
                "brand": {"@type": "Brand", "name": "Rehau"},
                "offers": {"price": "42.24", "priceCurrency": "UAH", "availability": "https://schema.org/InStock"}
              }
            </script>
          </head>
          <body>
            <h1>2941W Крайка ABS Пінія темно-коричнева 23x0,8мм (150 м.п.) REHAU</h1>
            <div class="availability-badge">В наявності</div>
            <div class="price-block">42.24 ₴ / м.п.</div>
            <div title="Товщина, мм"><h3>Товщина, мм</h3><button>0.8</button></div>
            <div title="Ширина, мм"><h3>Ширина, мм</h3><button>22</button></div>
            <table>
              <tr><td>Декор (лицьова)</td><td>H (Деревоподібні)</td></tr>
              <tr><td>Виробник</td><td>Rehau</td></tr>
              <tr><td>Країна-виробник</td><td>Німеччина</td></tr>
              <tr><td>Тип основи</td><td>ABS</td></tr>
              <tr><td>Тип крайки</td><td>ABS</td></tr>
            </table>
            <img src="https://viyar.ua/cdn-cgi/image/w=400/https://viyar.ua/upload/photos/ph152446.jpg" alt="2941W Крайка ABS Пінія темно-коричнева 23x0,8мм (150 м.п.) REHAU">
          </body>
        </html>
        """

        result = viyar_parser.parse_viyar_edge_detail(html, source_url="https://viyar.ua/ua/catalog/2941w/")
        canonical = result["canonical_candidate"]
        supplier = result["supplier_offer_candidate"]

        self.assertEqual(canonical["manufacturer_article"], "2941W")
        self.assertEqual(canonical["nominal_width_mm"], 23.0)
        self.assertEqual(canonical["width_mm"], 22.0)
        self.assertEqual(canonical["thickness_mm"], 0.8)
        self.assertEqual(canonical["material_type"], "ABS")
        self.assertEqual(canonical["color"], "H (Деревоподібні)")
        self.assertEqual(canonical["country"], "Німеччина")
        self.assertEqual(canonical["roll_length"], "150")
        self.assertEqual(supplier["article"], "152446")
        self.assertEqual(supplier["price"], 42.24)
        self.assertEqual(supplier["currency"], "UAH")
        self.assertEqual(supplier["unit"], "м.п.")
        self.assertEqual(supplier["availability"], "В наявності")
        self.assertEqual(canonical["image_url"], "https://viyar.ua/upload/photos/ph152446.jpg")
        self.assertEqual(len(canonical["image_urls"]), 1)

    def test_parse_viyar_edge_detail_normalizes_structured_edge_technology(self) -> None:
        html = VIYAR_EDGE_DETAIL_HTML.replace(
            "<tr class=\"vr-block-char__tr\">\n        <td class=\"vr-block-char__name\">Тип товару:</td>",
            "<tr class=\"vr-block-char__tr\">\n        <td class=\"vr-block-char__name\">Тип крайки:</td>\n        <td class=\"vr-block-char__value\">Лазерна ABS PRO</td>\n      </tr>\n      <tr class=\"vr-block-char__tr\">\n        <td class=\"vr-block-char__name\">Тип товару:</td>",
        )
        result = viyar_parser.parse_viyar_edge_detail(html)
        self.assertEqual(result["canonical_candidate"]["technology_code"], "laser_abs_pro")

    def test_parse_viyar_edge_detail_prefers_explicit_viyar_code_over_title_prefix(self) -> None:
        html = """
        <html><body>
          <h1>29881 HD Крайка ABS Срібляста 42x2мм Hranipex</h1>
          <div data-owner-id="29881" data-brand="Hranipex"></div>
          <span class="text-unit">м.п.</span>
          <table>
            <tr class="vr-block-char__tr"><td class="vr-block-char__name">Код:</td><td class="vr-block-char__value">12234</td></tr>
            <tr class="vr-block-char__tr"><td class="vr-block-char__name">Тип товару:</td><td class="vr-block-char__value">ABS</td></tr>
            <tr class="vr-block-char__tr"><td class="vr-block-char__name">Ширина:</td><td class="vr-block-char__value">42 мм</td></tr>
            <tr class="vr-block-char__tr"><td class="vr-block-char__name">Товщина:</td><td class="vr-block-char__value">2 мм</td></tr>
          </table>
        </body></html>
        """

        result = viyar_parser.parse_viyar_edge_detail(html)

        self.assertEqual(result["canonical_candidate"]["manufacturer_article"], "29881")
        self.assertEqual(result["supplier_offer_candidate"]["article"], "12234")

    def test_source_identity_guard_compares_explicit_viyar_code(self) -> None:
        html = """
        <html><body>
          <h1>29881 HD Крайка ABS Срібляста 42x2мм Hranipex</h1>
          <div data-owner-id="29881" data-brand="Hranipex"></div>
          <span class="text-unit">м.п.</span>
          <table>
            <tr class="vr-block-char__tr"><td class="vr-block-char__name">Код:</td><td class="vr-block-char__value">12234</td></tr>
            <tr class="vr-block-char__tr"><td class="vr-block-char__name">Тип товару:</td><td class="vr-block-char__value">ABS</td></tr>
            <tr class="vr-block-char__tr"><td class="vr-block-char__name">Ширина:</td><td class="vr-block-char__value">42 мм</td></tr>
            <tr class="vr-block-char__tr"><td class="vr-block-char__name">Товщина:</td><td class="vr-block-char__value">2 мм</td></tr>
          </table>
        </body></html>
        """

        async def fake_fetcher(page, url):
            return html

        result = asyncio.run(viyar_parser.preview_viyar_edge_product(
            "https://viyar.ua/ua/catalog/29881-hd/",
            page=object(),
            fetcher=fake_fetcher,
            expected_supplier_article="12234",
        ))

        self.assertTrue(result["success"])
        self.assertEqual(result["items"][0]["supplier_offer_candidate"]["article"], "12234")

    def test_parse_viyar_edge_detail_is_pure_html_parser_and_does_not_http(self) -> None:
        source = inspect.getsource(viyar_parser.parse_viyar_edge_detail)

        self.assertNotIn("goto(", source)
        self.assertNotIn("wait_for_load_state", source)
        self.assertNotIn("fetch_with_retry", source)
        self.assertNotIn("page.", source)
        self.assertFalse(inspect.iscoroutinefunction(viyar_parser.parse_viyar_edge_detail))


if __name__ == "__main__":
    unittest.main()
