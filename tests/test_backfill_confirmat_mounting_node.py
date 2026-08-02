from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.dependencies import auth as auth_dependencies
from api.routes import mounting_nodes as mounting_nodes_route
from services.mounting_node_service import MountingNodeService
from database.repositories.mounting_node_repository import MountingNodeRepository
from scripts import backfill_confirmat_mounting_node as script


class _AllowedEntitlementService:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def has_feature(self, current_user, feature_key: str) -> bool:
        return feature_key in {"fitting_holes.use", "mounting_nodes.view"}


class _ServiceContext:
    def __init__(self, service: MountingNodeService) -> None:
        self.service = service

    def __enter__(self):
        return self.service

    def __exit__(self, exc_type, exc, tb):
        self.service.close()
        return False


class BackfillConfirmatMountingNodeTests(unittest.TestCase):
    def test_dry_run_reports_plan_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "furniture_platform.db"
            self._create_database(database_path)
            before_snapshot = self._snapshot(database_path)

            stdout = StringIO()
            with redirect_stdout(stdout):
                result = script.main(
                    [
                        "--db-path",
                        str(database_path),
                        "--dry-run",
                    ]
                )

            after_snapshot = self._snapshot(database_path)
            output = stdout.getvalue()

            self.assertEqual(result, 0)
            self.assertEqual(before_snapshot, after_snapshot)
            self.assertIn("Mode: DRY-RUN", output)
            self.assertIn("Node code: mn_confirmat_7x50", output)
            self.assertIn("Template: id=7428", output)
            self.assertIn("Points loaded: 2", output)
            self.assertIn("Current row counts:", output)
            self.assertIn("Expected row counts after apply:", output)
            self.assertIn("mounting_nodes=0", output)
            self.assertEqual(list(database_path.parent.glob("*.bak")), [])

    def test_apply_creates_one_node_one_item_one_link_and_keeps_legacy_rows_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "furniture_platform.db"
            self._create_database(database_path)
            before_snapshot = self._snapshot(database_path)

            stdout = StringIO()
            with redirect_stdout(stdout):
                result = script.main(
                    [
                        "--db-path",
                        str(database_path),
                        "--apply",
                    ]
                )

            output = stdout.getvalue()
            backup_files = list(database_path.parent.glob("*.bak"))

            self.assertEqual(result, 0)
            self.assertIn("Mode: APPLY", output)
            self.assertIn("Backup:", output)
            self.assertIn("Created node id:", output)
            self.assertIn("Created item id:", output)
            self.assertIn("Created template-link id:", output)
            self.assertEqual(len(backup_files), 1)
            self.assertGreater(backup_files[0].stat().st_size, 0)

            after_snapshot = self._snapshot(database_path)
            self.assertEqual(before_snapshot["fittings"], after_snapshot["fittings"])
            self.assertEqual(before_snapshot["fitting_hole_templates"], after_snapshot["fitting_hole_templates"])
            self.assertEqual(before_snapshot["fitting_hole_points"], after_snapshot["fitting_hole_points"])
            self.assertEqual(after_snapshot["mounting_nodes_count"], 1)
            self.assertEqual(after_snapshot["mounting_node_items_count"], 1)
            self.assertEqual(after_snapshot["mounting_node_templates_count"], 1)
            self.assertEqual(after_snapshot["template_7428_point_count"], 2)
            self.assertEqual(after_snapshot["template_7474_link_count"], 0)
            self.assertEqual(after_snapshot["template_7475_link_count"], 0)

            app = FastAPI()
            app.include_router(mounting_nodes_route.router, prefix="/mounting-nodes")
            app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="free")

            engine = create_engine(
                f"sqlite:///{database_path.as_posix()}",
                connect_args={"check_same_thread": False},
            )
            Session = sessionmaker(bind=engine, expire_on_commit=False)
            session = Session()
            service = MountingNodeService(session=session)

            with patch.object(mounting_nodes_route, "EntitlementService", _AllowedEntitlementService):
                with patch.object(mounting_nodes_route, "MountingNodeService", return_value=_ServiceContext(service)):
                    with TestClient(app) as client:
                        list_response = client.get(
                            "/mounting-nodes?search=mn_confirmat_7x50",
                            headers={"Authorization": "Bearer token"},
                        )
                        self.assertEqual(list_response.status_code, 200)
                        list_body = list_response.json()
                        self.assertTrue(list_body["success"])
                        self.assertEqual(len(list_body["nodes"]), 1)
                        self.assertEqual(list_body["nodes"][0]["code"], "mn_confirmat_7x50")

                        node_id = list_body["nodes"][0]["id"]
                        detail_response = client.get(
                            f"/mounting-nodes/{node_id}",
                            headers={"Authorization": "Bearer token"},
                        )

            session.close()
            engine.dispose()

            self.assertEqual(detail_response.status_code, 200)
            detail_body = detail_response.json()
            self.assertTrue(detail_body["success"])
            self.assertEqual(detail_body["node"]["name"], script.DEFAULT_NODE_NAME)
            self.assertEqual(detail_body["node"]["code"], "mn_confirmat_7x50")
            self.assertEqual(len(detail_body["node"]["items"]), 1)
            self.assertEqual(detail_body["node"]["items"][0]["fitting_id"], 1)
            self.assertEqual(detail_body["node"]["items"][0]["fitting_article"], "190106")
            self.assertEqual(detail_body["node"]["items"][0]["quantity"], 1)
            self.assertEqual(len(detail_body["node"]["templates"]), 1)
            self.assertEqual(detail_body["node"]["templates"][0]["template_id"], 7428)
            self.assertEqual(detail_body["node"]["templates"][0]["mounting_variant_key"], "face_to_edge")
            self.assertEqual(detail_body["node"]["templates"][0]["points_count"], 2)
            self.assertTrue(detail_body["node"]["templates"][0]["is_default"])

    def test_second_apply_is_noop_and_reports_already_applied(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "furniture_platform.db"
            self._create_database(database_path)

            first_stdout = StringIO()
            with redirect_stdout(first_stdout):
                script.main(
                    [
                        "--db-path",
                        str(database_path),
                        "--apply",
                    ]
                )

            second_stdout = StringIO()
            with redirect_stdout(second_stdout):
                result = script.main(
                    [
                        "--db-path",
                        str(database_path),
                        "--apply",
                    ]
                )

            self.assertEqual(result, 0)
            self.assertIn("already applied", second_stdout.getvalue())
            self.assertEqual(len(list(database_path.parent.glob("*.bak"))), 1)
            snapshot = self._snapshot(database_path)
            self.assertEqual(snapshot["mounting_nodes_count"], 1)
            self.assertEqual(snapshot["mounting_node_items_count"], 1)
            self.assertEqual(snapshot["mounting_node_templates_count"], 1)

    def test_invalid_fitting_article_aborts_without_changes(self) -> None:
        self._assert_invalid_backfill(
            mutate=lambda path: self._update_row(
                path,
                "fittings",
                "article = 'wrong-article'",
                "id = 1",
            ),
            expected_reason="fitting article must be 190106",
        )

    def test_invalid_fitting_code_aborts_without_changes(self) -> None:
        self._assert_invalid_backfill(
            mutate=lambda path: self._update_row(
                path,
                "fittings",
                "code = 'wrong-code'",
                "id = 1",
            ),
            expected_reason="fitting code must be confirmat_7x50",
        )

    def test_template_with_wrong_fitting_aborts(self) -> None:
        self._assert_invalid_backfill(
            mutate=lambda path: self._update_row(
                path,
                "fitting_hole_templates",
                "fitting_id = 99",
                "id = 7428",
            ),
            expected_reason="does not belong to fitting_id=1",
        )

    def test_wrong_mounting_variant_aborts(self) -> None:
        self._assert_invalid_backfill(
            mutate=lambda path: self._update_row(
                path,
                "fitting_hole_templates",
                "mounting_variant_key = 'surface_mount'",
                "id = 7428",
            ),
            expected_reason="mounting_variant_key must be face_to_edge",
        )

    def test_template_without_required_points_aborts(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "furniture_platform.db"
            self._create_database(database_path, include_second_point=False)
            before_snapshot = self._snapshot(database_path)

            with self.assertRaises(SystemExit) as cm:
                script.main(
                    [
                        "--db-path",
                        str(database_path),
                        "--apply",
                    ]
                )

            self.assertEqual(cm.exception.code, 1)
            after_snapshot = self._snapshot(database_path)
            self.assertEqual(before_snapshot, after_snapshot)
            self.assertEqual(len(list(database_path.parent.glob("*.bak"))), 0)

    def test_existing_node_with_same_code_but_different_content_aborts(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "furniture_platform.db"
            self._create_database(database_path)
            self._insert_conflicting_node(database_path)

            before_snapshot = self._snapshot(database_path)
            with self.assertRaises(SystemExit) as cm:
                script.main(
                    [
                        "--db-path",
                        str(database_path),
                        "--apply",
                    ]
                )

            self.assertEqual(cm.exception.code, 1)
            after_snapshot = self._snapshot(database_path)
            self.assertEqual(before_snapshot, after_snapshot)
            self.assertEqual(len(list(database_path.parent.glob("*.bak"))), 0)

    def test_template_linked_to_other_node_aborts(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "furniture_platform.db"
            self._create_database(database_path)
            self._insert_foreign_link(database_path)

            before_snapshot = self._snapshot(database_path)
            with self.assertRaises(SystemExit) as cm:
                script.main(
                    [
                        "--db-path",
                        str(database_path),
                        "--apply",
                    ]
                )

            self.assertEqual(cm.exception.code, 1)
            after_snapshot = self._snapshot(database_path)
            self.assertEqual(before_snapshot, after_snapshot)
            self.assertEqual(len(list(database_path.parent.glob("*.bak"))), 0)

    def test_transaction_error_rolls_back_partial_records(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "furniture_platform.db"
            self._create_database(database_path)

            before_snapshot = self._snapshot(database_path)
            with patch.object(MountingNodeRepository, "replace_templates", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    script.main(
                        [
                            "--db-path",
                            str(database_path),
                            "--apply",
                        ]
                    )

            after_snapshot = self._snapshot(database_path)
            self.assertEqual(before_snapshot, after_snapshot)
            self.assertEqual(len(list(database_path.parent.glob("*.bak"))), 1)

    @staticmethod
    def _create_database(database_path: Path, *, include_second_point: bool = True) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE users (
                    id TEXT PRIMARY KEY,
                    email TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE service_drilling_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY,
                    city TEXT,
                    article TEXT,
                    code TEXT,
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
                    unit TEXT DEFAULT 'шт',
                    currency TEXT DEFAULT 'UAH',
                    parsed_at TEXT,
                    price_updated_at TEXT,
                    source_payload_json TEXT,
                    owner_user_id TEXT,
                    is_system INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fitting_hole_templates (
                    id INTEGER PRIMARY KEY,
                    fitting_id INTEGER NOT NULL,
                    name TEXT,
                    template_type TEXT,
                    side TEXT,
                    coordinate_system TEXT,
                    mounting_variant_key TEXT NOT NULL DEFAULT 'surface_mount',
                    is_default INTEGER NOT NULL DEFAULT 1,
                    notes TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    bundle_key TEXT,
                    bundle_name TEXT,
                    bundle_order_index INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fitting_hole_points (
                    id INTEGER PRIMARY KEY,
                    template_id INTEGER NOT NULL,
                    label TEXT,
                    x_mm REAL,
                    y_mm REAL,
                    z_mm REAL,
                    diameter_mm REAL,
                    depth_mm REAL,
                    target_panel TEXT,
                    target_surface TEXT,
                    target_side TEXT,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    mirrored INTEGER NOT NULL DEFAULT 0,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    operation TEXT,
                    side TEXT,
                    service_drilling_rule_id INTEGER,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE mounting_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    description TEXT,
                    owner_user_id TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_by_user_id TEXT,
                    updated_by_user_id TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE mounting_node_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id INTEGER NOT NULL,
                    fitting_id INTEGER NOT NULL,
                    role TEXT,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    is_required INTEGER NOT NULL DEFAULT 1,
                    affects_processing INTEGER NOT NULL DEFAULT 1,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(node_id, fitting_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE mounting_node_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id INTEGER NOT NULL,
                    template_id INTEGER NOT NULL UNIQUE,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(node_id, template_id)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO fittings (
                    id, article, code, name, fitting_type, fitting_group, is_system, is_active, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1, "190106", "confirmat_7x50", "Конфірмат 7×50", "confirmat", None, 1, 1, 0),
            )
            for template_id in (7428, 7474, 7475):
                connection.execute(
                    """
                    INSERT INTO fitting_hole_templates (
                        id, fitting_id, name, template_type, side, coordinate_system,
                        mounting_variant_key, is_default, notes, is_active, created_at, updated_at,
                        bundle_key, bundle_name, bundle_order_index
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        template_id,
                        1,
                        "Основний шаблон" if template_id == 7428 else f"Шаблон {template_id}",
                        "manual",
                        "left",
                        "2d",
                        "face_to_edge",
                        1,
                        None,
                        1,
                        "2026-07-29 00:00:00",
                        "2026-07-29 00:00:00",
                        None,
                        None,
                        0,
                    ),
                )
            connection.execute(
                """
                INSERT INTO fitting_hole_points (
                    id, template_id, label, x_mm, y_mm, z_mm, diameter_mm, depth_mm,
                    target_panel, target_surface, target_side, quantity, mirrored,
                    order_index, operation, side, service_drilling_rule_id, notes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    29,
                    7428,
                    "Point 29",
                    0,
                    0,
                    0,
                    7.0,
                    None,
                    "vertical_panel",
                    "plane",
                    "inner_face",
                    1,
                    0,
                    0,
                    "drill",
                    "left",
                    None,
                    None,
                    "2026-07-29 00:00:00",
                    "2026-07-29 00:00:00",
                ),
            )
            if include_second_point:
                connection.execute(
                    """
                    INSERT INTO fitting_hole_points (
                        id, template_id, label, x_mm, y_mm, z_mm, diameter_mm, depth_mm,
                        target_panel, target_surface, target_side, quantity, mirrored,
                        order_index, operation, side, service_drilling_rule_id, notes,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        30,
                        7428,
                        "Point 30",
                        0,
                        0,
                        0,
                        4.5,
                        34.0,
                        "horizontal_panel",
                        "edge",
                        "edge_near_vertical",
                        1,
                        0,
                        1,
                        "drill",
                        "left",
                        None,
                        None,
                        "2026-07-29 00:00:00",
                        "2026-07-29 00:00:00",
                    ),
                )
            connection.commit()

    @staticmethod
    def _update_row(database_path: Path, table_name: str, set_clause: str, where_clause: str) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}")
            connection.commit()

    @staticmethod
    def _insert_conflicting_node(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                INSERT INTO mounting_nodes (
                    code, name, description, owner_user_id, is_active,
                    created_by_user_id, updated_by_user_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "mn_confirmat_7x50",
                    "Conflicting node",
                    "Different content",
                    None,
                    1,
                    None,
                    None,
                    "2026-07-29 00:00:00",
                    "2026-07-29 00:00:00",
                ),
            )
            connection.execute(
                "INSERT INTO mounting_node_items (node_id, fitting_id, role, quantity, is_required, affects_processing, order_index, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, 1, "Other role", 2, 1, 0, 0, "2026-07-29 00:00:00", "2026-07-29 00:00:00"),
            )
            connection.commit()

    @staticmethod
    def _insert_foreign_link(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                INSERT INTO mounting_nodes (
                    code, name, description, owner_user_id, is_active,
                    created_by_user_id, updated_by_user_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "other-node",
                    "Other node",
                    None,
                    None,
                    1,
                    None,
                    None,
                    "2026-07-29 00:00:00",
                    "2026-07-29 00:00:00",
                ),
            )
            connection.execute(
                "INSERT INTO mounting_node_items (node_id, fitting_id, role, quantity, is_required, affects_processing, order_index, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, 1, "Other role", 1, 1, 1, 0, "2026-07-29 00:00:00", "2026-07-29 00:00:00"),
            )
            connection.execute(
                "INSERT INTO mounting_node_templates (node_id, template_id, is_default, order_index, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (1, 7428, 1, 0, "2026-07-29 00:00:00", "2026-07-29 00:00:00"),
            )
            connection.commit()

    def _assert_invalid_backfill(self, mutate, expected_reason: str) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "furniture_platform.db"
            self._create_database(database_path)
            mutate(database_path)

            before_snapshot = self._snapshot(database_path)
            stdout = StringIO()
            with redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as cm:
                    script.main(
                        [
                            "--db-path",
                            str(database_path),
                            "--apply",
                        ]
                    )

            self.assertEqual(cm.exception.code, 1)
            self.assertIn(expected_reason, stdout.getvalue())
            after_snapshot = self._snapshot(database_path)
            self.assertEqual(before_snapshot, after_snapshot)
            self.assertEqual(len(list(database_path.parent.glob("*.bak"))), 0)

    @staticmethod
    def _snapshot(database_path: Path) -> dict[str, object]:
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            return {
                "fittings": [
                    dict(row)
                    for row in connection.execute(
                        "SELECT id, article, code, name, fitting_type, fitting_group, is_system, is_active, sort_order FROM fittings ORDER BY id"
                    ).fetchall()
                ],
                "fitting_hole_templates": [
                    dict(row)
                    for row in connection.execute(
                        "SELECT id, fitting_id, name, mounting_variant_key, is_default, is_active FROM fitting_hole_templates ORDER BY id"
                    ).fetchall()
                ],
                "fitting_hole_points": [
                    dict(row)
                    for row in connection.execute(
                        "SELECT id, template_id, label, x_mm, y_mm, z_mm, diameter_mm, depth_mm, target_panel, target_surface, target_side, quantity, mirrored, order_index FROM fitting_hole_points ORDER BY id"
                    ).fetchall()
                ],
                "mounting_nodes_count": int(
                    connection.execute("SELECT COUNT(*) FROM mounting_nodes").fetchone()[0]
                ),
                "mounting_node_items_count": int(
                    connection.execute("SELECT COUNT(*) FROM mounting_node_items").fetchone()[0]
                ),
                "mounting_node_templates_count": int(
                    connection.execute("SELECT COUNT(*) FROM mounting_node_templates").fetchone()[0]
                ),
                "template_7428_point_count": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM fitting_hole_points WHERE template_id = 7428"
                    ).fetchone()[0]
                ),
                "template_7474_link_count": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM mounting_node_templates WHERE template_id = 7474"
                    ).fetchone()[0]
                ),
                "template_7475_link_count": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM mounting_node_templates WHERE template_id = 7475"
                    ).fetchone()[0]
                ),
            }


if __name__ == "__main__":
    unittest.main()
