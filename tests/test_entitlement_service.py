from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel
from database.repositories.plan_entitlement_repository import PlanEntitlementRepository
from services import subscription_service
from services.entitlement_service import (
    ADMIN_EFFECTIVE_PLAN,
    EntitlementAccessDeniedError,
    EntitlementService,
)


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@dataclass
class UserStub:
    role: str | None = None
    trial_started_at: object | None = None
    trial_ends_at: object | None = None


class EntitlementServiceTests(unittest.TestCase):
    def test_get_effective_plan_maps_trial_premium_business_and_admin(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as service:
                self.assertEqual(service.get_effective_plan(UserStub(role="free")), "free")
                self.assertEqual(service.get_effective_plan(UserStub(role="pro")), "pro")
                self.assertEqual(service.get_effective_plan(UserStub(role="admin")), ADMIN_EFFECTIVE_PLAN)
                self.assertEqual(service.get_effective_plan(UserStub(role=None)), "free")
                self.assertEqual(service.get_effective_plan(UserStub(role="unknown")), "free")

                trial_started_at = datetime.utcnow() - timedelta(days=1)
                trial_ends_at = datetime.utcnow() + timedelta(days=6)
                trial_user = UserStub(
                    role="free",
                    trial_started_at=trial_started_at,
                    trial_ends_at=trial_ends_at,
                )
                self.assertEqual(service.get_effective_plan(trial_user), "trial")

                with patch.object(subscription_service, "get_effective_plan", return_value="trial") as mocked:
                    self.assertEqual(service.get_effective_plan(UserStub(role="premium")), "trial")
                    mocked.assert_called_once()

                with patch.object(subscription_service, "get_effective_plan", return_value="premium") as mocked:
                    self.assertEqual(service.get_effective_plan(UserStub(role="premium")), "business")
                    mocked.assert_called_once()

    def test_get_entitlement_and_has_feature_cover_plan_mapping_and_admin_bypass(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as service:
                free_user = UserStub(role="free")
                pro_user = UserStub(role="pro")
                premium_user = UserStub(role="premium")
                admin_user = UserStub(role="admin")
                trial_window_user = UserStub(
                    role="free",
                    trial_started_at=datetime.utcnow() - timedelta(hours=1),
                    trial_ends_at=datetime.utcnow() + timedelta(days=6),
                )

                free_limit = service.get_entitlement(free_user, "ai_scan_limit")
                self.assertTrue(free_limit.exists)
                self.assertFalse(free_limit.allowed)

                trial_limit = service.get_entitlement(trial_window_user, "ai_scan_limit")
                self.assertTrue(trial_limit.allowed)
                self.assertEqual(trial_limit.integer_value, 10)
                self.assertTrue(service.has_feature(trial_window_user, "ai_scan_limit"))

                pro_limit = service.get_entitlement(pro_user, "ai_scan_limit")
                self.assertTrue(pro_limit.allowed)
                self.assertEqual(pro_limit.integer_value, 25)

                legacy_limit = service.get_entitlement(premium_user, "ai_scan_limit")
                self.assertEqual(legacy_limit.effective_plan, "business")
                self.assertTrue(legacy_limit.allowed)
                self.assertTrue(legacy_limit.is_unlimited)

                self.assertEqual(service.get_effective_plan(trial_window_user), "trial")

                self.assertTrue(service.has_feature(trial_window_user, "beta_toggle"))
                self.assertFalse(service.has_feature(free_user, "beta_toggle"))
                self.assertFalse(service.has_feature(free_user, "nullable_bool_feature"))
                self.assertFalse(service.has_feature(free_user, "empty_text_feature"))
                self.assertTrue(service.has_feature(pro_user, "support_level"))
                self.assertTrue(service.has_feature(pro_user, "theme_mode"))
                self.assertFalse(service.has_feature(premium_user, "empty_text_feature"))

                empty_text = service.get_entitlement(admin_user, "empty_text_feature")
                self.assertTrue(empty_text.exists)
                self.assertTrue(empty_text.allowed)

                inactive = service.get_entitlement(admin_user, "inactive_feature")
                self.assertFalse(inactive.exists)
                self.assertFalse(inactive.allowed)

                missing = service.get_entitlement(admin_user, "missing_feature")
                self.assertFalse(missing.exists)
                self.assertFalse(missing.allowed)

                admin_bypass = service.get_entitlement(admin_user, "missing_entitlement_feature")
                self.assertTrue(admin_bypass.exists)
                self.assertTrue(admin_bypass.allowed)

    def test_get_limit_and_check_limit_cover_numeric_and_safe_denials(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as service:
                free_user = UserStub(role="free")
                pro_user = UserStub(role="pro")
                premium_user = UserStub(role="premium")
                admin_user = UserStub(role="admin")
                trial_window_user = UserStub(
                    role="free",
                    trial_started_at=datetime.utcnow() - timedelta(hours=1),
                    trial_ends_at=datetime.utcnow() + timedelta(days=6),
                )

                free_limit = service.get_limit(free_user, "ai_scan_limit")
                self.assertEqual(free_limit.status, "access_denied")
                self.assertFalse(service.check_limit(free_user, "ai_scan_limit", 1))

                trial_limit = service.get_limit(trial_window_user, "ai_scan_limit")
                self.assertEqual(trial_limit.status, "limited")
                self.assertEqual(trial_limit.limit_value, 10)
                self.assertTrue(service.check_limit(trial_window_user, "ai_scan_limit", 9))
                self.assertFalse(service.check_limit(trial_window_user, "ai_scan_limit", 10))
                self.assertFalse(service.check_limit(trial_window_user, "ai_scan_limit", 11))

                pro_decimal = service.get_limit(pro_user, "storage_limit")
                self.assertEqual(pro_decimal.status, "limited")
                self.assertEqual(pro_decimal.limit_value, Decimal("2.75"))
                self.assertTrue(service.check_limit(pro_user, "storage_limit", Decimal("2.70")))
                self.assertFalse(service.check_limit(pro_user, "storage_limit", Decimal("2.75")))
                self.assertFalse(service.check_limit(pro_user, "storage_limit", Decimal("2.80")))

                premium_unlimited = service.get_limit(premium_user, "ai_scan_limit")
                self.assertEqual(premium_unlimited.status, "unlimited")
                self.assertTrue(service.check_limit(premium_user, "ai_scan_limit", 10_000))

                admin_unlimited = service.get_limit(admin_user, "ai_scan_limit")
                self.assertEqual(admin_unlimited.status, "unlimited")
                self.assertTrue(service.check_limit(admin_user, "ai_scan_limit", 10_000))

                self.assertEqual(service.get_limit(free_user, "support_level").status, "wrong_value_type")
                self.assertEqual(service.get_limit(free_user, "beta_toggle").status, "wrong_value_type")
                self.assertEqual(service.get_limit(free_user, "empty_text_feature").status, "wrong_value_type")
                self.assertEqual(service.get_limit(free_user, "inactive_feature").status, "access_denied")

                with self.assertRaises(ValueError):
                    service.check_limit(free_user, "ai_scan_limit", -1)
                with self.assertRaises(ValueError):
                    service.check_limit(free_user, "ai_scan_limit", None)

    def test_is_not_applicable_denies_all_access_paths(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as service:
                user = UserStub(role="free")

                resolution = service.get_entitlement(user, "not_applicable_feature")
                self.assertTrue(resolution.exists)
                self.assertTrue(resolution.is_not_applicable)
                self.assertFalse(resolution.allowed)

                self.assertFalse(service.has_feature(user, "not_applicable_feature"))

                limit = service.get_limit(user, "not_applicable_feature")
                self.assertEqual(limit.status, "not_applicable")
                self.assertFalse(service.check_limit(user, "not_applicable_feature", 0))

                with self.assertRaises(EntitlementAccessDeniedError):
                    service.require_feature(user, "not_applicable_feature")

    def test_empty_and_unknown_roles_remain_safe_and_free(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as service:
                empty_role_user = UserStub(role="")
                unknown_role_user = UserStub(role="mystery")

                self.assertEqual(service.get_effective_plan(empty_role_user), "free")
                self.assertEqual(service.get_effective_plan(unknown_role_user), "free")

                self.assertFalse(service.has_feature(empty_role_user, "ai_scan_limit"))
                self.assertFalse(service.has_feature(unknown_role_user, "ai_scan_limit"))

                self.assertFalse(service.get_entitlement(empty_role_user, "ai_scan_limit").allowed)
                self.assertFalse(service.get_entitlement(unknown_role_user, "ai_scan_limit").allowed)

    def test_require_feature_returns_resolution_or_raises_domain_error(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as service:
                trial_window_user = UserStub(
                    role="free",
                    trial_started_at=datetime.utcnow() - timedelta(hours=1),
                    trial_ends_at=datetime.utcnow() + timedelta(days=6),
                )
                allowed = service.require_feature(trial_window_user, "ai_scan_limit")
                self.assertTrue(allowed.allowed)
                self.assertEqual(allowed.feature_key, "ai_scan_limit")

                with self.assertRaises(EntitlementAccessDeniedError):
                    service.require_feature(UserStub(role="free"), "ai_scan_limit")

                with self.assertRaises(EntitlementAccessDeniedError):
                    service.require_feature(UserStub(role="admin"), "inactive_feature")

    def test_get_entitlement_uses_subscription_service_helper(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as service:
                user = UserStub(role="premium")

                with patch.object(subscription_service, "get_effective_plan", return_value="premium") as mocked:
                    result = service.get_entitlement(user, "ai_scan_limit")
                    self.assertEqual(result.effective_plan, "business")
                    mocked.assert_called_once_with(user)

    def test_invalid_feature_key_is_rejected_safely(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as service:
                with self.assertRaises(ValueError):
                    service.get_entitlement(UserStub(role="free"), "")
                with self.assertRaises(ValueError):
                    service.get_limit(UserStub(role="free"), " ")

    @staticmethod
    @contextmanager
    def _service_context(database_path: Path):
        engine, session = EntitlementServiceTests._create_session(database_path)
        repo = PlanEntitlementRepository(session)
        EntitlementServiceTests._seed_features(session)
        EntitlementServiceTests._seed_entitlements(session)
        service = EntitlementService(session=session, repository=repo)
        try:
            yield service
        finally:
            session.close()
            engine.dispose()

    @staticmethod
    def _create_session(database_path: Path):
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
            ],
        )
        Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        return engine, Session()

    @staticmethod
    def _seed_features(session) -> None:
        session.add_all(
            [
                EntitlementFeatureModel(
                    feature_key="beta_toggle",
                    name_uk="Бета-перемикач",
                    category="admin",
                    sort_order=2,
                    value_type="boolean",
                ),
                EntitlementFeatureModel(
                    feature_key="ai_scan_limit",
                    name_uk="Ліміт AI-сканів",
                    category="limits",
                    sort_order=1,
                    value_type="integer",
                ),
                EntitlementFeatureModel(
                    feature_key="missing_entitlement_feature",
                    name_uk="Feature без entitlement",
                    category="limits",
                    sort_order=4,
                    value_type="boolean",
                ),
                EntitlementFeatureModel(
                    feature_key="not_applicable_feature",
                    name_uk="Not applicable feature",
                    category="limits",
                    sort_order=99,
                    value_type="integer",
                ),
                EntitlementFeatureModel(
                    feature_key="storage_limit",
                    name_uk="Ліміт сховища",
                    category="limits",
                    sort_order=0,
                    value_type="decimal",
                ),
                EntitlementFeatureModel(
                    feature_key="empty_text_feature",
                    name_uk="Порожній текст",
                    category="support",
                    sort_order=0,
                    value_type="text",
                ),
                EntitlementFeatureModel(
                    feature_key="support_level",
                    name_uk="Рівень підтримки",
                    category="support",
                    sort_order=1,
                    value_type="text",
                ),
                EntitlementFeatureModel(
                    feature_key="theme_mode",
                    name_uk="Режим теми",
                    category="support",
                    sort_order=2,
                    value_type="enum",
                ),
                EntitlementFeatureModel(
                    feature_key="nullable_bool_feature",
                    name_uk="Nullable bool",
                    category="support",
                    sort_order=3,
                    value_type="boolean",
                ),
                EntitlementFeatureModel(
                    feature_key="inactive_feature",
                    name_uk="Неактивна feature",
                    category="support",
                    sort_order=4,
                    value_type="boolean",
                    is_active=False,
                ),
            ]
        )
        session.commit()

    @staticmethod
    def _seed_entitlements(session) -> None:
        feature_ids = {
            row.feature_key: row.id
            for row in session.query(EntitlementFeatureModel).all()
        }
        session.add_all(
            [
                PlanEntitlementModel(
                    feature_id=feature_ids["beta_toggle"],
                    plan_code="trial",
                    bool_value=True,
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["beta_toggle"],
                    plan_code="free",
                    bool_value=False,
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["ai_scan_limit"],
                    plan_code="trial",
                    integer_value=10,
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["ai_scan_limit"],
                    plan_code="pro",
                    integer_value=25,
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["ai_scan_limit"],
                    plan_code="business",
                    is_unlimited=True,
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["storage_limit"],
                    plan_code="trial",
                    decimal_value=Decimal("1.5"),
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["storage_limit"],
                    plan_code="pro",
                    decimal_value=Decimal("2.75"),
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["storage_limit"],
                    plan_code="business",
                    is_unlimited=True,
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["support_level"],
                    plan_code="trial",
                    text_value="standard",
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["support_level"],
                    plan_code="pro",
                    text_value="priority",
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["empty_text_feature"],
                    plan_code="business",
                    text_value="",
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["theme_mode"],
                    plan_code="trial",
                    text_value="light",
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["theme_mode"],
                    plan_code="pro",
                    text_value="dark",
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["theme_mode"],
                    plan_code="business",
                    text_value="system",
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["nullable_bool_feature"],
                    plan_code="free",
                    bool_value=None,
                ),
                PlanEntitlementModel(
                    feature_id=feature_ids["not_applicable_feature"],
                    plan_code="free",
                    is_not_applicable=True,
                ),
            ]
        )
        session.commit()


if __name__ == "__main__":
    unittest.main()
