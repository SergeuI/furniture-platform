from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import cleanup_confirmed_duplicate_fittings as cleanup


class CleanupConfirmedDuplicateFittingsTests(unittest.TestCase):
    def test_dry_run_reports_safe_delete_plan_and_gallery_audits(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "cleanup.db"
            self._create_database(database_path)

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys=ON")
                plan = cleanup._build_plan(connection)

            self.assertFalse(plan["prerequisite_missing"])
            self.assertEqual(plan["counts_before"]["fittings"], 10)
            self.assertEqual(plan["counts_before"]["fitting_images"], 22)
            self.assertEqual(plan["counts_after"]["fittings"], 3)
            self.assertEqual(plan["counts_after"]["fitting_images"], 9)
            self.assertEqual(plan["safe_delete_ids"], [15, 23, 31, 39, 46, 49, 59])
            self.assertEqual(plan["blocked_ids"], [])

            statuses = {candidate.fitting_id: candidate.status for candidate in plan["candidate_plans"]}
            self.assertEqual(
                statuses,
                {
                    15: "SAFE_DELETE",
                    23: "SAFE_DELETE",
                    31: "SAFE_DELETE",
                    39: "SAFE_DELETE",
                    46: "SAFE_DELETE",
                    49: "SAFE_DELETE",
                    59: "SAFE_DELETE",
                },
            )

            galleries = {candidate.fitting_id: candidate.gallery_status for candidate in plan["candidate_plans"]}
            self.assertEqual(galleries[15], "EMPTY")
            self.assertEqual(galleries[23], "EMPTY")
            self.assertEqual(galleries[31], "EMPTY")
            self.assertEqual(galleries[39], "EMPTY")
            self.assertEqual(galleries[46], "IDENTICAL")
            self.assertEqual(galleries[49], "IDENTICAL")
            self.assertEqual(galleries[59], "IDENTICAL")

            offers = {candidate.fitting_id: candidate.offer_status for candidate in plan["candidate_plans"]}
            self.assertEqual(offers[59], "verified")
            self.assertEqual(offers[46], "verified")
            self.assertEqual(offers[49], "not_needed")

    def test_apply_deletes_safe_candidates_and_cascades_duplicate_images(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "cleanup.db"
            self._create_database(database_path)

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys=ON")
                plan = cleanup._build_plan(connection)
                cleanup._apply_plan(connection, plan)
                connection.commit()

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys=ON")
                self.assertEqual(
                    cleanup._integrity_check(connection).lower(),
                    "ok",
                )
                self.assertEqual(cleanup._foreign_key_check(connection), [])
                self.assertEqual(cleanup._counts_snapshot(connection)["fittings"], 3)
                self.assertEqual(cleanup._counts_snapshot(connection)["fitting_images"], 9)
                self.assertEqual(cleanup._counts_snapshot(connection)["fitting_supplier_offers"], 1)
                self.assertEqual(cleanup._counts_snapshot(connection)["fitting_hole_templates"], 0)
                self.assertEqual(cleanup._counts_snapshot(connection)["mounting_node_items"], 0)
                remaining_ids = [
                    row[0]
                    for row in connection.execute("SELECT id FROM fittings ORDER BY id").fetchall()
                ]
                self.assertEqual(remaining_ids, [7, 45, 48])
                offer_rows = connection.execute(
                    """
                    SELECT fitting_id, article
                    FROM fitting_supplier_offers
                    ORDER BY fitting_id
                    """
                ).fetchall()
                self.assertEqual([tuple(row) for row in offer_rows], [(45, "190106")])

    def test_blocks_candidates_with_live_non_cascade_dependencies(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "blocked.db"
            self._create_database(database_path, blocked_candidate_id=15)

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys=ON")
                plan = cleanup._build_plan(connection)

            candidate = next(item for item in plan["candidate_plans"] if item.fitting_id == 15)
            self.assertEqual(candidate.status, "BLOCKED")
            self.assertIn("fitting_hole_templates=1", candidate.reason)
            self.assertIn(15, plan["blocked_ids"])
            self.assertNotIn(15, plan["safe_delete_ids"])

    @staticmethod
    def _create_database(database_path: Path, blocked_candidate_id: int | None = None) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(
                """
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY,
                    catalog_key TEXT,
                    article TEXT,
                    name TEXT,
                    source TEXT,
                    source_url TEXT,
                    source_payload_json TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE suppliers (
                    id INTEGER PRIMARY KEY,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fitting_supplier_offers (
                    id INTEGER PRIMARY KEY,
                    fitting_id INTEGER NOT NULL REFERENCES fittings(id) ON DELETE NO ACTION,
                    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE NO ACTION,
                    article TEXT,
                    source_url TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fitting_hole_templates (
                    id INTEGER PRIMARY KEY,
                    fitting_id INTEGER NOT NULL REFERENCES fittings(id) ON DELETE NO ACTION
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE mounting_node_items (
                    id INTEGER PRIMARY KEY,
                    fitting_id INTEGER NOT NULL REFERENCES fittings(id) ON DELETE NO ACTION
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fitting_images (
                    id INTEGER PRIMARY KEY,
                    fitting_id INTEGER NOT NULL REFERENCES fittings(id) ON DELETE CASCADE,
                    sort_order INTEGER NOT NULL,
                    is_primary INTEGER NOT NULL,
                    source_url TEXT,
                    image_cached_bytes BLOB NOT NULL,
                    image_cached_content_type TEXT NOT NULL,
                    image_sha256 TEXT NOT NULL
                )
                """
            )

            connection.execute(
                "INSERT INTO suppliers (id, code, name) VALUES (?, ?, ?)",
                (1, "viyar", "VIYAR"),
            )

            fixtures = [
                (7, "catalog-key-7", "131761", "Keeper 7", None, None, None),
                (15, "catalog-key-15", "131761", "Duplicate 15", None, None, None),
                (23, "catalog-key-23", "131761", "Duplicate 23", None, None, None),
                (31, "catalog-key-31", "131761", "Duplicate 31", None, None, None),
                (39, "catalog-key-39", "131761", "Duplicate 39", None, None, None),
                (
                    45,
                    "catalog-key-45",
                    "190106",
                    "Keeper 45",
                    "viyar",
                    "https://viyar.ua/ua/catalog/konfirmat-7x50/",
                    json.dumps({"source_site": "viyar", "parsed_item": {"article": "190106"}}, ensure_ascii=False),
                ),
                (
                    46,
                    "catalog-key-46",
                    "190106",
                    "Duplicate 46",
                    "viyar",
                    "https://viyar.ua/ua/catalog/konfirmat-7x50/",
                    json.dumps({"source_site": "viyar", "parsed_item": {"article": "190106"}}, ensure_ascii=False),
                ),
                (
                    48,
                    "catalog-key-48",
                    "61136",
                    "Keeper 48",
                    "viyar",
                    "https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                    json.dumps({"source_site": "viyar", "parsed_item": {"article": "61136"}}, ensure_ascii=False),
                ),
                (
                    49,
                    "catalog-key-49",
                    "61136",
                    "Duplicate 49",
                    "viyar",
                    "https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                    json.dumps({"source_site": "viyar", "parsed_item": {"article": "61136"}}, ensure_ascii=False),
                ),
                (
                    59,
                    "catalog-key-59",
                    "190106",
                    "Duplicate 59",
                    "viyar",
                    "https://viyar.ua/ua/catalog/konfirmat-7x50/",
                    json.dumps({"source_site": "viyar", "parsed_item": {"article": "190106"}}, ensure_ascii=False),
                ),
            ]
            connection.executemany(
                """
                INSERT INTO fittings (
                    id, catalog_key, article, name, source, source_url, source_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                fixtures,
            )

            def add_gallery(fitting_id: int, source_prefix: str, count: int) -> None:
                for index in range(count):
                    content = f"{source_prefix}-{index}".encode("utf-8")
                    sha256 = hashlib.sha256(content).hexdigest()
                    connection.execute(
                        """
                        INSERT INTO fitting_images (
                            fitting_id,
                            sort_order,
                            is_primary,
                            source_url,
                            image_cached_bytes,
                            image_cached_content_type,
                            image_sha256
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            fitting_id,
                            index,
                            1 if index == 0 else 0,
                            f"https://example.test/{source_prefix}/{index}.jpg",
                            content,
                            "image/jpeg",
                            sha256,
                        ),
                    )

            add_gallery(45, "gallery-45", 4)
            add_gallery(46, "gallery-45", 4)
            add_gallery(48, "gallery-48", 5)
            add_gallery(49, "gallery-48", 5)
            add_gallery(59, "gallery-45", 4)

            connection.execute(
                """
                INSERT INTO fitting_supplier_offers (
                    id, fitting_id, supplier_id, article, source_url
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (1, 45, 1, "190106", "https://viyar.ua/ua/catalog/konfirmat-7x50/"),
            )

            if blocked_candidate_id is not None:
                connection.execute(
                    "INSERT INTO fitting_hole_templates (id, fitting_id) VALUES (?, ?)",
                    (1, blocked_candidate_id),
                )

            connection.commit()


if __name__ == "__main__":
    unittest.main()
