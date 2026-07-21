from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts import backfill_system_catalog_ownership as migration


ADMIN_ID = "39fae34c-7012-474a-927e-66d9b08b7cf0"
USER_ID = "user-1"


class BackfillSystemCatalogOwnershipTests(unittest.TestCase):
    def test_dry_run_reports_valid_and_already_system_rows_without_changes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "catalog.db"
            self._create_database(database_path)

            before_snapshot = self._snapshot(database_path)
            stdout = StringIO()
            with redirect_stdout(stdout):
                result = migration.main(
                    [
                        "--database",
                        str(database_path),
                        "--material-id",
                        "1759",
                        "--material-id",
                        "1760",
                        "--fitting-id",
                        "42",
                        "--fitting-id",
                        "43",
                    ]
                )

            after_snapshot = self._snapshot(database_path)
            output = stdout.getvalue()

            self.assertEqual(result, 0)
            self.assertEqual(before_snapshot, after_snapshot)
            self.assertIn("Mode: DRY-RUN", output)
            self.assertIn("valid candidates: 2", output)
            self.assertIn("invalid selections: 0", output)
            self.assertIn("already system: 2", output)
            self.assertIn("can_apply=true", output)
            self.assertEqual(list(database_path.parent.glob("*.bak")), [])

    def test_apply_backfills_selected_rows_and_writes_one_audit_event(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "catalog.db"
            self._create_database(database_path)

            stdout = StringIO()
            with redirect_stdout(stdout):
                result = migration.main(
                    [
                        "--database",
                        str(database_path),
                        "--apply",
                        "--material-id",
                        "1759",
                        "--fitting-id",
                        "42",
                    ]
                )

            output = stdout.getvalue()
            backup_files = list(database_path.parent.glob("*.bak"))

            self.assertEqual(result, 0)
            self.assertIn("Mode: APPLY", output)
            self.assertIn("Backup:", output)
            self.assertEqual(len(backup_files), 1)

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                material = self._material(connection, 1759)
                fitting = self._fitting(connection, 42)
                audit_rows = connection.execute(
                    "SELECT action, entity_type, entity_id, details FROM audit_logs ORDER BY created_at"
                ).fetchall()

            self.assertIsNotNone(material)
            self.assertEqual(material["is_default"], 1)
            self.assertIsNone(material["owner_user_id"])
            self.assertEqual(material["name"], "Legacy Material")
            self.assertEqual(material["article"], "139601")
            self.assertEqual(material["image"], "https://example.com/material-1759.jpg")
            self.assertEqual(material["source_url"], "https://example.com/material-1759")

            self.assertIsNotNone(fitting)
            self.assertEqual(fitting["is_system"], 1)
            self.assertIsNone(fitting["owner_user_id"])
            self.assertEqual(fitting["name"], "Legacy Fitting")
            self.assertEqual(fitting["article"], "23913")
            self.assertEqual(fitting["price"], 11.25)
            self.assertEqual(fitting["image_url"], "https://example.com/fitting-42.jpg")
            self.assertEqual(fitting["source_url"], "https://example.com/fitting-42")

            self.assertEqual(len(audit_rows), 1)
            self.assertEqual(audit_rows[0]["action"], "catalog.system_ownership.backfilled")
            self.assertEqual(audit_rows[0]["entity_type"], "catalog")
            self.assertEqual(audit_rows[0]["entity_id"], "system_catalog_ownership")
            details = json.loads(audit_rows[0]["details"])
            self.assertEqual(details["source"], "cli")
            self.assertEqual(details["material_ids"], [1759])
            self.assertEqual(details["fitting_ids"], [42])
            self.assertEqual(details["material_count"], 1)
            self.assertEqual(details["fitting_count"], 1)

    def test_apply_rolls_back_when_invalid_id_is_mixed_with_valid_rows(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "catalog.db"
            self._create_database(database_path)

            before_snapshot = self._snapshot(database_path)
            with self.assertRaises(SystemExit):
                migration.main(
                    [
                        "--database",
                        str(database_path),
                        "--apply",
                        "--material-id",
                        "1759",
                        "--fitting-id",
                        "999",
                    ]
                )

            after_snapshot = self._snapshot(database_path)

            self.assertEqual(before_snapshot, after_snapshot)
            self.assertEqual(list(database_path.parent.glob("*.bak")), [])

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                material = self._material(connection, 1759)
                audit_count = connection.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]

            self.assertIsNotNone(material)
            self.assertEqual(material["is_default"], 0)
            self.assertEqual(material["owner_user_id"], ADMIN_ID)
            self.assertEqual(audit_count, 0)

    def test_apply_on_already_system_rows_is_noop_without_backup_or_audit(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "catalog.db"
            self._create_database(database_path)

            stdout = StringIO()
            with redirect_stdout(stdout):
                result = migration.main(
                    [
                        "--database",
                        str(database_path),
                        "--apply",
                        "--material-id",
                        "1760",
                        "--fitting-id",
                        "43",
                    ]
                )

            output = stdout.getvalue()

            self.assertEqual(result, 0)
            self.assertIn("No changes required.", output)
            self.assertEqual(list(database_path.parent.glob("*.bak")), [])

            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                material = self._material(connection, 1760)
                fitting = self._fitting(connection, 43)
                audit_count = connection.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]

            self.assertIsNotNone(material)
            self.assertEqual(material["is_default"], 1)
            self.assertIsNone(material["owner_user_id"])
            self.assertIsNotNone(fitting)
            self.assertEqual(fitting["is_system"], 1)
            self.assertIsNone(fitting["owner_user_id"])
            self.assertEqual(audit_count, 0)

    @staticmethod
    def _create_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE users (
                    id TEXT PRIMARY KEY,
                    role TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE materials (
                    id INTEGER PRIMARY KEY,
                    article TEXT,
                    name TEXT,
                    image TEXT,
                    source_url TEXT,
                    owner_user_id TEXT,
                    is_default INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE fittings (
                    id INTEGER PRIMARY KEY,
                    article TEXT,
                    name TEXT,
                    price REAL,
                    image_url TEXT,
                    source_url TEXT,
                    owner_user_id TEXT,
                    is_system INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE audit_logs (
                    id TEXT PRIMARY KEY,
                    actor_user_id TEXT NOT NULL,
                    actor_email TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    details TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.executemany(
                "INSERT INTO users (id, role) VALUES (?, ?)",
                [
                    (ADMIN_ID, "admin"),
                    (USER_ID, "free"),
                ],
            )
            connection.executemany(
                """
                INSERT INTO materials (
                    id, article, name, image, source_url, owner_user_id, is_default
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        1759,
                        "139601",
                        "Legacy Material",
                        "https://example.com/material-1759.jpg",
                        "https://example.com/material-1759",
                        ADMIN_ID,
                        0,
                    ),
                    (
                        1760,
                        "135440",
                        "System Material",
                        "https://example.com/material-1760.jpg",
                        "https://example.com/material-1760",
                        None,
                        1,
                    ),
                    (
                        1761,
                        "107446",
                        "User Material",
                        "https://example.com/material-1761.jpg",
                        "https://example.com/material-1761",
                        USER_ID,
                        0,
                    ),
                ],
            )
            connection.executemany(
                """
                INSERT INTO fittings (
                    id, article, name, price, image_url, source_url, owner_user_id, is_system
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        42,
                        "23913",
                        "Legacy Fitting",
                        11.25,
                        "https://example.com/fitting-42.jpg",
                        "https://example.com/fitting-42",
                        ADMIN_ID,
                        0,
                    ),
                    (
                        43,
                        "52244",
                        "System Fitting",
                        12.5,
                        "https://example.com/fitting-43.jpg",
                        "https://example.com/fitting-43",
                        None,
                        1,
                    ),
                    (
                        44,
                        "57412",
                        "User Fitting",
                        13.75,
                        "https://example.com/fitting-44.jpg",
                        "https://example.com/fitting-44",
                        USER_ID,
                        0,
                    ),
                ],
            )
            connection.commit()

    @staticmethod
    def _material(connection: sqlite3.Connection, material_id: int) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM materials WHERE id = ?",
            (material_id,),
        ).fetchone()

    @staticmethod
    def _fitting(connection: sqlite3.Connection, fitting_id: int) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM fittings WHERE id = ?",
            (fitting_id,),
        ).fetchone()

    @staticmethod
    def _snapshot(database_path: Path) -> dict[str, object]:
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            material_rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM materials ORDER BY id"
                ).fetchall()
            ]
            fitting_rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM fittings ORDER BY id"
                ).fetchall()
            ]
            audit_rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM audit_logs ORDER BY id"
                ).fetchall()
            ]
        return {
            "materials": material_rows,
            "fittings": fitting_rows,
            "audit_logs": audit_rows,
        }


if __name__ == "__main__":
    unittest.main()
