from __future__ import annotations

import asyncio
import inspect
import time
import unittest
from unittest.mock import AsyncMock, patch

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


VIYAR_RECOMMENDED_EDGE_SECTION_NAME_ONLY_HTML = """
<html>
  <body>
    <section data-section_name="  Крайка  ">
      <div class="vr-card">
        <a class="vr-card__link" href="/ua/catalog/444444-fallback-edge/?from=card" title="444444 Fallback edge">
          <span class="vr-card__title">444444 Fallback edge</span>
        </a>
      </div>
    </section>
  </body>
</html>
"""


VIYAR_RECOMMENDED_EDGE_CURRENT_MARKUP_HTML = """
<html>
  <body>
    <section id="rekomenduemayakromka">
      <div>
        <a href="/ua/catalog/2941w_kromka_abs_piniya_temno-korichnevaya-23x08/">
          <img src="https://viyar.ua/media/ph152446_6732276ab.jpg"
               alt="2941W Крайка ABS Пінія темно-коричнева 23х0,8мм (150 м.п.) REHAU">
        </a>
        <a href="/ua/catalog/2941w_kromka_abs_piniya_temno-korichnevaya-23x08/">
          2941W Крайка ABS Пінія темно-коричнева 23х0,8мм (150 м.п.) REHAU
        </a>
        <span>152446</span>
        <span>В наявності</span>
        <span>42.24 ₴ / м.п.</span>
      </div>
      <div>
        <a href="/ua/catalog/2941w_kromka_abs_piniya-temno-korichnevaya-23x08/">
          <img src="/media/ph152446_6732276ab.jpg"
               alt="2941W Крайка ABS Пінія темно-коричнева 23х0,8мм (150 м.п.) REHAU">
        </a>
        <a href="/ua/catalog/2941w_kromka_abs_piniya-temno-korichnevaya-23x08/">
          2941W Крайка ABS Пінія темно-коричнева 23х0,8мм (150 м.п.) REHAU
        </a>
        <span>152446</span>
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
    def test_api_first_discovery_does_not_refetch_material_page(self) -> None:
        class Page:
            request = object()

        async def run():
            with (
                patch.object(viyar_parser, "_fetch_viyar_recommended_edge_cards_from_api", new=AsyncMock(return_value=[])),
                patch.object(
                    viyar_parser,
                    "fetch_with_retry",
                    new=AsyncMock(side_effect=AssertionError("material page must be fallback only")),
                ),
            ):
                return await viyar_parser.preview_viyar_recommended_edges(
                    "https://viyar.ua/ua/catalog/k008/",
                    Page(),
                )

        result = asyncio.run(run())
        self.assertTrue(result["success"])
        self.assertEqual(result["recommended_edges_count"], 0)

    def test_api_timeout_uses_html_fallback(self) -> None:
        fetcher = AsyncMock(return_value="<html />")

        async def run():
            with (
                patch.object(viyar_parser, "_fetch_viyar_recommended_edge_cards_from_api", new=AsyncMock(side_effect=asyncio.TimeoutError)),
                patch.object(viyar_parser, "extract_recommended_edge_cards", return_value=[]),
            ):
                return await viyar_parser.preview_viyar_recommended_edges(
                    "https://viyar.ua/ua/catalog/k008/",
                    type("Page", (), {})(),
                    fetcher=fetcher,
                )

        result = asyncio.run(run())
        self.assertTrue(result["success"])
        fetcher.assert_awaited_once()

    def test_slow_detail_candidates_use_bounded_concurrency_and_progress(self) -> None:
        articles = [str(157900 + index) for index in range(10)]
        cards = [{"article": article, "source_url": f"https://viyar.ua/e/{article}"} for article in articles]
        progress = []

        class Context:
            async def new_page(self):
                return object()

        class Page:
            request = object()
            context = Context()

        async def fetcher(_page, url):
            await asyncio.sleep(0.05)
            return f"<html>{url}</html>"

        async def run():
            with (
                patch.object(viyar_parser, "_fetch_viyar_recommended_edge_cards_from_api", new=AsyncMock(return_value=cards)),
                patch.object(viyar_parser, "parse_viyar_edge_detail", return_value={}),
                patch.object(viyar_parser, "_classify_viyar_edge_preview_status", return_value={"status": "parsed", "reason": None, "missing_fields": []}),
            ):
                started_at = time.monotonic()
                result = await viyar_parser.preview_viyar_recommended_edges(
                    "https://viyar.ua/ua/catalog/k008/",
                    Page(),
                    fetcher=fetcher,
                    progress_callback=progress.append,
                )
                return result, time.monotonic() - started_at

        result, elapsed = asyncio.run(run())
        self.assertLess(elapsed, 0.35)
        self.assertEqual([item["discovered_card"]["article"] for item in result["items"]], articles)
        self.assertEqual(progress[0], {"phase": "recommendations_found", "total": 10})
        self.assertEqual(progress[-1]["checked"], 10)
        self.assertEqual(progress[-1]["total"], 10)

    def test_twenty_four_concurrent_candidates_keep_all_indexed_results(self) -> None:
        cards = [
            {"article": str(index), "source_url": f"https://viyar.ua/e/{index}"}
            for index in range(24)
        ]

        class Context:
            async def new_page(self):
                return object()

        class Page:
            request = object()
            context = Context()

        async def fetcher(_page, _url):
            await asyncio.sleep(0)
            return "<html />"

        async def run():
            with (
                patch.object(viyar_parser, "_fetch_viyar_recommended_edge_cards_from_api", new=AsyncMock(return_value=cards)),
                patch.object(viyar_parser, "parse_viyar_edge_detail", return_value={}),
                patch.object(viyar_parser, "_classify_viyar_edge_preview_status", return_value={"status": "parsed", "reason": None, "missing_fields": []}),
            ):
                return await viyar_parser.preview_viyar_recommended_edges(
                    "https://viyar.ua/ua/catalog/k008/", Page(), fetcher=fetcher
                )

        result = asyncio.run(run())
        self.assertEqual(result["recommended_edges_count"], 24)
        self.assertEqual(result["preview_count"], 24)
        self.assertEqual([item["candidate_index"] for item in result["items"]], list(range(24)))

    def test_concurrent_task_exception_is_explicitly_represented(self) -> None:
        cards = [
            {"article": str(index), "source_url": f"https://viyar.ua/e/{index}"}
            for index in range(24)
        ]

        class Context:
            async def new_page(self):
                return object()

        class Page:
            request = object()
            context = Context()

        async def fetcher(_page, url):
            if url.endswith("/7"):
                raise asyncio.CancelledError()
            return "<html />"

        async def run():
            with (
                patch.object(viyar_parser, "_fetch_viyar_recommended_edge_cards_from_api", new=AsyncMock(return_value=cards)),
                patch.object(viyar_parser, "parse_viyar_edge_detail", return_value={}),
                patch.object(viyar_parser, "_classify_viyar_edge_preview_status", return_value={"status": "parsed", "reason": None, "missing_fields": []}),
            ):
                return await viyar_parser.preview_viyar_recommended_edges(
                    "https://viyar.ua/ua/catalog/k008/", Page(), fetcher=fetcher
                )

        result = asyncio.run(run())
        self.assertEqual(len(result["items"]), 24)
        failed = result["items"][7]
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["reason"], "task_cancelled")
        self.assertEqual(failed["exception_type"], "CancelledError")
        self.assertTrue(failed["cancelled"])

    def test_api_discovery_reads_recommendation_ids_and_returns_ten_cards(self) -> None:
        articles = ["184342", "185187", "184343", "184340", "152444", "184341", "180094", "184339", "152482", "152565"]
        recommendation_ids = [f"product-{article}" for article in articles]
        api_items = [
            {
                "id": product_id,
                "product_code": article,
                "product_title": f"{article} Крайка ABS 22x0,8мм REHAU",
                "slug": f"edge-{article}",
                "preview_path_old": f"https://viyar.ua/upload/photos/ph{article}.jpg",
            }
            for article, product_id in zip(articles, recommendation_ids)
        ]

        class Response:
            status = 200

            def __init__(self, payload):
                self.payload = payload

            async def json(self):
                return self.payload

        class Request:
            def __init__(self):
                self.calls = 0

            async def get(self, url):
                self.calls += 1
                if self.calls == 1:
                    return Response({"items": [{"bend_recommendation_ids": recommendation_ids}]})
                return Response({"items": api_items})

        class Page:
            request = Request()

        cards = asyncio.run(
            viyar_parser._fetch_viyar_recommended_edge_cards_from_api(
                Page(),
                "https://viyar.ua/ua/catalog/k520-material/",
            )
        )

        self.assertEqual(len(cards), 10)
        self.assertEqual([card["article"] for card in cards], articles)
        self.assertTrue(all(card["source"] == "viyar_api" for card in cards))

    def test_api_discovery_deduplicates_duplicate_product_articles(self) -> None:
        ids = ["one", "two"]

        class Response:
            status = 200

            def __init__(self, payload):
                self.payload = payload

            async def json(self):
                return self.payload

        class Request:
            calls = 0

            async def get(self, url):
                self.calls += 1
                if self.calls == 1:
                    return Response({"items": [{"bend_recommendation_ids": ids}]})
                return Response({"items": [
                    {"id": "one", "product_code": "184339", "product_title": "184339 Edge", "slug": "one"},
                    {"id": "two", "product_code": "184339", "product_title": "184339 Duplicate", "slug": "two"},
                ]})

        class Page:
            request = Request()

        cards = asyncio.run(
            viyar_parser._fetch_viyar_recommended_edge_cards_from_api(
                Page(),
                "https://viyar.ua/ua/catalog/k520-material/",
            )
        )

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["article"], "184339")

    def test_extract_recommended_edge_cards_reads_current_hydrated_markup(self) -> None:
        cards = viyar_parser.extract_recommended_edge_cards(VIYAR_RECOMMENDED_EDGE_CURRENT_MARKUP_HTML)

        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["article"], "152446")
        self.assertEqual(card["supplier_article"], "152446")
        self.assertEqual(card["manufacturer_article"], "2941W")
        self.assertEqual(card["width_mm"], 23.0)
        self.assertEqual(card["thickness_mm"], 0.8)
        self.assertEqual(card["image_url"], "https://viyar.ua/media/ph152446_6732276ab.jpg")
        self.assertEqual(card["price"], 42.24)
        self.assertEqual(card["unit"], "м.п.")
        self.assertEqual(card["availability"], "В наявності")

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

    def test_extract_recommended_edge_cards_falls_back_to_edge_section_name(self) -> None:
        cards = viyar_parser.extract_recommended_edge_cards(VIYAR_RECOMMENDED_EDGE_SECTION_NAME_ONLY_HTML)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["article"], "444444")
        self.assertEqual(cards[0]["source_url"], "https://viyar.ua/ua/catalog/444444-fallback-edge/")

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

    def test_preview_current_markup_discovers_control_edge_and_uses_detail_parser(self) -> None:
        async def fake_fetcher(page, url):
            if url == "https://viyar.ua/ua/catalog/k533/":
                return VIYAR_RECOMMENDED_EDGE_CURRENT_MARKUP_HTML
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
        self.assertEqual(result["items"][0]["status"], "parsed")
        self.assertEqual(result["items"][0]["discovered_card"]["article"], "152446")
        self.assertEqual(result["items"][0]["supplier_offer_candidate"]["article"], "152446")

    def _run_preview_with_hydrated_dom(self, initial_html: str, hydrated_html: str, api_result):
        class Section:
            async def count(self):
                return 1

            async def scroll_into_view_if_needed(self):
                return None

        class Anchor:
            @property
            def first(self):
                return self

            async def count(self):
                return 1

            async def click(self, timeout=None):
                page.hydrated = True

        class Page:
            request = object()
            hydrated = False

            def locator(self, selector):
                return Anchor() if selector.startswith("a[") else Section()

            async def content(self):
                return hydrated_html if self.hydrated else initial_html

            async def wait_for_timeout(self, _timeout):
                return None

            class Context:
                async def new_page(self):
                    return object()

            context = Context()

        page = Page()

        async def api_fetcher(_page, _url, diagnostics=None):
            if diagnostics is not None and api_result:
                diagnostics.update({"status": 200, "recommendation_status": 200, "candidate_count": len(api_result)})
            return api_result

        async def detail_fetcher(_page, url):
            if url.endswith("/material/"):
                return initial_html
            return VIYAR_EDGE_DETAIL_NO_IMAGE_HTML

        async def run():
            with (
                patch.object(viyar_parser, "_fetch_viyar_recommended_edge_cards_from_api", new=api_fetcher),
                patch.object(viyar_parser, "parse_viyar_edge_detail", return_value={}),
                patch.object(viyar_parser, "_classify_viyar_edge_preview_status", return_value={"status": "parsed", "reason": None, "missing_fields": []}),
            ):
                return await viyar_parser.preview_viyar_recommended_edges(
                    "https://viyar.ua/ua/catalog/material/",
                    page,
                    fetcher=detail_fetcher,
                )

        return asyncio.run(run())

    def test_api_first_five_candidates_skips_dom_fallback(self) -> None:
        cards = [{"supplier_article": str(90886 + index), "article": str(90886 + index), "source_url": f"https://viyar.ua/e/{index}"} for index in range(5)]
        result = self._run_preview_with_hydrated_dom("<section id='rekomenduemayakromka'></section>", "<section id='rekomenduemayakromka'></section>", cards)
        self.assertEqual(result["discovery"]["source"], "api")
        self.assertEqual(result["discovery"]["final_candidate_count"], 5)

    def test_empty_api_hydrates_dom_before_returning_zero(self) -> None:
        hydrated = "<section id='rekomenduemayakromka'><a href='/ua/catalog/edge-90886/'><span>90886</span> 90886 Крайка 22x0,4 REHAU</a></section>"
        result = self._run_preview_with_hydrated_dom("<section id='rekomenduemayakromka'></section>", hydrated, [])
        self.assertEqual(result["discovery"]["source"], "hydrated_dom")
        self.assertEqual(result["discovery"]["dom_candidate_count"], 1)
        self.assertEqual(result["recommended_edges_count"], 1)

    def test_empty_hydrated_dom_is_reported_as_none(self) -> None:
        result = self._run_preview_with_hydrated_dom("<section id='rekomenduemayakromka'></section>", "<section id='rekomenduemayakromka'></section>", [])
        self.assertEqual(result["discovery"]["source"], "none")
        self.assertEqual(result["discovery"]["final_candidate_count"], 0)

    def test_duplicate_paths_dedupe_by_supplier_article(self) -> None:
        cards = [
            {"supplier_article": "90886", "article": "90886", "source_url": "https://viyar.ua/e/one"},
            {"supplier_article": "90886", "article": "90886", "source_url": "https://viyar.ua/e/two"},
        ]
        result = self._run_preview_with_hydrated_dom("<section id='rekomenduemayakromka'></section>", "<section id='rekomenduemayakromka'></section>", cards)
        self.assertEqual(result["recommended_edges_count"], 1)

    def test_dom_extraction_ignores_promotional_section(self) -> None:
        html = """
        <section data-section_name="Промо"><a href="/ua/catalog/promo-999/">999 Promo</a></section>
        <section id="rekomenduemayakromka"><a href="/ua/catalog/edge-90886/"><span>90886</span> 90886 Крайка 22x0,4 REHAU</a></section>
        """
        cards = viyar_parser.extract_recommended_edge_cards(html)
        self.assertEqual([card["article"] for card in cards], ["90886"])

    def test_k688_and_k689_control_articles_resolve_identically(self) -> None:
        expected = ["90886", "35699", "35681", "123171", "38836"]
        for url in ("k688-201247", "k689-201248"):
            class Response:
                status = 200

                async def json(self):
                    return {"items": [{"id": article, "product_code": article, "product_title": f"{article} Edge", "slug": f"edge-{article}"} for article in expected]}

            class Request:
                calls = 0

                async def get(self, _url):
                    self.calls += 1
                    if self.calls == 1:
                        return type("ProductResponse", (), {"status": 200, "json": lambda _self: asyncio.sleep(0, result={"items": [{"bend_recommendation_ids": expected}]})})()
                    return Response()

            cards = asyncio.run(viyar_parser._fetch_viyar_recommended_edge_cards_from_api(type("Page", (), {"request": Request()})(), url))
            self.assertEqual([card["article"] for card in cards], expected)

    def test_extract_recommended_edge_cards_is_pure_html_parser_and_does_not_http(self) -> None:
        source = inspect.getsource(viyar_parser.extract_recommended_edge_cards)

        self.assertNotIn("goto(", source)
        self.assertNotIn("wait_for_load_state", source)
        self.assertNotIn("fetch_with_retry", source)
        self.assertNotIn("page.", source)
        self.assertFalse(inspect.iscoroutinefunction(viyar_parser.extract_recommended_edge_cards))


if __name__ == "__main__":
    unittest.main()
