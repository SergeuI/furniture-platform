from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from database.repositories.inventory_repository import _extract_supplier_offer_characteristics


class MaterialSupplierOfferCharacteristicsTests(unittest.TestCase):
    def test_legacy_payload_shapes_are_read_without_mutation(self) -> None:
        offer = SimpleNamespace(
            source_payload_json=json.dumps(
                {
                    "parsed_material": {
                        "characteristics": {
                            " Тип основи ": " ДСП ",
                            "Товщина": "18 мм",
                            "Порожнє": "   ",
                        }
                    }
                },
                ensure_ascii=False,
            )
        )

        self.assertEqual(
            _extract_supplier_offer_characteristics(offer),
            {"Тип основи": "ДСП", "Товщина": "18 мм"},
        )

    def test_null_malformed_and_direct_payloads_return_safe_map(self) -> None:
        self.assertEqual(
            _extract_supplier_offer_characteristics(SimpleNamespace(source_payload_json=None)),
            {},
        )
        self.assertEqual(
            _extract_supplier_offer_characteristics(SimpleNamespace(source_payload_json="not-json")),
            {},
        )
        self.assertEqual(
            _extract_supplier_offer_characteristics(
                SimpleNamespace(source_payload_json={"characteristics": {"Площа": "5.796"}})
            ),
            {"Площа": "5.796"},
        )


if __name__ == "__main__":
    unittest.main()
