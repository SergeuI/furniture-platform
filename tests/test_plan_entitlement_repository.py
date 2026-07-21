from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel
from database.repositories.plan_entitlement_repository import (
    PlanEntitlementRepository,
)


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


class PlanEntitlementRepositoryTests(unittest.TestCase):
    def test_get_feature_by_key_and_list_features_are_sorted(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._session_context(Path(tmpdir) / "entitlements.db") as session:
                self._seed_features(session)

                repo = PlanEntitlementRepository(session)

                self.assertIsNone(repo.get_feature_by_key("missing_feature"))
                self.assertIsNotNone(repo.get_feature_by_key("inactive_feature", active_only=False))
                self.assertIsNone(repo.get_feature_by_key("inactive_feature"))

                features = repo.list_features()
                self.assertEqual(
                    [feature.feature_key for feature in features],
                    [
                        "beta_toggle",
                        "storage_limit",
                        "ai_scan_limit",
                        "missing_entitlement_feature",
                        "not_applicable_feature",
                        "empty_text_feature",
                        "support_level",
                        "theme_mode",
                        "nullable_bool_feature",
                    ],
                )

                all_features = repo.list_features(active_only=False)
                self.assertEqual(
                    [feature.feature_key for feature in all_features][-1],
                    "inactive_feature",
                )

    def test_plan_entitlement_lookup_and_validation_are_read_only(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._session_context(Path(tmpdir) / "entitlements.db") as session:
                self._seed_features(session)
                self._seed_entitlements(session)

                repo = PlanEntitlementRepository(session)
                ai_scan_feature = repo.get_feature_by_key("ai_scan_limit")
                self.assertIsNotNone(ai_scan_feature)

                with patch.object(session, "commit", side_effect=AssertionError("commit")):
                    with patch.object(session, "flush", side_effect=AssertionError("flush")):
                        entitlement = repo.get_plan_entitlement(ai_scan_feature.id, "pro")
                        self.assertIsNotNone(entitlement)
                        self.assertEqual(entitlement.integer_value, 25)

                        with self.assertRaises(ValueError):
                            repo.get_plan_entitlement(ai_scan_feature.id, "starter")

                        with self.assertRaises(ValueError):
                            repo.get_entitlement_by_feature_key("ai_scan_limit", "starter")

                        self.assertIsNone(
                            repo.get_entitlement_by_feature_key("missing_feature", "pro")
                        )

                record = repo.get_entitlement_by_feature_key("missing_entitlement_feature", "pro")
                self.assertIsNotNone(record)
                self.assertIsNone(record.entitlement)
                self.assertEqual(record.feature.feature_key, "missing_entitlement_feature")

    def test_list_plan_entitlements_returns_sorted_feature_definitions(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._session_context(Path(tmpdir) / "entitlements.db") as session:
                self._seed_features(session)
                self._seed_entitlements(session)

                repo = PlanEntitlementRepository(session)

                records = repo.list_plan_entitlements("business")
                self.assertEqual(
                    [record.feature.feature_key for record in records],
                    [
                        "beta_toggle",
                        "storage_limit",
                        "ai_scan_limit",
                        "missing_entitlement_feature",
                        "not_applicable_feature",
                        "empty_text_feature",
                        "support_level",
                        "theme_mode",
                        "nullable_bool_feature",
                    ],
                )
                self.assertTrue(all(record.entitlement is None or record.entitlement.plan_code == "business" for record in records))

                business_ai = next(record for record in records if record.feature.feature_key == "ai_scan_limit")
                self.assertIsNotNone(business_ai.entitlement)
                self.assertTrue(business_ai.entitlement.is_unlimited)

                with self.assertRaises(ValueError):
                    repo.list_plan_entitlements("starter")

    def test_invalid_plan_code_is_rejected_before_sql_for_public_methods(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            sql_count = {"value": 0}

            def _count_sql(conn, cursor, statement, parameters, context, executemany):
                if statement.lstrip().upper().startswith("SELECT"):
                    sql_count["value"] += 1

            with self._session_context(Path(tmpdir) / "entitlements.db") as session:
                self._seed_features(session)
                self._seed_entitlements(session)
                event.listen(session.bind, "before_cursor_execute", _count_sql)
                repo = PlanEntitlementRepository(session)

                for method_call in (
                    lambda: repo.get_plan_entitlement(1, "starter"),
                    lambda: repo.get_entitlement_by_feature_key("ai_scan_limit", "starter"),
                    lambda: repo.list_plan_entitlements("starter"),
                ):
                    sql_count["value"] = 0
                    with self.assertRaises(ValueError):
                        method_call()
                    self.assertEqual(sql_count["value"], 0)

    @staticmethod
    @contextmanager
    def _session_context(database_path: Path):
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
        session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
        try:
            yield session
        finally:
            session.close()
            engine.dispose()

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
