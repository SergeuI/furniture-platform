from __future__ import annotations

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch

from services import material_catalog_service


class MaterialSourceFetchBudgetTests(unittest.TestCase):
    def test_direct_source_fast_path_does_not_use_browser_fallback(self) -> None:
        material = {"article": "31289", "name": "Kronospan 7190", "price": 1}

        async def run():
            with (
                patch.object(material_catalog_service, "_fetch_html", return_value=("<html />", "https://viyar.ua/product/")),
                patch.object(material_catalog_service, "_extract_material_from_product_html", return_value=material),
                patch.object(material_catalog_service, "_fetch_viyar_material_by_article_async_traced", new=AsyncMock()) as fallback,
            ):
                result = await material_catalog_service.fetch_viyar_product_details_by_url_traced(
                    "https://viyar.ua/product/",
                    article_hint="31289",
                )
                fallback.assert_not_awaited()
                return result

        result, debug = asyncio.run(run())
        self.assertEqual(result, material)
        self.assertEqual(debug["strategy"], "direct_url_html")

    def test_direct_failure_uses_bounded_browser_fallback(self) -> None:
        material = {"article": "31289", "name": "Kronospan 7190", "price": 1}

        async def run():
            with (
                patch.object(material_catalog_service, "_fetch_html", side_effect=OSError("direct failed")),
                patch.object(
                    material_catalog_service,
                    "_fetch_viyar_material_by_article_async_traced",
                    new=AsyncMock(return_value=(material, {"strategy": "browser", "trace": []})),
                ) as fallback,
            ):
                result = await material_catalog_service.fetch_viyar_product_details_by_url_traced(
                    "https://viyar.ua/product/",
                    article_hint="31289",
                )
                fallback.assert_awaited_once()
                return result

        result, debug = asyncio.run(run())
        self.assertEqual(result, material)
        self.assertEqual(debug["strategy"], "browser")

    def test_all_source_methods_fail_within_budget(self) -> None:
        async def run():
            with (
                patch.object(material_catalog_service, "WORKER_TIMEOUT_SECONDS", 0.05),
                patch.object(material_catalog_service, "_fetch_html", side_effect=OSError("direct failed")),
                patch.object(
                    material_catalog_service,
                    "_fetch_viyar_material_by_article_async_traced",
                    new=AsyncMock(side_effect=RuntimeError("browser failed")),
                ),
            ):
                started_at = time.monotonic()
                with self.assertRaises(material_catalog_service.MaterialImportError):
                    await material_catalog_service.fetch_viyar_product_details_by_url_traced(
                        "https://viyar.ua/product/",
                        article_hint="31289",
                    )
                return time.monotonic() - started_at

        elapsed = asyncio.run(run())
        self.assertLess(elapsed, 1.0)


if __name__ == "__main__":
    unittest.main()
