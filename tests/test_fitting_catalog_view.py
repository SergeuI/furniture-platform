from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


class FittingCatalogViewTests(unittest.TestCase):
    def test_body_navigation_and_canonical_grouping_are_stable(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        payload = {
            "language": "uk",
            "view": {
                "activeCategoryCode": "connectors_fasteners",
                "activeCity": "kyiv",
                "canonicalProducts": [
                    {
                        "id": 10,
                        "article": "A-1",
                        "name": "Canonical Bolt",
                        "brand": "BrandX",
                        "manufacturer_id": 1,
                        "series_id": 2,
                        "category_id": 3,
                        "is_active": True,
                    },
                    {
                        "id": 11,
                        "article": "B-2",
                        "name": "Canonical Spacer",
                        "brand": "BrandX",
                        "manufacturer_id": 1,
                        "series_id": 2,
                        "category_id": None,
                        "is_active": True,
                    },
                ],
                "legacyCategories": [
                    {
                        "code": "connectors_fasteners",
                        "name": "\u0417'\u0454\u0434\u043d\u0443\u0432\u0430\u043b\u044c\u043d\u0430 \u0442\u0430 \u043a\u0440\u0456\u043f\u0438\u043b\u044c\u043d\u0430 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430",
                        "group_name": "fasteners",
                        "item_count": 2,
                    },
                ],
                "legacyItems": [
                    {
                        "id": 1,
                        "technical_product_id": 10,
                        "city": "kyiv",
                        "article": "A-1",
                        "name": "Legacy Bolt Kyiv",
                        "fitting_type": "connectors_fasteners",
                        "price": None,
                        "stock": None,
                        "source": "legacy",
                        "is_system": True,
                        "owner_user_id": None,
                    },
                    {
                        "id": 2,
                        "technical_product_id": 10,
                        "city": "lviv",
                        "article": "A-1",
                        "name": "Legacy Bolt Lviv",
                        "fitting_type": "connectors_fasteners",
                        "price": 10.5,
                        "stock": "low",
                        "source": "legacy",
                        "image_url": "https://cdn.example.com/fittings/a-1.jpg",
                        "is_system": True,
                        "owner_user_id": None,
                    },
                    {
                        "id": 3,
                        "technical_product_id": 11,
                        "city": "kyiv",
                        "article": "B-2",
                        "name": "Legacy Spacer Kyiv",
                        "fitting_type": "",
                        "price": 12.0,
                        "stock": "in stock",
                        "source": "legacy",
                        "is_system": False,
                        "owner_user_id": 10,
                    },
                ],
                "manufacturers": [
                    {"id": 1, "code": "brandx", "name": "BrandX"},
                ],
                "series": [
                    {"id": 2, "manufacturer_id": 1, "code": "clip-top", "name": "CLIP top"},
                ],
                "taxonomyCategories": [
                    {"id": 3, "code": "connectors_fasteners", "name": "Connectors"},
                ],
            },
        }

        script = (
            "import { buildCanonicalFittingCatalogView, getFittingCatalogBodyNavItems, canRenderCanonicalFittingOwnershipBadge } from './frontend/admin/src/fittingCatalogView.js';"
            "import { getCanonicalFittingsCountLabel, getCanonicalFittingsOverviewCountLabel, getCanonicalFittingOwnershipSource } from './frontend/admin/src/fittingCatalogView.js';"
            "import { getFittingOwnershipTypeLabel } from './frontend/admin/src/fittingEntitlements.js';"
            "const payload = JSON.parse(process.argv[1]);"
            "const nav = getFittingCatalogBodyNavItems(payload.language);"
            "const view = buildCanonicalFittingCatalogView(payload.view);"
            "const uncategorizedView = buildCanonicalFittingCatalogView({ ...payload.view, activeCategoryCode: 'uncategorized' });"
            "const ownershipSource = getCanonicalFittingOwnershipSource(view.visibleCards[0]);"
            "const overviewZeroVisibleLabel = getCanonicalFittingsOverviewCountLabel({ activeCategoryCode: 'connectors_fasteners', visibleCards: [], allCards: Array.from({ length: 1 }, (_, index) => ({ id: index + 1 })), language: payload.language });"
            "const overviewTwoCardsLabel = getCanonicalFittingsOverviewCountLabel({ activeCategoryCode: 'connectors_fasteners', visibleCards: Array.from({ length: 1 }, (_, index) => ({ id: index + 1 })), allCards: Array.from({ length: 2 }, (_, index) => ({ id: index + 1 })), language: payload.language });"
            "const overviewZeroCardsLabel = getCanonicalFittingsOverviewCountLabel({ allCards: [], language: payload.language });"
            "const categoryCountLabel = getCanonicalFittingsCountLabel({ activeCategoryCode: 'connectors_fasteners', visibleCards: Array.from({ length: 1 }, (_, index) => ({ id: index + 1 })), allCards: Array.from({ length: 2 }, (_, index) => ({ id: index + 1 })), language: payload.language });"
            "process.stdout.write(JSON.stringify({ nav, view, uncategorizedView, overviewZeroVisibleLabel, overviewTwoCardsLabel, overviewZeroCardsLabel, categoryCountLabel, ownershipSource, ownershipLabel: getFittingOwnershipTypeLabel(ownershipSource, null, payload.language), ownershipBadgeRenderable: canRenderCanonicalFittingOwnershipBadge(view.visibleCards[0]) }));"
        )

        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script, json.dumps(payload)],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        result = json.loads(completed.stdout)
        nav = result["nav"]
        view = result["view"]
        uncategorized_view = result["uncategorizedView"]

        self.assertEqual(
            [item["view"] for item in nav],
            [
                "catalogFittings",
                "catalogFittingManufacturers",
                "catalogFittingSeries",
                "catalogFittingCategories",
                "catalogFittingProducts",
            ],
        )
        self.assertEqual(
            [item["label"] for item in nav],
            [
                "\u041a\u0430\u0442\u0430\u043b\u043e\u0433",
                "\u0412\u0438\u0440\u043e\u0431\u043d\u0438\u043a\u0438",
                "\u0421\u0435\u0440\u0456\u0457",
                "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0457",
                "\u0422\u0435\u0445\u043d\u0456\u0447\u043d\u0456 \u0442\u043e\u0432\u0430\u0440\u0438",
            ],
        )
        self.assertEqual(view["categories"][0]["canonical_item_count"], 1)
        self.assertEqual(view["categories"][1]["code"], "uncategorized")
        self.assertEqual(view["categories"][1]["canonical_item_count"], 1)
        self.assertEqual(result["overviewZeroVisibleLabel"], "\u0031 \u0442\u043e\u0432\u0430\u0440")
        self.assertEqual(result["overviewTwoCardsLabel"], "\u0032 \u0442\u043e\u0432\u0430\u0440\u0438")
        self.assertEqual(result["overviewZeroCardsLabel"], "\u0030 \u0442\u043e\u0432\u0430\u0440\u0456\u0432")
        self.assertEqual(result["categoryCountLabel"], "\u0031 \u0442\u043e\u0432\u0430\u0440")
        self.assertEqual(len(view["visibleCards"]), 1)
        self.assertEqual(len(view["allCards"]), 2)
        self.assertEqual(view["visibleCards"][0]["legacy_row_count"], 2)
        self.assertEqual(view["visibleCards"][0]["category_code"], "connectors_fasteners")
        self.assertEqual(view["visibleCards"][0]["representative_legacy_row"]["id"], 1)
        self.assertEqual(view["visibleCards"][0]["image_legacy_row"]["id"], 2)
        self.assertEqual(view["visibleCards"][0]["commercial_legacy_row"]["id"], 2)
        self.assertEqual(result["ownershipSource"]["id"], 1)
        self.assertEqual(result["ownershipLabel"], "\u0421\u0438\u0441\u0442\u0435\u043c\u043d\u0430")
        self.assertTrue(result["ownershipBadgeRenderable"])
        self.assertEqual(len(uncategorized_view["visibleCards"]), 1)
        self.assertEqual(uncategorized_view["visibleCards"][0]["category_code"], "uncategorized")

        search_payload = dict(payload)
        search_payload["view"] = dict(payload["view"], search="BrandX")
        search_completed = subprocess.run(
            ["node", "--input-type=module", "-e", script, json.dumps(search_payload)],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        search_result = json.loads(search_completed.stdout)["view"]
        self.assertEqual(len(search_result["visibleCards"]), 1)
        self.assertEqual(search_result["visibleCards"][0]["legacy_row_count"], 2)
