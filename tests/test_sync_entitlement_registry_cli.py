from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.audit_log import AuditLogModel
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


class SyncEntitlementRegistryCliTests(unittest.TestCase):
    def test_dry_run_is_read_only_and_does_not_create_backup(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "registry.db"
            self._create_stage1_database(database_path)

            before_stat = database_path.stat()
            before_backups = self._backup_files(database_path)

            result = self._run_cli(database_path)

            after_stat = database_path.stat()
            after_backups = self._backup_files(database_path)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Mode: DRY-RUN", result.stdout)
            self.assertIn("New features: 17", result.stdout)
            self.assertEqual(before_stat.st_size, after_stat.st_size)
            self.assertEqual(before_stat.st_mtime_ns, after_stat.st_mtime_ns)
            self.assertEqual(before_backups, after_backups)

            with self._session(database_path) as session:
                self.assertEqual(session.query(EntitlementFeatureModel).count(), 0)
                self.assertEqual(session.query(PlanEntitlementModel).count(), 0)
                self.assertEqual(session.query(AuditLogModel).count(), 0)

    def test_apply_creates_registry_and_backup(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "registry.db"
            self._create_stage1_database(database_path)

            result = self._run_cli(database_path, "--apply")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Mode: APPLY", result.stdout)
            self.assertIn("Applied: True", result.stdout)
            self.assertIn("Backup:", result.stdout)

            backups = self._backup_files(database_path)
            self.assertEqual(len(backups), 1)
            self.assertGreater(backups[0].stat().st_size, 0)

            with self._session(database_path) as session:
                features = session.query(EntitlementFeatureModel).order_by(EntitlementFeatureModel.feature_key).all()
                entitlements = session.query(PlanEntitlementModel).all()

                self.assertEqual(len(features), 17)
                self.assertTrue(all(feature.is_system for feature in features))
                self.assertEqual(len(entitlements), 68)
                self.assertEqual(session.query(AuditLogModel).count(), 1)

                for entitlement in entitlements:
                    self.assertIsNone(entitlement.bool_value)
                    self.assertIsNone(entitlement.integer_value)
                    self.assertIsNone(entitlement.decimal_value)
                    self.assertIsNone(entitlement.text_value)
                    self.assertFalse(entitlement.is_unlimited)
                    self.assertFalse(entitlement.is_not_applicable)

    def test_repeat_apply_is_idempotent_and_does_not_create_new_audit(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "registry.db"
            self._create_stage1_database(database_path)

            first_result = self._run_cli(database_path, "--apply")
            self.assertEqual(first_result.returncode, 0, first_result.stdout + first_result.stderr)
            first_backups = self._backup_files(database_path)

            with self._session(database_path) as session:
                before_feature_count = session.query(EntitlementFeatureModel).count()
                before_plan_count = session.query(PlanEntitlementModel).count()
                before_audit_count = session.query(AuditLogModel).count()

            second_result = self._run_cli(database_path, "--apply")

            self.assertEqual(second_result.returncode, 0, second_result.stdout + second_result.stderr)
            self.assertIn("No changes required.", second_result.stdout)
            self.assertEqual(first_backups, self._backup_files(database_path))

            with self._session(database_path) as session:
                self.assertEqual(session.query(EntitlementFeatureModel).count(), before_feature_count)
                self.assertEqual(session.query(PlanEntitlementModel).count(), before_plan_count)
                self.assertEqual(session.query(AuditLogModel).count(), before_audit_count)

    def test_conflict_apply_blocks_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "registry.db"
            self._create_stage1_database(database_path)

            with self._session(database_path) as session:
                session.add(
                    EntitlementFeatureModel(
                        feature_key="materials.view",
                        name_uk="Custom materials view",
                        description_uk="Custom collision",
                        category="custom",
                        value_type="boolean",
                        is_system=False,
                    )
                )
                session.commit()

            result = self._run_cli(database_path, "--apply")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Conflicts:", result.stdout)
            self.assertEqual(self._backup_files(database_path), [])

            with self._session(database_path) as session:
                self.assertEqual(session.query(EntitlementFeatureModel).count(), 1)
                self.assertEqual(session.query(PlanEntitlementModel).count(), 0)
                self.assertEqual(session.query(AuditLogModel).count(), 0)
                feature = session.query(EntitlementFeatureModel).one()
                self.assertEqual(feature.feature_key, "materials.view")
                self.assertFalse(feature.is_system)

    @staticmethod
    def _run_cli(database_path: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "sync_entitlement_registry.py"
        project_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = str(project_root)
        return subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--database",
                str(database_path),
                *extra_args,
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            env=env,
        )

    @staticmethod
    def _backup_files(database_path: Path) -> list[Path]:
        return sorted(database_path.parent.glob(f"{database_path.name}.*.bak"))

    @staticmethod
    def _create_stage1_database(database_path: Path) -> None:
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", _enable_foreign_keys)
        Base.metadata.create_all(
            engine,
            tables=[
                EntitlementFeatureModel.__table__,
                PlanEntitlementModel.__table__,
                AuditLogModel.__table__,
            ],
        )
        engine.dispose()

    @staticmethod
    def _session(database_path: Path):
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", _enable_foreign_keys)
        Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        session = Session()

        class _SessionContext:
            def __enter__(self_inner):
                return session

            def __exit__(self_inner, exc_type, exc, tb):
                session.close()
                engine.dispose()

        return _SessionContext()


if __name__ == "__main__":
    unittest.main()
