from __future__ import annotations

import unittest

from services import viyar_parser


MATERIAL_PAGE_HTML = """
<html>
  <body>
    <section data-section_name="Крайка" data-list_name="Крайки та пластики">
      <a class="vr-card__link" href="/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/?ms_q=141342">
        <span class="vr-card__title">141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU</span>
      </a>
      <a class="vr-card__link" href="/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh0_8mm_150_m_p_rehau/?ms_q=141342">
        <span class="vr-card__title">141342 Kromka ABS Izumrud Zelenyy 23x0,8mm 150 m.p. REHAU</span>
      </a>
      <a class="vr-card__link" href="/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh2mm_100_m_p_rehau/?ms_q=141342">
        <span class="vr-card__title">141342 Kromka ABS Izumrud Zelenyy 23x2mm 100 m.p. REHAU</span>
      </a>
      <a class="vr-card__link" href="/ua/catalog/141342_kromka_abs_izumrud_zelenyy_43kh2mm_100_m_p_rehau/?ms_q=141342">
        <span class="vr-card__title">141342 Kromka ABS Izumrud Zelenyy 43x2mm 100 m.p. REHAU</span>
      </a>
      <a class="vr-card__link" href="/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh0_8mm_150_m_p_rehau/?duplicate=1">
        <span class="vr-card__title">Duplicate 23x0,8mm</span>
      </a>
    </section>
  </body>
</html>
"""


EDGE_HTML_BY_URL = {
    "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/": """
        <html>
          <body>
            <h1>141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU</h1>
            <div data-owner-id="185187" data-brand="Rehau"></div>
            <div class="productLabel">СКОРО У ПРОДАЖУ</div>
            <div id="product_price">19.26 UAH / м.п.</div>
            <span class="text-unit">м.п.</span>
            <div class="productImageBlock__slider">
              <img src="/store/Items/photos/ph185187.jpg">
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
                <td class="vr-block-char__name">Виробник:</td>
                <td class="vr-block-char__value">Rehau</td>
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
    """,
    "https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh0_8mm_150_m_p_rehau/": """
        <html>
          <body>
            <h1>141342 Kromka ABS Izumrud Zelenyy 23x0,8mm 150 m.p. REHAU</h1>
            <div data-owner-id="152444" data-brand="Rehau"></div>
            <div class="productLabel">В наявності</div>
            <div id="product_price">17.10 UAH / м.п.</div>
            <span class="text-unit">м.п.</span>
            <div class="productImageBlock__slider">
              <img src="/store/Items/photos/ph152444.jpg">
            </div>
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
                <td class="vr-block-char__name">Колір:</td>
                <td class="vr-block-char__value">Смарагд зелений</td>
              </tr>
              <tr class="vr-block-char__tr">
                <td class="vr-block-char__name">Виробник:</td>
                <td class="vr-block-char__value">Rehau</td>
              </tr>
              <tr class="vr-block-char__tr">
                <td class="vr-block-char__name">Довжина рулону:</td>
                <td class="vr-block-char__value">150 м.п.</td>
              </tr>
            </table>
          </body>
        </html>
    """,
    "https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh2mm_100_m_p_rehau/": """
        <html>
          <body>
            <h1>141342 Kromka ABS Izumrud Zelenyy 23x2mm 100 m.p. REHAU</h1>
            <div data-owner-id="152482" data-brand="Rehau"></div>
            <div class="productLabel">В наявності</div>
            <div id="product_price">18.20 UAH / м.п.</div>
            <span class="text-unit">м.п.</span>
            <div class="productImageBlock__slider">
              <img src="/store/Items/photos/ph152482.jpg">
            </div>
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
                <td class="vr-block-char__value">2 мм</td>
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
                <td class="vr-block-char__name">Довжина рулону:</td>
                <td class="vr-block-char__value">100 м.п.</td>
              </tr>
            </table>
          </body>
        </html>
    """,
    "https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_43kh2mm_100_m_p_rehau/": """
        <html>
          <body>
            <h1>141342 Kromka ABS Izumrud Zelenyy 43x2mm 100 m.p. REHAU</h1>
            <div data-owner-id="152565" data-brand="Rehau"></div>
            <div class="productLabel">В наявності</div>
            <div id="product_price">24.50 UAH / м.п.</div>
            <span class="text-unit">м.п.</span>
            <div class="productImageBlock__slider">
              <img src="/store/Items/photos/ph152565.jpg">
            </div>
            <table>
              <tr class="vr-block-char__tr">
                <td class="vr-block-char__name">Тип товару:</td>
                <td class="vr-block-char__value">ABS</td>
              </tr>
              <tr class="vr-block-char__tr">
                <td class="vr-block-char__name">Ширина:</td>
                <td class="vr-block-char__value">43 мм</td>
              </tr>
              <tr class="vr-block-char__tr">
                <td class="vr-block-char__name">Товщина:</td>
                <td class="vr-block-char__value">2 мм</td>
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
                <td class="vr-block-char__name">Довжина рулону:</td>
                <td class="vr-block-char__value">100 м.п.</td>
              </tr>
            </table>
          </body>
        </html>
    """,
}


class ViyarEdgePreviewFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_flow_fetches_material_once_and_preview_items_are_parsed(self) -> None:
        calls: list[str] = []

        async def fake_fetcher(page, url):
            calls.append(url)
            if url == "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/":
                return MATERIAL_PAGE_HTML
            return EDGE_HTML_BY_URL[url]

        result = await viyar_parser.preview_viyar_recommended_edges(
            "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/?ms_q=K520%20PD",
            page=object(),
            fetcher=fake_fetcher,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["recommended_edges_count"], 4)
        self.assertEqual(result["preview_count"], 4)
        self.assertEqual(
            calls,
            [
                "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/",
                "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
                "https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh0_8mm_150_m_p_rehau/",
                "https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh2mm_100_m_p_rehau/",
                "https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_43kh2mm_100_m_p_rehau/",
            ],
        )

        items = result["items"]
        self.assertEqual([item["status"] for item in items], ["parsed", "parsed", "parsed", "parsed"])
        self.assertEqual(
            [item["discovered_card"]["article"] for item in items],
            ["141342", "141342", "141342", "141342"],
        )
        self.assertEqual(
            [item["supplier_offer_candidate"]["article"] for item in items],
            ["185187", "152444", "152482", "152565"],
        )
        self.assertEqual(
            [item["canonical_candidate"]["width_mm"] for item in items],
            [22.0, 23.0, 23.0, 43.0],
        )
        self.assertEqual(
            [item["canonical_candidate"]["thickness_mm"] for item in items],
            [0.4, 0.8, 2.0, 2.0],
        )
        self.assertEqual(items[0]["supplier_offer_candidate"]["availability"], "Скоро у продажу")

    async def test_preview_flow_does_not_fetch_duplicate_recommended_url_twice_and_survives_failure(self) -> None:
        calls: list[str] = []

        async def fake_fetcher(page, url):
            calls.append(url)
            if url == "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/":
                return MATERIAL_PAGE_HTML
            if url.endswith("23kh2mm_100_m_p_rehau/"):
                return None
            return EDGE_HTML_BY_URL[url]

        result = await viyar_parser.preview_viyar_recommended_edges(
            "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/?ms_q=K520%20PD",
            page=object(),
            fetcher=fake_fetcher,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["recommended_edges_count"], 4)
        self.assertEqual(result["preview_count"], 4)
        self.assertEqual(calls.count("https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh0_8mm_150_m_p_rehau/"), 1)
        self.assertEqual(calls.count("https://viyar.ua/ua/catalog/141342_kromka_abs_izumrud_zelenyy_23kh2mm_100_m_p_rehau/"), 1)
        self.assertEqual([item["status"] for item in result["items"]], ["parsed", "parsed", "failed", "parsed"])
        self.assertIn("could not be fetched", (result["items"][2]["error"] or "").lower())

    async def test_preview_flow_does_not_touch_database(self) -> None:
        async def fake_fetcher(page, url):
            if url == "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/":
                return MATERIAL_PAGE_HTML
            return EDGE_HTML_BY_URL[url]

        with unittest.mock.patch("services.viyar_parser.aiosqlite.connect") as connect_mock:
            await viyar_parser.preview_viyar_recommended_edges(
                "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/?ms_q=K520%20PD",
                page=object(),
                fetcher=fake_fetcher,
            )

        connect_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
