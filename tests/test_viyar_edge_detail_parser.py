from __future__ import annotations

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


VIYAR_EDGE_DETAIL_TITLE_WIDTH_PRIORITY_HTML = """
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


class ViyarEdgeDetailParserTests(unittest.TestCase):
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

    def test_parse_viyar_edge_detail_prefers_title_width_over_characteristics_width(self) -> None:
        result = viyar_parser.parse_viyar_edge_detail(VIYAR_EDGE_DETAIL_TITLE_WIDTH_PRIORITY_HTML)

        canonical = result["canonical_candidate"]

        self.assertEqual(canonical["manufacturer"], "Rehau")
        self.assertEqual(canonical["manufacturer_article"], "5000W")
        self.assertEqual(canonical["material_type"], "ABS")
        self.assertEqual(canonical["width_mm"], 23.0)
        self.assertEqual(canonical["thickness_mm"], 0.8)

    def test_parse_viyar_edge_detail_is_pure_html_parser_and_does_not_http(self) -> None:
        source = inspect.getsource(viyar_parser.parse_viyar_edge_detail)

        self.assertNotIn("goto(", source)
        self.assertNotIn("wait_for_load_state", source)
        self.assertNotIn("fetch_with_retry", source)
        self.assertNotIn("page.", source)
        self.assertFalse(inspect.iscoroutinefunction(viyar_parser.parse_viyar_edge_detail))


if __name__ == "__main__":
    unittest.main()
