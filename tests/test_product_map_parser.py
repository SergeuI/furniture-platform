from __future__ import annotations
import unittest
import tempfile
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
        self.assertEqual(len(records), 22)
        self.assertEqual(records[0]["id"], "CORE-001")
        self.assertEqual(records[0]["group"], "Core / Реєстрація і тарифи")
        self.assertEqual(records[0]["normalized_status"], "PLANNED")
        records_by_id = {record["id"]: record for record in records}
        for record_id in ("CORE-3D-001", "CORE-CAD-001", "CORE-KIN-001", "UX-TOOLS-001"):
            self.assertIn(record_id, records_by_id)
            self.assertTrue(records_by_id[record_id]["description"])
        self.assertEqual(records_by_id["CORE-001"]["description"], records_by_id["CORE-001"]["goal"])
        self.assertTrue(records[0]["source_lines"])

    def test_table_only_id_is_parsed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.md"
            path.write_text(
                "| ID | Напрям | Бажаний результат | Статус | Ключові залежності |\n"
                "|---|---|---|---|---|\n"
                "| TEST-001 | Тест | Мета тесту | [ПЛАН] | CORE-001 |\n",
                encoding="utf-8",
            )
            record = parse_product_map(path)[0]
            self.assertEqual(record["id"], "TEST-001")
            self.assertEqual(record["description"], "Мета тесту")

    def test_heading_only_id_is_parsed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.md"
            path.write_text(
                "## TEST-002 — Заголовок тесту\n\nОпис із заголовка.\n\n"
                "**Критерії приймання:** критерій тесту.\n",
                encoding="utf-8",
            )
            record = parse_product_map(path)[0]
            self.assertEqual(record["id"], "TEST-002")
            self.assertEqual(record["title"], "Заголовок тесту")
            self.assertEqual(record["original_status"], "")
            self.assertEqual(record["normalized_status"], "UNKNOWN")
            self.assertIn("Опис із заголовка.", record["description"])
            self.assertEqual(record["acceptance_criteria"], "критерій тесту.")

    def test_table_and_heading_id_has_one_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.md"
            path.write_text(
                "| ID | Напрям | Бажаний результат | Статус | Ключові залежності |\n"
                "|---|---|---|---|---|\n"
                "| TEST-003 | Табличний тест | Таблична мета | [УЗГОДЖЕНО] | Немає |\n\n"
                "### TEST-003 — Деталі тесту\n\nОпис тесту.\n",
                encoding="utf-8",
            )
            records = parse_product_map(path)
            self.assertEqual([record["id"] for record in records], ["TEST-003"])
            self.assertEqual(records[0]["section"], "TEST-003 — Деталі тесту")
            self.assertIn("Опис тесту.", records[0]["description"])

if __name__ == "__main__":
    unittest.main()
