from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import export_server_catalog
from scripts import import_server_catalog
from services import fitting_catalog_sync


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2yN0sAAAAASUVORK5CYII="
)

GALLERY_IMAGE_BYTES = [
    PNG_1X1,
    PNG_1X1 + b"1",
    PNG_1X1 + b"2",
    PNG_1X1 + b"3",
]


class FittingCatalogSyncTests(unittest.TestCase):
    def test_source_inference_uses_source_url_when_source_is_missing(self) -> None:
        self.assertEqual(
            fitting_catalog_sync.infer_fitting_source_site(None, "https://viyar.ua/ua/catalog/test/"),
            "viyar",
        )
        self.assertEqual(
            fitting_catalog_sync.infer_fitting_source_site("", "https://kronas.com.ua/catalog/test/"),
            "kronas",
        )
        self.assertEqual(
            fitting_catalog_sync.infer_fitting_source_site(None, "https://mt.ua/products/test"),
            "mt",
        )
        self.assertIsNone(
            fitting_catalog_sync.infer_fitting_source_site(None, "https://example.com/catalog/test"),
        )

    def test_export_and_import_bundle_preserve_global_reference_data(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmpdir_path = Path(tmpdir)
            db_path = tmpdir_path / "source.db"
            bundle_dir = tmpdir_path / "bundle"
            uploads_root = tmpdir_path / "uploads"
            self._create_catalog_database(db_path, uploads_root)

            with patch("services.fitting_catalog_sync.LOCAL_UPLOADS_ROOT", uploads_root):
                export_result = export_server_catalog.export_bundle(db_path, bundle_dir)

            self.assertEqual(export_result["counts"]["suppliers"], 1)
            self.assertEqual(export_result["counts"]["fitting_manufacturers"], 1)
            self.assertEqual(export_result["counts"]["fitting_products"], 1)
            self.assertEqual(export_result["counts"]["fittings"], 1)
            self.assertEqual(export_result["counts"]["fitting_supplier_offers"], 1)
            self.assertEqual(export_result["counts"]["fitting_images"], 1)
            self.assertEqual(export_result["counts"]["fitting_hole_service_rules"], 1)
            self.assertEqual(export_result["counts"]["service_catalog_items"], 1)
            self.assertEqual(export_result["missing_media"], [])

            catalog = export_result["catalog"]
            self.assertEqual([row["code"] for row in catalog["entities"]["suppliers"]], ["viyar"])
            self.assertEqual([row["name"] for row in catalog["entities"]["fitting_manufacturers"]], ["Hettich"])
            self.assertEqual(catalog["entities"]["fitting_supplier_offers"][0]["supplier_code"], "viyar")
            self.assertEqual(catalog["entities"]["fitting_supplier_offers"][0]["fitting_article"], "A-100")
            self.assertEqual(catalog["entities"]["fitting_images"][0]["fitting_article"], "A-100")
            self.assertEqual(catalog["entities"]["fitting_hole_service_rules"][0]["service_source"], "viyar")
            self.assertEqual(
                catalog["entities"]["fitting_hole_service_rules"][0]["service_external_code"],
                "viyar-service-drilling-main-00011",
            )
            self.assertTrue((bundle_dir / "catalog.json").exists())
            self.assertTrue((bundle_dir / "manifest.json").exists())
            self.assertTrue((bundle_dir / "media" / "supplier-logos").exists())
            self.assertTrue((bundle_dir / "media" / "fitting-manufacturer-logos").exists())
            self.assertTrue((bundle_dir / "media" / "fitting-images").exists())

            target_db = tmpdir_path / "target.db"
            self._create_empty_target_database(target_db)

            dry_run = import_server_catalog.import_bundle(target_db, bundle_dir, apply=False)
            self.assertGreaterEqual(dry_run["summary"].get("inserted", 0), 1)
            self.assertEqual(dry_run["conflicts"], [])

            apply_result = import_server_catalog.import_bundle(target_db, bundle_dir, apply=True)
            self.assertEqual(apply_result["conflicts"], [])
            self.assertTrue(apply_result["backup_path"])

            with sqlite3.connect(target_db) as connection:
                connection.row_factory = sqlite3.Row
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0], 2)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_manufacturers").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_products").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fittings").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_supplier_offers").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_images").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_hole_service_rules").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM service_catalog_items").fetchone()[0], 1)
                private_row = connection.execute(
                    "SELECT code, owner_user_id, is_system FROM suppliers WHERE code = ?",
                    ("private-supplier",),
                ).fetchone()
                self.assertEqual(tuple(private_row), ("private-supplier", "user-1", 0))
                self.assertEqual(
                    connection.execute("SELECT logo_url FROM suppliers WHERE code = ?", ("viyar",)).fetchone()[0],
                    "/uploads/supplier-logos/viyar.png",
                )
                self.assertTrue(
                    (target_db.parent / "data" / "uploads" / "supplier-logos" / "viyar.png").exists()
                )
                self.assertTrue(
                    (target_db.parent / "data" / "uploads" / "fitting-manufacturer-logos" / "hettich.png").exists()
                )
                image_row = connection.execute(
                    "SELECT image_cached_bytes, image_sha256 FROM fitting_images WHERE fitting_id = ?",
                    (1,),
                ).fetchone()
                self.assertEqual(hashlib.sha256(image_row["image_cached_bytes"]).hexdigest(), image_row["image_sha256"])
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

            second_apply = import_server_catalog.import_bundle(target_db, bundle_dir, apply=True)
            self.assertGreaterEqual(second_apply["summary"].get("unchanged", 0), 1)
            with sqlite3.connect(target_db) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0], 2)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_supplier_offers").fetchone()[0], 1)

    def test_import_fitting_images_updates_existing_server_row_by_sha_identity(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmpdir_path = Path(tmpdir)
            db_path = tmpdir_path / "source.db"
            bundle_dir = tmpdir_path / "bundle"
            uploads_root = tmpdir_path / "uploads"
            self._create_catalog_database(db_path, uploads_root)

            with patch("services.fitting_catalog_sync.LOCAL_UPLOADS_ROOT", uploads_root):
                export_server_catalog.export_bundle(db_path, bundle_dir)

            target_db = tmpdir_path / "target.db"
            self._create_target_database_with_existing_fitting_image(target_db)

            dry_run = import_server_catalog.import_bundle(target_db, bundle_dir, apply=False)
            self.assertGreaterEqual(dry_run["summary"].get("updated", 0), 1)
            self.assertEqual(dry_run["conflicts"], [])
            with sqlite3.connect(target_db) as connection:
                connection.row_factory = sqlite3.Row
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_images").fetchone()[0], 1)
                self.assertEqual(
                    connection.execute("SELECT sort_order FROM fitting_images WHERE fitting_id = 1").fetchone()[0],
                    7,
                )

            apply_result = import_server_catalog.import_bundle(target_db, bundle_dir, apply=True)
            self.assertEqual(apply_result["conflicts"], [])
            with sqlite3.connect(target_db) as connection:
                connection.row_factory = sqlite3.Row
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_images").fetchone()[0], 1)
                image_row = connection.execute(
                    "SELECT sort_order, is_primary, source_url, image_cached_bytes, image_sha256 FROM fitting_images WHERE fitting_id = 1",
                ).fetchone()
                self.assertEqual(image_row["sort_order"], 0)
                self.assertEqual(image_row["is_primary"], 1)
                self.assertEqual(image_row["source_url"], "https://example.com/a100.png")
                self.assertEqual(hashlib.sha256(image_row["image_cached_bytes"]).hexdigest(), image_row["image_sha256"])
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

            second_apply = import_server_catalog.import_bundle(target_db, bundle_dir, apply=True)
            self.assertGreaterEqual(second_apply["summary"].get("unchanged", 0), 1)
            with sqlite3.connect(target_db) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_images").fetchone()[0], 1)

    def test_import_fitting_images_dedupes_bundle_rows_after_remap(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmpdir_path = Path(tmpdir)
            db_path = tmpdir_path / "source.db"
            bundle_dir = tmpdir_path / "bundle"
            duplicate_bundle_dir = tmpdir_path / "bundle-duplicate"
            uploads_root = tmpdir_path / "uploads"
            self._create_catalog_database(db_path, uploads_root)

            with patch("services.fitting_catalog_sync.LOCAL_UPLOADS_ROOT", uploads_root):
                export_server_catalog.export_bundle(db_path, bundle_dir)

            shutil.copytree(bundle_dir, duplicate_bundle_dir)
            catalog_path = duplicate_bundle_dir / "catalog.json"
            manifest_path = duplicate_bundle_dir / "manifest.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            duplicate_row = dict(catalog["entities"]["fitting_images"][0])
            duplicate_row["sort_order"] = 7
            catalog["entities"]["fitting_images"].append(duplicate_row)
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["catalog_sha256"] = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            target_db = tmpdir_path / "target.db"
            self._create_empty_target_database(target_db)

            dry_run = import_server_catalog.import_bundle(target_db, duplicate_bundle_dir, apply=False)
            self.assertEqual(dry_run["conflicts"], [])
            self.assertGreaterEqual(dry_run["summary"].get("inserted", 0), 1)
            with sqlite3.connect(target_db) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_images").fetchone()[0], 0)

            apply_result = import_server_catalog.import_bundle(target_db, duplicate_bundle_dir, apply=True)
            self.assertEqual(apply_result["conflicts"], [])
            with sqlite3.connect(target_db) as connection:
                connection.row_factory = sqlite3.Row
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_images").fetchone()[0], 1)
                image_row = connection.execute(
                    "SELECT sort_order, source_url, image_sha256 FROM fitting_images WHERE fitting_id = 1",
                ).fetchone()
                self.assertEqual(image_row["sort_order"], 0)
                self.assertEqual(image_row["source_url"], "https://example.com/a100.png")
                self.assertEqual(image_row["image_sha256"], hashlib.sha256(PNG_1X1).hexdigest())

            second_apply = import_server_catalog.import_bundle(target_db, duplicate_bundle_dir, apply=True)
            self.assertGreaterEqual(second_apply["summary"].get("unchanged", 0), 1)
            with sqlite3.connect(target_db) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_images").fetchone()[0], 1)

    def test_import_fitting_images_handles_swap_rotation_and_extra_rows(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmpdir_path = Path(tmpdir)
            db_path = tmpdir_path / "source.db"
            bundle_dir = tmpdir_path / "bundle"
            uploads_root = tmpdir_path / "uploads"
            self._create_three_image_catalog_database(db_path, uploads_root)

            with patch("services.fitting_catalog_sync.LOCAL_UPLOADS_ROOT", uploads_root):
                export_server_catalog.export_bundle(db_path, bundle_dir)

            swap_bundle_dir = tmpdir_path / "bundle-swap"
            rotation_bundle_dir = tmpdir_path / "bundle-rotation"
            shutil.copytree(bundle_dir, swap_bundle_dir)
            shutil.copytree(bundle_dir, rotation_bundle_dir)
            self._rewrite_bundle_sort_orders(swap_bundle_dir, [1, 0, 2])
            self._rewrite_bundle_sort_orders(rotation_bundle_dir, [2, 0, 1])

            swap_target = tmpdir_path / "swap.db"
            self._create_gallery_target_database(swap_target)
            swap_result = import_server_catalog.import_bundle(swap_target, swap_bundle_dir, apply=True)
            self.assertEqual(swap_result["conflicts"], [])
            self.assertGreaterEqual(swap_result["summary"].get("updated", 0), 2)
            with sqlite3.connect(swap_target) as connection:
                self._assert_gallery_orders(
                    connection,
                    [
                        "https://example.com/b-100.png",
                        "https://example.com/a-100.png",
                        "https://example.com/c-100.png",
                    ],
                    [0, 1, 2],
                )
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            swap_second = import_server_catalog.import_bundle(swap_target, swap_bundle_dir, apply=True)
            self.assertEqual(swap_second["summary"].get("inserted", 0), 0)
            self.assertEqual(swap_second["summary"].get("updated", 0), 0)
            self.assertGreaterEqual(swap_second["summary"].get("unchanged", 0), 3)

            rotation_target = tmpdir_path / "rotation.db"
            self._create_gallery_target_database(rotation_target)
            rotation_result = import_server_catalog.import_bundle(rotation_target, rotation_bundle_dir, apply=True)
            self.assertEqual(rotation_result["conflicts"], [])
            with sqlite3.connect(rotation_target) as connection:
                self._assert_gallery_orders(
                    connection,
                    [
                        "https://example.com/b-100.png",
                        "https://example.com/c-100.png",
                        "https://example.com/a-100.png",
                    ],
                    [0, 1, 2],
                )
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            rotation_second = import_server_catalog.import_bundle(rotation_target, rotation_bundle_dir, apply=True)
            self.assertEqual(rotation_second["summary"].get("inserted", 0), 0)
            self.assertEqual(rotation_second["summary"].get("updated", 0), 0)
            self.assertGreaterEqual(rotation_second["summary"].get("unchanged", 0), 3)

            occupied_target = tmpdir_path / "occupied.db"
            self._create_gallery_target_database(occupied_target, include_extra_image=True)
            occupied_dry_run = import_server_catalog.import_bundle(occupied_target, bundle_dir, apply=False)
            self.assertEqual(occupied_dry_run["conflicts"], [])
            with sqlite3.connect(occupied_target) as connection:
                self._assert_gallery_orders(
                    connection,
                    [
                        "https://example.com/a-100.png",
                        "https://example.com/b-100.png",
                        "https://example.com/extra.png",
                        "https://example.com/c-100.png",
                    ],
                    [0, 1, 1, 2],
                )
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            occupied_apply = import_server_catalog.import_bundle(occupied_target, bundle_dir, apply=True)
            self.assertEqual(occupied_apply["conflicts"], [])
            with sqlite3.connect(occupied_target) as connection:
                self._assert_gallery_orders(
                    connection,
                    [
                        "https://example.com/a-100.png",
                        "https://example.com/b-100.png",
                        "https://example.com/c-100.png",
                        "https://example.com/extra.png",
                    ],
                    [0, 1, 2, 3],
                )
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            occupied_second = import_server_catalog.import_bundle(occupied_target, bundle_dir, apply=True)
            self.assertEqual(occupied_second["summary"].get("inserted", 0), 0)
            self.assertEqual(occupied_second["summary"].get("updated", 0), 0)
            self.assertGreaterEqual(occupied_second["summary"].get("unchanged", 0), 4)

    def test_import_fitting_images_leaves_user_owned_gallery_untouched(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmpdir_path = Path(tmpdir)
            target_db = tmpdir_path / "target.db"
            self._create_user_owned_gallery_target_database(target_db)
            with sqlite3.connect(target_db) as connection:
                connection.row_factory = sqlite3.Row
                current_maps = import_server_catalog._load_current_maps(connection)
                fitting_id = connection.execute("SELECT id FROM fittings WHERE article = ?", ("U-100",)).fetchone()[0]
                desired_rows = [
                    {
                        "fitting_id": fitting_id,
                        "sort_order": 0,
                        "is_primary": 1,
                        "source_url": "https://example.com/u-100.png",
                        "image_cached_bytes": PNG_1X1,
                        "image_cached_content_type": "image/png",
                        "image_sha256": hashlib.sha256(PNG_1X1).hexdigest(),
                    }
                ]
                skipped: list[str] = []
                inserted, updated, unchanged = import_server_catalog._sync_fitting_images_for_fitting(
                    connection,
                    fitting_id,
                    desired_rows,
                    current_maps=current_maps,
                    skipped=skipped,
                )
                self.assertEqual((inserted, updated, unchanged), (0, 0, 0))
                self.assertTrue(any(item.startswith("fitting_images:user-owned:") for item in skipped))
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM fitting_images").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT sort_order FROM fitting_images WHERE fitting_id = ?", (fitting_id,)).fetchone()[0], 4)

    def test_import_real_bundle_on_staging_like_copy_is_idempotent(self) -> None:
        bundle_path = Path(r"D:\PY\.server-catalog-sync\20260819-013308")
        self.assertTrue(bundle_path.exists())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmpdir_path = Path(tmpdir)
            target_db = tmpdir_path / "staging-like.db"
            self._create_staging_like_target_database_with_gallery(target_db)

            with sqlite3.connect(target_db) as connection:
                before_rows = connection.execute(
                    """
                    SELECT fittings.article, fitting_images.sort_order, fitting_images.is_primary,
                           fitting_images.source_url, fitting_images.image_sha256
                    FROM fitting_images
                    JOIN fittings ON fittings.id = fitting_images.fitting_id
                    ORDER BY fitting_images.fitting_id, fitting_images.sort_order, fitting_images.id
                    """
                ).fetchall()

            dry_run = import_server_catalog.import_bundle(target_db, bundle_path, apply=False)
            self.assertEqual(dry_run["conflicts"], [])
            self.assertEqual(dry_run["skipped"], [])
            with sqlite3.connect(target_db) as connection:
                after_rows = connection.execute(
                    """
                    SELECT fittings.article, fitting_images.sort_order, fitting_images.is_primary,
                           fitting_images.source_url, fitting_images.image_sha256
                    FROM fitting_images
                    JOIN fittings ON fittings.id = fitting_images.fitting_id
                    ORDER BY fitting_images.fitting_id, fitting_images.sort_order, fitting_images.id
                    """
                ).fetchall()
                self.assertEqual(before_rows, after_rows)
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

            apply_result = import_server_catalog.import_bundle(target_db, bundle_path, apply=True)
            self.assertEqual(apply_result["conflicts"], [])
            with sqlite3.connect(target_db) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM (
                            SELECT fitting_id, image_sha256
                            FROM fitting_images
                            GROUP BY fitting_id, image_sha256
                            HAVING COUNT(*) > 1
                        )
                        """
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM (
                            SELECT fitting_id, sort_order
                            FROM fitting_images
                            GROUP BY fitting_id, sort_order
                            HAVING COUNT(*) > 1
                        )
                        """
                    ).fetchone()[0],
                    0,
                )

            second_apply = import_server_catalog.import_bundle(target_db, bundle_path, apply=True)
            self.assertEqual(second_apply["conflicts"], [])
            self.assertEqual(second_apply["summary"].get("inserted", 0), 0)
            self.assertEqual(second_apply["summary"].get("updated", 0), 0)
            with sqlite3.connect(target_db) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    @staticmethod
    def _rewrite_bundle_sort_orders(bundle_dir: Path, sort_orders: list[int]) -> None:
        catalog_path = bundle_dir / "catalog.json"
        manifest_path = bundle_dir / "manifest.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        for row, sort_order in zip(catalog["entities"]["fitting_images"], sort_orders, strict=True):
            row["sort_order"] = sort_order
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["catalog_sha256"] = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def _assert_gallery_orders(self, connection: sqlite3.Connection, source_urls: list[str], sort_orders: list[int]) -> None:
        rows = connection.execute(
            """
            SELECT fitting_images.source_url, fitting_images.sort_order
            FROM fitting_images
            JOIN fittings ON fittings.id = fitting_images.fitting_id
            ORDER BY fitting_images.sort_order, fitting_images.id
            """
        ).fetchall()
        self_rows = [(row[0], row[1]) for row in rows]
        self.assertEqual(self_rows, list(zip(source_urls, sort_orders, strict=True)))

    @staticmethod
    def _create_three_image_catalog_database(database_path: Path, uploads_root: Path) -> None:
        uploads_root.mkdir(parents=True, exist_ok=True)
        (uploads_root / "supplier-logos").mkdir(parents=True, exist_ok=True)
        (uploads_root / "fitting-manufacturer-logos").mkdir(parents=True, exist_ok=True)
        (uploads_root / "supplier-logos" / "viyar.png").write_bytes(PNG_1X1)
        (uploads_root / "fitting-manufacturer-logos" / "hettich.png").write_bytes(PNG_1X1)

        with sqlite3.connect(database_path) as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    logo_url TEXT,
                    owner_user_id TEXT,
                    is_system INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_manufacturers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    description TEXT,
                    website_url TEXT,
                    logo_url TEXT,
                    country_code TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT UNIQUE,
                    code TEXT,
                    name TEXT NOT NULL,
                    brand TEXT,
                    description TEXT,
                    manufacturer_id INTEGER,
                    series_id INTEGER,
                    category_id INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    catalog_key TEXT NOT NULL UNIQUE,
                    city TEXT,
                    code TEXT,
                    article TEXT,
                    name TEXT,
                    price REAL,
                    stock TEXT,
                    fitting_type TEXT,
                    fitting_group TEXT,
                    image_url TEXT,
                    image_cached_bytes BLOB,
                    image_cached_content_type TEXT,
                    source_url TEXT,
                    source TEXT,
                    brand TEXT,
                    description TEXT,
                    unit TEXT,
                    currency TEXT,
                    parsed_at TEXT,
                    price_updated_at TEXT,
                    source_payload_json TEXT,
                    owner_user_id TEXT,
                    technical_product_id INTEGER,
                    is_system INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fitting_id INTEGER NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_primary INTEGER NOT NULL DEFAULT 0,
                    source_url TEXT,
                    image_cached_bytes BLOB NOT NULL,
                    image_cached_content_type TEXT NOT NULL,
                    image_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE service_catalog_items (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_code TEXT NOT NULL,
                    parent_external_code TEXT,
                    owner_user_id TEXT,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    item_type TEXT NOT NULL DEFAULT 'service',
                    folder_path TEXT,
                    description TEXT,
                    full_description TEXT,
                    article TEXT,
                    unit TEXT,
                    base_price REAL,
                    currency TEXT,
                    source_url TEXT,
                    rules_source_url TEXT,
                    is_calculable INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_synced_at TEXT,
                    price_sync_status TEXT,
                    price_source_label TEXT
                );
                CREATE TABLE fitting_hole_service_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT,
                    diameter_min_mm REAL,
                    diameter_max_mm REAL,
                    depth_min_mm REAL,
                    depth_max_mm REAL,
                    service_catalog_item_id TEXT,
                    source TEXT,
                    city TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_hole_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fitting_id INTEGER NOT NULL,
                    name TEXT,
                    template_type TEXT,
                    side TEXT,
                    coordinate_system TEXT,
                    mounting_variant_key TEXT NOT NULL DEFAULT 'surface_mount',
                    is_default INTEGER NOT NULL DEFAULT 1,
                    notes TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    bundle_key TEXT,
                    bundle_name TEXT,
                    bundle_order_index INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE fitting_hole_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    label TEXT,
                    x_mm REAL,
                    y_mm REAL,
                    z_mm REAL,
                    target_panel TEXT,
                    target_surface TEXT,
                    target_side TEXT,
                    diameter_mm REAL,
                    depth_mm REAL,
                    side TEXT,
                    operation TEXT,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    mirrored INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    service_drilling_rule_id INTEGER
                );
                """
            )
            connection.execute(
                "INSERT INTO suppliers (code, name, logo_url, owner_user_id, is_system, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                ("viyar", "VIYAR", "/uploads/supplier-logos/viyar.png", None, 1, 1),
            )
            connection.execute(
                "INSERT INTO fitting_manufacturers (code, name, logo_url, is_active) VALUES (?, ?, ?, ?)",
                ("hettich", "Hettich", "/uploads/fitting-manufacturer-logos/hettich.png", 1),
            )
            connection.execute(
                "INSERT INTO fitting_products (article, code, name, brand, manufacturer_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                ("A-100", "A-100", "Product A", "Hettich", 1, 1),
            )
            connection.execute(
                "INSERT INTO fitting_products (article, code, name, brand, manufacturer_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                ("B-100", "B-100", "Product B", "Hettich", 1, 1),
            )
            connection.execute(
                "INSERT INTO fitting_products (article, code, name, brand, manufacturer_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                ("C-100", "C-100", "Product C", "Hettich", 1, 1),
            )
            for index, article in enumerate(["A-100", "B-100", "C-100"], start=1):
                connection.execute(
                    """
                    INSERT INTO fittings (
                        catalog_key,
                        article,
                        name,
                        price,
                        stock,
                        source_url,
                        source,
                        brand,
                        description,
                        unit,
                        currency,
                        technical_product_id,
                        owner_user_id,
                        is_system,
                        is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"catalog-key-{article.lower()}",
                        article,
                        f"Fitting {article}",
                        10.0 + index,
                        "in stock",
                        f"https://example.com/{article.lower()}",
                        None,
                        "Hettich",
                        f"Description {article}",
                        "шт",
                        "UAH",
                        index,
                        None,
                        1,
                        1,
                    ),
                )
            for fitting_id, sort_order in ((1, 0), (1, 1), (1, 2)):
                article = ["A-100", "B-100", "C-100"][sort_order]
                connection.execute(
                    "INSERT INTO fitting_images (fitting_id, sort_order, is_primary, source_url, image_cached_bytes, image_cached_content_type, image_sha256) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        fitting_id,
                        sort_order,
                        1 if sort_order == 0 else 0,
                        f"https://example.com/{article.lower()}.png",
                        GALLERY_IMAGE_BYTES[sort_order],
                        "image/png",
                        hashlib.sha256(GALLERY_IMAGE_BYTES[sort_order]).hexdigest(),
                    ),
                )
            connection.commit()

    @staticmethod
    def _create_gallery_target_database(database_path: Path, *, include_extra_image: bool = False) -> None:
        FittingCatalogSyncTests._create_empty_target_database(database_path)
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                "INSERT INTO suppliers (code, name, logo_url, owner_user_id, is_system, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                ("viyar", "VIYAR", "/uploads/supplier-logos/viyar.png", None, 1, 1),
            )
            manufacturer_id = connection.execute(
                "INSERT INTO fitting_manufacturers (code, name, logo_url, is_active) VALUES (?, ?, ?, ?)",
                ("hettich", "Hettich", "/uploads/fitting-manufacturer-logos/hettich.png", 1),
            ).lastrowid
            product_id = connection.execute(
                "INSERT INTO fitting_products (article, code, name, brand, manufacturer_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                ("A-100", "A-100", "Existing product A-100", "Hettich", manufacturer_id, 1),
            ).lastrowid
            fitting_id = connection.execute(
                """
                INSERT INTO fittings (
                    catalog_key,
                    article,
                    name,
                    price,
                    stock,
                    source_url,
                    source,
                    brand,
                    description,
                    unit,
                    currency,
                    technical_product_id,
                    owner_user_id,
                    is_system,
                    is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "existing-a-100",
                    "A-100",
                    "Existing A-100",
                    20.0,
                    "in stock",
                    "https://example.com/a-100.png",
                    None,
                    "Hettich",
                    "Existing A-100",
                    "шт",
                    "UAH",
                    product_id,
                    None,
                    1,
                    1,
                ),
            ).lastrowid
            for sort_order, (source_url, image_bytes) in enumerate(
                [
                    ("https://example.com/a-100.png", GALLERY_IMAGE_BYTES[0]),
                    ("https://example.com/b-100.png", GALLERY_IMAGE_BYTES[1]),
                    ("https://example.com/c-100.png", GALLERY_IMAGE_BYTES[2]),
                ]
            ):
                connection.execute(
                    "INSERT INTO fitting_images (fitting_id, sort_order, is_primary, source_url, image_cached_bytes, image_cached_content_type, image_sha256) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        fitting_id,
                        sort_order,
                        1 if sort_order == 0 else 0,
                        source_url,
                        image_bytes,
                        "image/png",
                        hashlib.sha256(image_bytes).hexdigest(),
                    ),
                )
            if include_extra_image:
                connection.execute(
                    "INSERT INTO fitting_images (fitting_id, sort_order, is_primary, source_url, image_cached_bytes, image_cached_content_type, image_sha256) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        1,
                        1,
                        0,
                        "https://example.com/extra.png",
                        GALLERY_IMAGE_BYTES[3],
                        "image/png",
                        hashlib.sha256(GALLERY_IMAGE_BYTES[3]).hexdigest(),
                    ),
                )
            connection.commit()

    @staticmethod
    def _create_user_owned_gallery_target_database(database_path: Path) -> None:
        FittingCatalogSyncTests._create_empty_target_database(database_path)
        with sqlite3.connect(database_path) as connection:
            manufacturer_id = connection.execute(
                "INSERT INTO fitting_manufacturers (code, name, logo_url, is_active) VALUES (?, ?, ?, ?)",
                ("hettich", "Hettich", "/uploads/fitting-manufacturer-logos/hettich.png", 1),
            ).lastrowid
            product_id = connection.execute(
                "INSERT INTO fitting_products (article, code, name, brand, manufacturer_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                ("U-100", "U-100", "User product", "Hettich", manufacturer_id, 1),
            ).lastrowid
            fitting_id = connection.execute(
                """
                INSERT INTO fittings (
                    catalog_key,
                    article,
                    name,
                    price,
                    stock,
                    source_url,
                    source,
                    brand,
                    description,
                    unit,
                    currency,
                    technical_product_id,
                    owner_user_id,
                    is_system,
                    is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "user-owned-key",
                    "U-100",
                    "User fitting",
                    99.0,
                    "in stock",
                    "https://example.com/u-100",
                    None,
                    "Hettich",
                    "User-owned fitting",
                    "шт",
                    "UAH",
                    product_id,
                    "user-1",
                    0,
                    1,
                ),
            ).lastrowid
            connection.execute(
                "INSERT INTO fitting_images (fitting_id, sort_order, is_primary, source_url, image_cached_bytes, image_cached_content_type, image_sha256) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    fitting_id,
                    4,
                    1,
                    "https://example.com/u-100.png",
                    PNG_1X1,
                    "image/png",
                    hashlib.sha256(PNG_1X1).hexdigest(),
                ),
            )
            connection.commit()

    @staticmethod
    def _create_catalog_database(database_path: Path, uploads_root: Path) -> None:
        uploads_root.mkdir(parents=True, exist_ok=True)
        (uploads_root / "supplier-logos").mkdir(parents=True, exist_ok=True)
        (uploads_root / "fitting-manufacturer-logos").mkdir(parents=True, exist_ok=True)
        (uploads_root / "supplier-logos" / "viyar.png").write_bytes(PNG_1X1)
        (uploads_root / "fitting-manufacturer-logos" / "hettich.png").write_bytes(PNG_1X1)

        with sqlite3.connect(database_path) as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    logo_url TEXT,
                    owner_user_id TEXT,
                    is_system INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_manufacturers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    description TEXT,
                    website_url TEXT,
                    logo_url TEXT,
                    country_code TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_series (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manufacturer_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    parent_id INTEGER,
                    description TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT UNIQUE,
                    code TEXT,
                    name TEXT NOT NULL,
                    brand TEXT,
                    description TEXT,
                    manufacturer_id INTEGER,
                    series_id INTEGER,
                    category_id INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    catalog_key TEXT NOT NULL UNIQUE,
                    city TEXT,
                    code TEXT,
                    article TEXT,
                    name TEXT,
                    price REAL,
                    stock TEXT,
                    fitting_type TEXT,
                    fitting_group TEXT,
                    image_url TEXT,
                    image_cached_bytes BLOB,
                    image_cached_content_type TEXT,
                    source_url TEXT,
                    source TEXT,
                    brand TEXT,
                    description TEXT,
                    unit TEXT,
                    currency TEXT,
                    parsed_at TEXT,
                    price_updated_at TEXT,
                    source_payload_json TEXT,
                    owner_user_id TEXT,
                    technical_product_id INTEGER,
                    is_system INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_supplier_offers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fitting_id INTEGER NOT NULL,
                    supplier_id INTEGER NOT NULL,
                    article TEXT,
                    external_product_id TEXT,
                    source_url TEXT,
                    price REAL,
                    currency TEXT DEFAULT 'UAH',
                    unit TEXT DEFAULT 'шт',
                    stock TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 0,
                    parsed_at TEXT,
                    price_updated_at TEXT,
                    source_payload_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fitting_id INTEGER NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_primary INTEGER NOT NULL DEFAULT 0,
                    source_url TEXT,
                    image_cached_bytes BLOB NOT NULL,
                    image_cached_content_type TEXT NOT NULL,
                    image_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE service_catalog_items (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_code TEXT NOT NULL,
                    parent_external_code TEXT,
                    owner_user_id TEXT,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    item_type TEXT NOT NULL DEFAULT 'service',
                    folder_path TEXT,
                    description TEXT,
                    full_description TEXT,
                    article TEXT,
                    unit TEXT,
                    base_price REAL,
                    currency TEXT,
                    source_url TEXT,
                    rules_source_url TEXT,
                    is_calculable INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_synced_at TEXT,
                    price_sync_status TEXT,
                    price_source_label TEXT
                );
                CREATE TABLE fitting_hole_service_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT,
                    diameter_min_mm REAL,
                    diameter_max_mm REAL,
                    depth_min_mm REAL,
                    depth_max_mm REAL,
                    service_catalog_item_id TEXT,
                    source TEXT,
                    city TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_hole_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fitting_id INTEGER NOT NULL,
                    name TEXT,
                    template_type TEXT,
                    side TEXT,
                    coordinate_system TEXT,
                    mounting_variant_key TEXT NOT NULL DEFAULT 'surface_mount',
                    is_default INTEGER NOT NULL DEFAULT 1,
                    notes TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    bundle_key TEXT,
                    bundle_name TEXT,
                    bundle_order_index INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE fitting_hole_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    label TEXT,
                    x_mm REAL,
                    y_mm REAL,
                    z_mm REAL,
                    target_panel TEXT,
                    target_surface TEXT,
                    target_side TEXT,
                    diameter_mm REAL,
                    depth_mm REAL,
                    side TEXT,
                    operation TEXT,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    mirrored INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    service_drilling_rule_id INTEGER
                );
                """
            )
            connection.execute(
                "INSERT INTO suppliers (code, name, logo_url, owner_user_id, is_system, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                ("viyar", "VIYAR", "/uploads/supplier-logos/viyar.png", None, 1, 1),
            )
            connection.execute(
                "INSERT INTO suppliers (code, name, owner_user_id, is_system, is_active) VALUES (?, ?, ?, ?, ?)",
                ("private-supplier", "Private", "user-1", 0, 1),
            )
            connection.execute(
                "INSERT INTO fitting_manufacturers (code, name, logo_url, is_active) VALUES (?, ?, ?, ?)",
                ("hettich", "Hettich", "/uploads/fitting-manufacturer-logos/hettich.png", 1),
            )
            connection.execute(
                "INSERT INTO fitting_categories (code, name, is_active) VALUES (?, ?, ?)",
                ("hinges", "Hinges", 1),
            )
            connection.execute(
                "INSERT INTO fitting_products (article, code, name, brand, manufacturer_id, category_id, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("A-100", "A-100", "Test product", "Hettich", 1, 1, 1),
            )
            connection.execute(
                """
                INSERT INTO fittings (
                    catalog_key,
                    article,
                    name,
                    price,
                    stock,
                    source_url,
                    source,
                    brand,
                    description,
                    unit,
                    currency,
                    technical_product_id,
                    owner_user_id,
                    is_system,
                    is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "catalog-key-a100",
                    "A-100",
                    "Test fitting",
                    10.5,
                    "in stock",
                    "https://viyar.ua/ua/catalog/test-a100/",
                    None,
                    "Hettich",
                    "Test fitting description",
                    "шт",
                    "UAH",
                    1,
                    None,
                    1,
                    1,
                ),
            )
            connection.execute(
                "INSERT INTO fitting_supplier_offers (fitting_id, supplier_id, article, source_url, price, currency, unit, stock, is_active, priority) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, 1, "A-100", "https://viyar.ua/ua/catalog/test-a100/", 10.5, "UAH", "шт", "in stock", 1, 100),
            )
            connection.execute(
                "INSERT INTO fitting_images (fitting_id, sort_order, is_primary, source_url, image_cached_bytes, image_cached_content_type, image_sha256) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, 0, 1, "https://example.com/a100.png", PNG_1X1, "image/png", hashlib.sha256(PNG_1X1).hexdigest()),
            )
            service_id = "8e811ec0-a14d-4e09-b96e-8cb5f206a248"
            connection.execute(
                "INSERT INTO service_catalog_items (id, source, external_code, owner_user_id, name, slug, item_type, folder_path, article, unit, base_price, currency, source_url, rules_source_url, is_calculable, sort_order, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    service_id,
                    "viyar",
                    "viyar-service-drilling-main-00011",
                    None,
                    "Свердління отворів",
                    "prisadka-service",
                    "service",
                    "viyar-services/prisadka",
                    "00011",
                    "service",
                    8.82,
                    "UAH",
                    "https://viyar.ua/ua/catalog/sverlenie_otverstiy/",
                    "https://viyar.ua/ua/catalog/sverlenie_otverstiy/",
                    1,
                    0,
                    1,
                ),
            )
            connection.execute(
                "INSERT INTO fitting_hole_service_rules (operation, diameter_min_mm, service_catalog_item_id, source, is_active, priority, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("drill", 8.0, service_id, "viyar", 1, 0, "Test"),
            )
            connection.commit()

    @staticmethod
    def _create_empty_target_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    logo_url TEXT,
                    owner_user_id TEXT,
                    is_system INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_manufacturers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    description TEXT,
                    website_url TEXT,
                    logo_url TEXT,
                    country_code TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_series (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manufacturer_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    parent_id INTEGER,
                    description TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT UNIQUE,
                    code TEXT,
                    name TEXT NOT NULL,
                    brand TEXT,
                    description TEXT,
                    manufacturer_id INTEGER,
                    series_id INTEGER,
                    category_id INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    catalog_key TEXT NOT NULL UNIQUE,
                    city TEXT,
                    code TEXT,
                    article TEXT,
                    name TEXT,
                    price REAL,
                    stock TEXT,
                    fitting_type TEXT,
                    fitting_group TEXT,
                    image_url TEXT,
                    image_cached_bytes BLOB,
                    image_cached_content_type TEXT,
                    source_url TEXT,
                    source TEXT,
                    brand TEXT,
                    description TEXT,
                    unit TEXT,
                    currency TEXT,
                    parsed_at TEXT,
                    price_updated_at TEXT,
                    source_payload_json TEXT,
                    owner_user_id TEXT,
                    technical_product_id INTEGER,
                    is_system INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_supplier_offers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fitting_id INTEGER NOT NULL,
                    supplier_id INTEGER NOT NULL,
                    article TEXT,
                    external_product_id TEXT,
                    source_url TEXT,
                    price REAL,
                    currency TEXT DEFAULT 'UAH',
                    unit TEXT DEFAULT 'шт',
                    stock TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 0,
                    parsed_at TEXT,
                    price_updated_at TEXT,
                    source_payload_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fitting_id INTEGER NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_primary INTEGER NOT NULL DEFAULT 0,
                    source_url TEXT,
                    image_cached_bytes BLOB NOT NULL,
                    image_cached_content_type TEXT NOT NULL,
                    image_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE service_catalog_items (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_code TEXT NOT NULL,
                    parent_external_code TEXT,
                    owner_user_id TEXT,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    item_type TEXT NOT NULL DEFAULT 'service',
                    folder_path TEXT,
                    description TEXT,
                    full_description TEXT,
                    article TEXT,
                    unit TEXT,
                    base_price REAL,
                    currency TEXT,
                    source_url TEXT,
                    rules_source_url TEXT,
                    is_calculable INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_synced_at TEXT,
                    price_sync_status TEXT,
                    price_source_label TEXT
                );
                CREATE TABLE fitting_hole_service_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT,
                    diameter_min_mm REAL,
                    diameter_max_mm REAL,
                    depth_min_mm REAL,
                    depth_max_mm REAL,
                    service_catalog_item_id TEXT,
                    source TEXT,
                    city TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE fitting_hole_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fitting_id INTEGER NOT NULL,
                    name TEXT,
                    template_type TEXT,
                    side TEXT,
                    coordinate_system TEXT,
                    mounting_variant_key TEXT NOT NULL DEFAULT 'surface_mount',
                    is_default INTEGER NOT NULL DEFAULT 1,
                    notes TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    bundle_key TEXT,
                    bundle_name TEXT,
                    bundle_order_index INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE fitting_hole_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    label TEXT,
                    x_mm REAL,
                    y_mm REAL,
                    z_mm REAL,
                    target_panel TEXT,
                    target_surface TEXT,
                    target_side TEXT,
                    diameter_mm REAL,
                    depth_mm REAL,
                    side TEXT,
                    operation TEXT,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    mirrored INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    service_drilling_rule_id INTEGER
                );
                """
            )
            connection.execute(
                "INSERT INTO suppliers (code, name, owner_user_id, is_system, is_active) VALUES (?, ?, ?, ?, ?)",
                ("private-supplier", "Private", "user-1", 0, 1),
            )
            connection.commit()

    @staticmethod
    def _create_target_database_with_existing_fitting_image(database_path: Path) -> None:
        FittingCatalogSyncTests._create_empty_target_database(database_path)
        with sqlite3.connect(database_path) as connection:
            supplier_id = connection.execute(
                "INSERT INTO suppliers (code, name, logo_url, owner_user_id, is_system, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                ("viyar", "VIYAR", "/uploads/supplier-logos/viyar.png", None, 1, 1),
            ).lastrowid
            manufacturer_id = connection.execute(
                "INSERT INTO fitting_manufacturers (code, name, logo_url, is_active) VALUES (?, ?, ?, ?)",
                ("hettich", "Hettich", "/uploads/fitting-manufacturer-logos/hettich.png", 1),
            ).lastrowid
            category_id = connection.execute(
                "INSERT INTO fitting_categories (code, name, is_active) VALUES (?, ?, ?)",
                ("hinges", "Hinges", 1),
            ).lastrowid
            product_id = connection.execute(
                "INSERT INTO fitting_products (article, code, name, brand, manufacturer_id, category_id, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("A-100", "A-100", "Test product", "Hettich", manufacturer_id, category_id, 1),
            ).lastrowid
            fitting_id = connection.execute(
                """
                INSERT INTO fittings (
                    catalog_key,
                    article,
                    name,
                    price,
                    stock,
                    source_url,
                    source,
                    brand,
                    description,
                    unit,
                    currency,
                    technical_product_id,
                    owner_user_id,
                    is_system,
                    is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "catalog-key-a100",
                    "A-100",
                    "Test fitting",
                    10.5,
                    "in stock",
                    "https://viyar.ua/ua/catalog/test-a100/",
                    None,
                    "Hettich",
                    "Test fitting description",
                    "шт",
                    "UAH",
                    product_id,
                    None,
                    1,
                    1,
                ),
            ).lastrowid
            connection.execute(
                "INSERT INTO fitting_images (fitting_id, sort_order, is_primary, source_url, image_cached_bytes, image_cached_content_type, image_sha256) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (fitting_id, 7, 0, "https://example.com/existing-a100.png", PNG_1X1, "image/png", hashlib.sha256(PNG_1X1).hexdigest()),
            )
            connection.commit()

    @staticmethod
    def _create_staging_like_target_database(database_path: Path) -> None:
        FittingCatalogSyncTests._create_target_database_with_existing_fitting_image(database_path)
        with sqlite3.connect(database_path) as connection:
            manufacturer_id = connection.execute(
                "SELECT id FROM fitting_manufacturers WHERE code = ?",
                ("hettich",),
            ).fetchone()[0]
            category_id = connection.execute(
                "SELECT id FROM fitting_categories WHERE code = ?",
                ("hinges",),
            ).fetchone()[0]
            for index in range(2, 14):
                article = f"EXIST-{index:02d}"
                product_id = connection.execute(
                    "INSERT INTO fitting_products (article, code, name, brand, manufacturer_id, category_id, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (article, article, f"Existing product {index}", "Hettich", manufacturer_id, category_id, 1),
                ).lastrowid
                connection.execute(
                    """
                    INSERT INTO fittings (
                        catalog_key,
                        article,
                        name,
                        price,
                        stock,
                        source_url,
                        source,
                        brand,
                        description,
                        unit,
                        currency,
                        technical_product_id,
                        owner_user_id,
                        is_system,
                        is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"catalog-key-{article.lower()}",
                        article,
                        f"Existing fitting {index}",
                        10.5 + index,
                        "in stock",
                        f"https://example.com/{article.lower()}",
                        None,
                        "Hettich",
                        f"Existing fitting description {index}",
                        "шт",
                        "UAH",
                        product_id,
                        None,
                        1,
                        1,
                    ),
                )
            connection.commit()

    @staticmethod
    def _create_staging_like_target_database_with_gallery(database_path: Path) -> None:
        FittingCatalogSyncTests._create_staging_like_target_database(database_path)
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("DELETE FROM fitting_images")
            fittings = connection.execute("SELECT id, article FROM fittings ORDER BY id").fetchall()
            for row in fittings:
                fitting_id = row["id"]
                article = row["article"]
                for sort_order, image_bytes in enumerate(GALLERY_IMAGE_BYTES[:3]):
                    connection.execute(
                        "INSERT INTO fitting_images (fitting_id, sort_order, is_primary, source_url, image_cached_bytes, image_cached_content_type, image_sha256) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            fitting_id,
                            sort_order,
                            1 if sort_order == 0 else 0,
                            f"https://example.com/{article.lower()}-{sort_order}.png",
                            image_bytes,
                            "image/png",
                            hashlib.sha256(image_bytes).hexdigest(),
                        ),
                    )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
