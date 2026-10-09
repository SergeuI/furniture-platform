from __future__ import annotations
import unittest
from pathlib import Path
from scripts.product_map_parser import filter_product_map_records, group_for_id, normalize_status, parse_product_map, summarize_product_map_records

class ProductMapParserTests(unittest.TestCase):
    def test_status_mapping_is_explicit_and_safe(self):
        self.assertEqual(normalize_status("[ПЕРЕВІРЕНО]"), "DONE")
        self.assertEqual(normalize_status("[БАЗА]"), "BASE")
        self.assertEqual(normalize_status("[НЕВІДОМИЙ]"), "UNKNOWN")
        self.assertEqual(normalize_status("[БАЗА] + [РОЗРОБКА]"), "IN PROGRESS")

    def test_summary_helper_counts_statuses_and_progress(self):
        self.assertEqual(summarize_product_map_records([]), {"total": 0, "DONE": 0, "IN PROGRESS": 0, "PLANNED": 0, "BLOCKED": 0, "BASE": 0, "V2": 0, "IDEA": 0, "UNKNOWN": 0, "progress": 0})
        records = parse_product_map("docs/MPFC_MASTER_PRODUCT_MAP.md")
        sample = [dict(records[0], normalized_status="DONE")]
        self.assertEqual(summarize_product_map_records(sample)["progress"], 100)
        sample = [dict(records[0], normalized_status=status) for status in ("DONE", "IN PROGRESS", "PLANNED", "BASE")]
        summary = summarize_product_map_records(sample)
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["DONE"], 1)
        self.assertEqual(summary["BASE"], 1)
        self.assertEqual(summary["progress"], 25)
    def test_filter_helper_supports_query_and_status(self):
        records = parse_product_map("docs/MPFC_MASTER_PRODUCT_MAP.md")
        self.assertTrue(all("склад" in " ".join(str(value) for value in (r["title"], r["group"], r["goal"], r["description"])).casefold() for r in filter_product_map_records(records, "склад")))
        self.assertTrue(filter_product_map_records(records, "", "PLANNED"))
        self.assertTrue(all(r["normalized_status"] == "PLANNED" for r in filter_product_map_records(records, "", "PLANNED")))
        combined = filter_product_map_records(records, "склад", "PLANNED")
        self.assertTrue(combined)
        self.assertTrue(all(r["normalized_status"] == "PLANNED" for r in combined))
        self.assertEqual(len(filter_product_map_records(records)), len(records))
    def test_parses_real_map_without_writing(self):
        path = Path("docs/MPFC_MASTER_PRODUCT_MAP.md")
        before = path.read_bytes()
        records = parse_product_map(path)
        after = path.read_bytes()
        self.assertEqual(before, after)
        self.assertEqual(len(records), 16)
        self.assertEqual(records[0]["id"], "CORE-001")
        self.assertEqual(records[0]["group"], "Core / Реєстрація і тарифи")
        self.assertEqual(records[0]["normalized_status"], "PLANNED")
        self.assertTrue(records[0]["source_lines"])

if __name__ == "__main__":
    unittest.main()
