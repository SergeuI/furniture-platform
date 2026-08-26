from __future__ import annotations

import asyncio
import inspect
import unittest

from services import viyar_parser


VIYAR_RECOMMENDED_EDGE_HTML = """
<html>
  <body>
    <section
      data-section_name="Супутні та Аналоги"
      data-list_name="Крайки та пластики"
    >
      <a class="vr-card__link" href="/ua/catalog/ignored-analog/">
        <span>Ignored analog</span>
      </a>
    </section>
    <section
      data-section_name="Крайка"
      data-list_name="Крайки та пластики"
      data-owner-id="185187"
    >
      <div class="vr-card">
        <a
          class="vr-card__link"
          href="/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/?from=card"
          title="141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU"
        >
          <img
            src="/store/Items/photos/ph141342.jpg"
            alt="141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU"
          >
          <span class="vr-card__title">141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU</span>
        </a>
      </div>
      <div class="vr-card">
        <a
          class="vr-card__link"
          href="https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/?duplicate=1"
          title="141342 duplicate"
        >
          <span class="vr-card__title">141342 duplicate</span>
        </a>
      </div>
      <div class="vr-card">
        <a
          class="vr-card__link"
          href="/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/?duplicate=1"
        >
          <span class="vr-card__title">Outside duplicate should not count</span>
        </a>
      </div>
      <div class="vr-card">
        <a class="vr-card__link">
          <span class="vr-card__title">Missing href</span>
        </a>
      </div>
    </section>
    <a class="vr-card__link" href="/ua/catalog/outside-section/">
      Outside section
    </a>
  </body>
</html>
"""


VIYAR_RECOMMENDED_EDGE_THREE_CARDS_HTML = """
<html>
  <body>
    <section
      data-section_name="Крайка"
      data-list_name="Крайки та пластики"
      data-owner-id="185187"
    >
      <div class="vr-card">
        <a class="vr-card__link" href="/ua/catalog/111111-first-edge/?from=card" title="111111 First edge">
          <span class="vr-card__title">111111 First edge</span>
        </a>
      </div>
      <div class="vr-card">
        <a class="vr-card__link" href="/ua/catalog/222222-second-edge/?from=card" title="222222 Second edge">
          <span class="vr-card__title">222222 Second edge</span>
        </a>
      </div>
      <div class="vr-card">
        <a class="vr-card__link" href="/ua/catalog/333333-third-edge/?from=card" title="333333 Third edge">
          <span class="vr-card__title">333333 Third edge</span>
        </a>
      </div>
    </section>
  </body>
</html>
"""


VIYAR_RECOMMENDED_EDGE_NEEDS_REVIEW_HTML = """
<html>
  <body>
    <section
      data-section_name="Крайка"
      data-list_name="Крайки та пластики"
      data-owner-id="185187"
    >
      <a
        class="vr-card__link"
        href="/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/"
        title="141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU"
      >
        <img src="/store/Items/photos/ph141342.jpg" alt="141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU">
      </a>
    </section>
  </body>
</html>
"""


VIYAR_EDGE_DETAIL_NEEDS_REVIEW_HTML = """
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


VIYAR_EDGE_DETAIL_NO_IMAGE_HTML = """
<html>
  <body>
    <h1>2941W Крайка ABS Пінія темно-коричнева 23x0,8мм (150 м.п.) REHAU</h1>
    <div data-owner-id="152446" data-brand="Rehau"></div>
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


class ViyarRecommendedEdgeParserTests(unittest.TestCase):
    def test_extract_recommended_edge_cards_returns_all_unique_cards_in_order(self) -> None:
        cards = viyar_parser.extract_recommended_edge_cards(VIYAR_RECOMMENDED_EDGE_THREE_CARDS_HTML)

        self.assertEqual(len(cards), 3)
        self.assertEqual(
            [card["source_url"] for card in cards],
            [
                "https://viyar.ua/ua/catalog/111111-first-edge/",
                "https://viyar.ua/ua/catalog/222222-second-edge/",
                "https://viyar.ua/ua/catalog/333333-third-edge/",
            ],
        )
        self.assertEqual(
            [card["article"] for card in cards],
            ["111111", "222222", "333333"],
        )

    def test_extract_recommended_edge_cards_scopes_to_exact_edge_section(self) -> None:
        cards = viyar_parser.extract_recommended_edge_cards(VIYAR_RECOMMENDED_EDGE_HTML)

        self.assertEqual(len(cards), 1)
        self.assertEqual(
            cards[0]["article"],
            "141342",
        )
        self.assertEqual(cards[0]["name"], "141342 Крайка ABS Смарагд зелений 22x0,4мм (300 м.п.) REHAU")
        self.assertEqual(
            cards[0]["source_url"],
            "https://viyar.ua/ua/catalog/141342-krayka-abs-smaragd-zeleniy-22x0-4mm-300-m-p-rehau/",
        )
        self.assertEqual(cards[0]["image_url"], "https://viyar.ua/store/Items/photos/ph141342.jpg")
        self.assertEqual(cards[0]["source"], "viyar")

    def test_extract_recommended_edge_cards_excludes_other_sections_and_missing_section(self) -> None:
        no_section_html = """
        <html>
          <body>
            <section data-section_name="Супутні та Аналоги" data-list_name="Крайки та пластики">
              <a class="vr-card__link" href="/ua/catalog/ignored/">
                <span>Ignored</span>
              </a>
            </section>
          </body>
        </html>
        """

        self.assertEqual(viyar_parser.extract_recommended_edge_cards(no_section_html), [])

    def test_preview_recommended_edges_preserves_needs_review_reason_and_missing_fields(self) -> None:
        async def fake_fetcher(page, url):
            if url == "https://viyar.ua/ua/catalog/k533/":
                return VIYAR_RECOMMENDED_EDGE_NEEDS_REVIEW_HTML
            return VIYAR_EDGE_DETAIL_NEEDS_REVIEW_HTML

        result = asyncio.run(
            viyar_parser.preview_viyar_recommended_edges(
                "https://viyar.ua/ua/catalog/k533/",
                page=object(),
                fetcher=fake_fetcher,
            )
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["recommended_edges_count"], 1)
        self.assertEqual(result["preview_count"], 1)
        item = result["items"][0]
        self.assertEqual(item["status"], "needs_review")
        self.assertEqual(item["reason"], "missing_supplier_fields")
        self.assertIn("unit", item["missing_fields"])
        self.assertEqual(item["discovered_card"]["article"], "141342")

    def test_preview_recommended_edges_allows_missing_image_when_identity_fields_are_present(self) -> None:
        async def fake_fetcher(page, url):
            if url == "https://viyar.ua/ua/catalog/k533/":
                return VIYAR_RECOMMENDED_EDGE_NEEDS_REVIEW_HTML
            return VIYAR_EDGE_DETAIL_NO_IMAGE_HTML

        result = asyncio.run(
            viyar_parser.preview_viyar_recommended_edges(
                "https://viyar.ua/ua/catalog/k533/",
                page=object(),
                fetcher=fake_fetcher,
            )
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["recommended_edges_count"], 1)
        self.assertEqual(result["preview_count"], 1)
        item = result["items"][0]
        self.assertEqual(item["status"], "parsed")
        self.assertEqual(item["canonical_candidate"]["manufacturer"], "Rehau")
        self.assertIsNone(item["canonical_candidate"]["image_url"])
        self.assertEqual(item["supplier_offer_candidate"]["article"], "152446")

    def test_extract_recommended_edge_cards_is_pure_html_parser_and_does_not_http(self) -> None:
        source = inspect.getsource(viyar_parser.extract_recommended_edge_cards)

        self.assertNotIn("goto(", source)
        self.assertNotIn("wait_for_load_state", source)
        self.assertNotIn("fetch_with_retry", source)
        self.assertNotIn("page.", source)
        self.assertFalse(inspect.iscoroutinefunction(viyar_parser.extract_recommended_edge_cards))


if __name__ == "__main__":
    unittest.main()
