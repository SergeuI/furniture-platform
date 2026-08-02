from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.audit_log import AuditLogModel
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel
from database.repositories.admin_entitlement_repository import AdminEntitlementRepository
from services.entitlement_registry import SYSTEM_ENTITLEMENT_REGISTRY
from services.entitlement_registry_sync_service import EntitlementRegistrySyncService


BOOLEAN_FEATURE_PLAN_DEFAULTS = {
    "mounting_nodes.view": {
        "trial": True,
        "free": False,
        "pro": True,
        "business": True,
    },
    "mounting_nodes.create": {
        "trial": True,
        "free": False,
        "pro": True,
        "business": True,
    },
    "mounting_nodes.edit": {
        "trial": True,
        "free": False,
        "pro": True,
        "business": True,
    },
    "mounting_nodes.delete": {
        "trial": True,
        "free": False,
        "pro": True,
        "business": True,
    },
}


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


class EntitlementRegistrySyncServiceTests(unittest.TestCase):
    def test_dry_run_reports_missing_system_features_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                plan = service.plan_sync()

                self.assertEqual(len(plan["new_features"]), len(SYSTEM_ENTITLEMENT_REGISTRY))
                new_feature_keys = {item["feature_key"] for item in plan["new_features"]}
                self.assertTrue({"mounting_nodes.view", "mounting_nodes.create", "mounting_nodes.edit", "mounting_nodes.delete"}.issubset(new_feature_keys))
                self.assertTrue(all(item["category"] == "mounting_nodes" for item in plan["new_features"] if item["feature_key"].startswith("mounting_nodes.")))
                self.assertEqual({item["sort_order"] for item in plan["new_features"] if item["feature_key"].startswith("mounting_nodes.")}, {10, 20, 30, 40})
                self.assertEqual(plan["metadata_updates"], [])
                self.assertEqual(plan["missing_plan_rows"], [])
                self.assertEqual(plan["conflicts"], [])
                self.assertEqual(plan["unchanged"], [])
                self.assertEqual(plan["db_system_features_missing_from_registry"], [])
                self.assertEqual(session.query(EntitlementFeatureModel).count(), 0)
                self.assertEqual(session.query(PlanEntitlementModel).count(), 0)
                self.assertEqual(session.query(AuditLogModel).count(), 0)

    def test_apply_creates_system_registry_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                first_result = service.apply_sync(actor_user_id="admin", actor_email="admin@example.com")

                self.assertTrue(first_result["applied"])
                self.assertEqual(len(first_result["created_features"]), len(SYSTEM_ENTITLEMENT_REGISTRY))
                self.assertEqual(session.query(EntitlementFeatureModel).count(), len(SYSTEM_ENTITLEMENT_REGISTRY))
                self.assertEqual(session.query(PlanEntitlementModel).count(), len(SYSTEM_ENTITLEMENT_REGISTRY) * 4)
                self.assertEqual(session.query(AuditLogModel).count(), 1)

                mapped_feature_keys = set(BOOLEAN_FEATURE_PLAN_DEFAULTS)
                for feature in session.query(EntitlementFeatureModel).all():
                    self.assertTrue(feature.is_system)

                for feature in session.query(EntitlementFeatureModel).all():
                    entitlements = repo.list_entitlements_for_feature(feature.id)
                    self.assertEqual(len(entitlements), 4)
                    for entitlement in entitlements:
                        if feature.feature_key in mapped_feature_keys:
                            self.assertEqual(
                                entitlement.bool_value,
                                BOOLEAN_FEATURE_PLAN_DEFAULTS[feature.feature_key][entitlement.plan_code],
                            )
                        elif feature.value_type == "boolean":
                            self.assertIsNone(entitlement.bool_value)
                        else:
                            self.assertIsNone(entitlement.bool_value)
                        self.assertIsNone(entitlement.integer_value)
                        self.assertIsNone(entitlement.decimal_value)
                        self.assertIsNone(entitlement.text_value)
                        self.assertFalse(entitlement.is_unlimited)
                        self.assertFalse(entitlement.is_not_applicable)

                sample_feature = repo.get_feature_by_key("materials.view")
                sample_entitlement = repo.get_entitlement(sample_feature.id, "trial")
                sample_entitlement.bool_value = True
                session.commit()

                second_result = service.apply_sync(actor_user_id="admin", actor_email="admin@example.com")
                session.refresh(sample_entitlement)

                self.assertFalse(second_result["applied"])
                self.assertEqual(session.query(EntitlementFeatureModel).count(), len(SYSTEM_ENTITLEMENT_REGISTRY))
                self.assertEqual(session.query(PlanEntitlementModel).count(), len(SYSTEM_ENTITLEMENT_REGISTRY) * 4)
                self.assertEqual(session.query(AuditLogModel).count(), 1)
                self.assertTrue(sample_entitlement.bool_value)

    def test_plan_sync_repairs_blank_boolean_rows_to_registry_defaults(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                service.apply_sync(actor_user_id="admin", actor_email="admin@example.com")

                feature = repo.get_feature_by_key("mounting_nodes.view")
                for plan_code in ("trial", "free", "pro", "business"):
                    entitlement = repo.get_entitlement(feature.id, plan_code)
                    entitlement.bool_value = None
                    entitlement.integer_value = None
                    entitlement.decimal_value = None
                    entitlement.text_value = None
                    entitlement.is_unlimited = False
                    entitlement.is_not_applicable = False
                session.commit()

                plan = service.plan_sync()
                self.assertEqual(
                    plan["missing_plan_rows"],
                    [
                        {
                            "feature_key": "mounting_nodes.view",
                            "missing_plan_codes": ["trial", "free", "pro", "business"],
                        }
                    ],
                )

                result = service.apply_sync(actor_user_id="admin", actor_email="admin@example.com")
                self.assertTrue(result["applied"])
                self.assertEqual(result["created_plan_rows"], [])
                self.assertEqual(session.query(PlanEntitlementModel).count(), len(SYSTEM_ENTITLEMENT_REGISTRY) * 4)

                repaired_feature = repo.get_feature_by_key("mounting_nodes.view")
                repaired_entitlements = repo.list_entitlements_for_feature(repaired_feature.id)
                self.assertEqual(
                    {entitlement.plan_code: entitlement.bool_value for entitlement in repaired_entitlements},
                    BOOLEAN_FEATURE_PLAN_DEFAULTS["mounting_nodes.view"],
                )
                self.assertEqual(service.plan_sync()["missing_plan_rows"], [])

                unmapped_feature = repo.get_feature_by_key("fittings.create")
                unmapped_entitlements = repo.list_entitlements_for_feature(unmapped_feature.id)
                self.assertTrue(all(entitlement.bool_value is None for entitlement in unmapped_entitlements))

    def test_blank_rows_do_not_overwrite_explicit_boolean_overrides(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                service.apply_sync(actor_user_id="admin", actor_email="admin@example.com")

                override_feature = repo.get_feature_by_key("materials.view")
                repo.get_entitlement(override_feature.id, "trial").bool_value = False
                repo.get_entitlement(override_feature.id, "free").bool_value = True

                repair_feature = repo.get_feature_by_key("mounting_nodes.view")
                for plan_code in ("trial", "free", "pro", "business"):
                    entitlement = repo.get_entitlement(repair_feature.id, plan_code)
                    entitlement.bool_value = None
                    entitlement.integer_value = None
                    entitlement.decimal_value = None
                    entitlement.text_value = None
                    entitlement.is_unlimited = False
                    entitlement.is_not_applicable = False
                session.commit()

                result = service.apply_sync(actor_user_id="admin", actor_email="admin@example.com")
                self.assertTrue(result["applied"])

                self.assertFalse(repo.get_entitlement(override_feature.id, "trial").bool_value)
                self.assertTrue(repo.get_entitlement(override_feature.id, "free").bool_value)

    def test_plan_sync_reports_conflicts_for_custom_and_mismatched_system_features(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, _repo):
                custom_feature = EntitlementFeatureModel(
                    feature_key="materials.view",
                    name_uk="Custom duplicate",
                    category="custom",
                    value_type="boolean",
                    is_system=False,
                )
                session.add(custom_feature)

                mismatched_feature = EntitlementFeatureModel(
                    feature_key="fittings.view",
                    name_uk="System mismatch",
                    category="fittings",
                    value_type="integer",
                    is_system=True,
                )
                session.add(mismatched_feature)
                session.commit()

                plan = service.plan_sync()
                conflict_keys = {item["feature_key"] for item in plan["conflicts"]}
                self.assertIn("materials.view", conflict_keys)
                self.assertIn("fittings.view", conflict_keys)

                with self.assertRaises(ValueError):
                    service.apply_sync(actor_user_id="admin", actor_email="admin@example.com")

                self.assertEqual(session.query(AuditLogModel).count(), 0)

    def test_orphaned_system_features_are_reported_but_not_deleted(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                service.apply_sync(actor_user_id="admin", actor_email="admin@example.com")

                feature = EntitlementFeatureModel(
                    feature_key="legacy.system.feature",
                    name_uk="Legacy system",
                    category="legacy",
                    value_type="boolean",
                    is_system=True,
                )
                session.add(feature)
                session.commit()

                plan = service.plan_sync()
                self.assertIn("legacy.system.feature", plan["db_system_features_missing_from_registry"])

                audit_count_before = session.query(AuditLogModel).count()
                result = service.apply_sync(actor_user_id="admin", actor_email="admin@example.com")
                self.assertFalse(result["applied"])
                self.assertEqual(repo.get_feature_by_key("legacy.system.feature").feature_key, "legacy.system.feature")
                self.assertEqual(session.query(AuditLogModel).count(), audit_count_before)

    @staticmethod
    @contextmanager
    def _service_context(database_path: Path):
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
        Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        session = Session()
        repo = AdminEntitlementRepository(session)
        service = EntitlementRegistrySyncService(session=session, repository=repo)
        try:
            yield session, service, repo
        finally:
            session.close()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
