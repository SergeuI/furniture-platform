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
                        "price": 10.0,
                        "stock": "in stock",
                        "source": "legacy",
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
            "import { buildCanonicalFittingCatalogView, getFittingCatalogBodyNavItems } from './frontend/admin/src/fittingCatalogView.js';"
            "const payload = JSON.parse(process.argv[1]);"
            "const nav = getFittingCatalogBodyNavItems(payload.language);"
            "const view = buildCanonicalFittingCatalogView(payload.view);"
            "process.stdout.write(JSON.stringify({ nav, view }));"
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

        self.assertEqual(
            [item["view"] for item in nav],
            [
                "catalogFittings",
                "catalogFittingManufacturers",
                "catalogFittingSeries",
                "catalogFittingCategories",
            ],
        )
        self.assertEqual(
            [item["label"] for item in nav],
            ["\u041a\u0430\u0442\u0430\u043b\u043e\u0433", "\u0412\u0438\u0440\u043e\u0431\u043d\u0438\u043a\u0438", "\u0421\u0435\u0440\u0456\u0457", "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0457"],
        )
        self.assertEqual(view["categories"][0]["canonical_item_count"], 1)
        self.assertEqual(len(view["visibleCards"]), 1)
        self.assertEqual(view["visibleCards"][0]["legacy_row_count"], 2)
        self.assertEqual(view["visibleCards"][0]["category_code"], "connectors_fasteners")

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
