from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.audit_log import AuditLogModel
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel
from database.repositories.admin_entitlement_repository import AdminEntitlementRepository
from services.admin_entitlement_service import AdminEntitlementService


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


class AdminEntitlementServiceTests(unittest.TestCase):
    def test_create_feature_creates_four_plan_rows_with_denied_defaults(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                result = service.create_feature(
                    {
                        "feature_key": "ai_scan_limit",
                        "name_uk": "Ліміт AI-сканів",
                        "category": "limits",
                        "value_type": "integer",
                        "sort_order": 7,
                    },
                    actor_user_id="admin",
                    actor_email="admin@example.com",
                )

                self.assertEqual(result["feature"]["feature_key"], "ai_scan_limit")
                self.assertEqual(len(result["matrix_row"].keys()), 5)

                feature = repo.get_feature_by_key("ai_scan_limit")
                self.assertIsNotNone(feature)
                entitlements = repo.list_entitlements_for_feature(feature.id)
                self.assertEqual(len(entitlements), 4)
                self.assertEqual(
                    [item.plan_code for item in entitlements],
                    ["trial", "free", "pro", "business"],
                )
                for entitlement in entitlements:
                    self.assertIsNone(entitlement.bool_value)
                    self.assertIsNone(entitlement.integer_value)
                    self.assertIsNone(entitlement.decimal_value)
                    self.assertIsNone(entitlement.text_value)
                    self.assertFalse(entitlement.is_unlimited)
                    self.assertFalse(entitlement.is_not_applicable)

                audit_rows = session.query(AuditLogModel).all()
                self.assertEqual(len(audit_rows), 1)
                self.assertEqual(audit_rows[0].action, "entitlement.feature.created")

    def test_duplicate_feature_key_is_rejected_and_does_not_create_rows(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                payload = {
                    "feature_key": "ai_scan_limit",
                    "name_uk": "Ліміт AI-сканів",
                    "category": "limits",
                    "value_type": "integer",
                }
                service.create_feature(payload, actor_user_id="admin", actor_email="admin@example.com")

                with self.assertRaises(ValueError):
                    service.create_feature(payload, actor_user_id="admin", actor_email="admin@example.com")

                self.assertEqual(session.query(EntitlementFeatureModel).count(), 1)
                self.assertEqual(session.query(PlanEntitlementModel).count(), 4)

    def test_invalid_value_type_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (_session, service, _repo):
                with self.assertRaises(ValueError):
                    service.create_feature(
                        {
                            "feature_key": "bad_feature",
                            "name_uk": "Погана фіча",
                            "category": "limits",
                            "value_type": "money",
                        },
                        actor_user_id="admin",
                        actor_email="admin@example.com",
                    )

    def test_list_features_is_sorted_and_honors_active_only(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, _repo):
                self._seed_feature(
                    session,
                    feature_key="zeta_feature",
                    name_uk="Zeta",
                    category="zeta",
                    value_type="boolean",
                )
                self._seed_feature(
                    session,
                    feature_key="alpha_feature",
                    name_uk="Alpha",
                    category="alpha",
                    value_type="boolean",
                    sort_order=2,
                )
                inactive_feature = self._seed_feature(
                    session,
                    feature_key="alpha_hidden",
                    name_uk="Hidden",
                    category="alpha",
                    value_type="boolean",
                    sort_order=3,
                )
                inactive_feature.is_active = False
                session.commit()

                active_features = service.list_features(active_only=True)
                self.assertEqual(
                    [item["feature_key"] for item in active_features],
                    ["alpha_feature", "zeta_feature"],
                )

                all_features = service.list_features(active_only=False)
                self.assertEqual(
                    [item["feature_key"] for item in all_features],
                    ["alpha_feature", "alpha_hidden", "zeta_feature"],
                )

    def test_update_feature_changes_allowed_fields_and_rejects_feature_key(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                feature = self._seed_feature(
                    session,
                    feature_key="support_level",
                    name_uk="Рівень підтримки",
                    category="support",
                    value_type="text",
                    sort_order=1,
                )

                result = service.update_feature(
                    feature.id,
                    {
                        "name_uk": "Новий рівень підтримки",
                        "description_uk": "Оновлений опис",
                        "category": "support_plus",
                        "sort_order": 9,
                        "is_active": False,
                    },
                    actor_user_id="admin",
                    actor_email="admin@example.com",
                )

                self.assertEqual(result["feature"]["name_uk"], "Новий рівень підтримки")
                self.assertEqual(result["feature"]["category"], "support_plus")
                self.assertEqual(result["feature"]["sort_order"], 9)
                self.assertFalse(result["feature"]["is_active"])
                self.assertEqual(repo.get_feature_by_key("support_level").name_uk, "Новий рівень підтримки")

                with self.assertRaises(ValueError):
                    service.update_feature(
                        feature.id,
                        {"feature_key": "new_key"},
                        actor_user_id="admin",
                        actor_email="admin@example.com",
                    )

    def test_value_type_change_clears_old_typed_values_and_flags(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                feature = self._seed_feature(
                    session,
                    feature_key="theme_mode",
                    name_uk="Режим теми",
                    category="support",
                    value_type="text",
                )
                for entitlement in repo.list_entitlements_for_feature(feature.id):
                    entitlement.text_value = "dark"
                    entitlement.is_unlimited = True
                    entitlement.is_not_applicable = False
                session.commit()

                service.update_feature(
                    feature.id,
                    {
                        "value_type": "boolean",
                    },
                    actor_user_id="admin",
                    actor_email="admin@example.com",
                )

                refreshed = repo.list_entitlements_for_feature(feature.id)
                for entitlement in refreshed:
                    self.assertIsNone(entitlement.text_value)
                    self.assertFalse(entitlement.is_unlimited)
                    self.assertFalse(entitlement.is_not_applicable)

    def test_get_matrix_returns_all_plan_codes_and_does_not_create_missing_rows(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                feature = self._seed_feature(
                    session,
                    feature_key="ai_scan_limit",
                    name_uk="Ліміт AI-сканів",
                    category="limits",
                    value_type="integer",
                )
                missing_row = repo.get_entitlement(feature.id, "business")
                session.delete(missing_row)
                session.commit()
                before_count = session.query(PlanEntitlementModel).count()

                result = service.get_matrix()
                matrix_row = next(row for row in result["matrix"] if row["feature"]["feature_key"] == "ai_scan_limit")
                self.assertEqual(set(matrix_row.keys()), {"feature", "trial", "free", "pro", "business"})
                self.assertIsNone(matrix_row["business"]["id"])
                self.assertEqual(session.query(PlanEntitlementModel).count(), before_count)

    def test_update_matrix_updates_valid_values(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                features = self._seed_matrix_feature_set(session)
                result = service.update_matrix(
                    [
                        {
                            "feature_id": features["boolean"].id,
                            "plan_code": "trial",
                            "bool_value": True,
                        },
                        {
                            "feature_id": features["integer"].id,
                            "plan_code": "pro",
                            "integer_value": 25,
                        },
                        {
                            "feature_id": features["decimal"].id,
                            "plan_code": "pro",
                            "decimal_value": Decimal("2.75"),
                        },
                        {
                            "feature_id": features["text"].id,
                            "plan_code": "free",
                            "text_value": "priority",
                        },
                        {
                            "feature_id": features["enum"].id,
                            "plan_code": "business",
                            "text_value": "system",
                        },
                    ],
                    actor_user_id="admin",
                    actor_email="admin@example.com",
                )

                self.assertEqual(result["updated_count"], 5)
                boolean_row = repo.get_entitlement(features["boolean"].id, "trial")
                self.assertTrue(boolean_row.bool_value)
                integer_row = repo.get_entitlement(features["integer"].id, "pro")
                self.assertEqual(integer_row.integer_value, 25)
                decimal_row = repo.get_entitlement(features["decimal"].id, "pro")
                self.assertEqual(decimal_row.decimal_value, Decimal("2.75"))
                text_row = repo.get_entitlement(features["text"].id, "free")
                self.assertEqual(text_row.text_value, "priority")
                enum_row = repo.get_entitlement(features["enum"].id, "business")
                self.assertEqual(enum_row.text_value, "system")

    def test_update_matrix_rejects_unknown_feature_id(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (_session, service, _repo):
                with self.assertRaises(ValueError):
                    service.update_matrix(
                        [
                            {
                                "feature_id": 9999,
                                "plan_code": "trial",
                                "bool_value": True,
                            }
                        ],
                        actor_user_id="admin",
                        actor_email="admin@example.com",
                    )

    def test_update_matrix_rejects_invalid_plan_code(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, _repo):
                feature = self._seed_feature(
                    session,
                    feature_key="ai_scan_limit",
                    name_uk="Ліміт AI-сканів",
                    category="limits",
                    value_type="integer",
                )
                with self.assertRaises(ValueError):
                    service.update_matrix(
                        [
                            {
                                "feature_id": feature.id,
                                "plan_code": "starter",
                                "integer_value": 5,
                            }
                        ],
                        actor_user_id="admin",
                        actor_email="admin@example.com",
                    )

    def test_update_matrix_rejects_duplicate_feature_and_plan(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, _repo):
                feature = self._seed_feature(
                    session,
                    feature_key="ai_scan_limit",
                    name_uk="Ліміт AI-сканів",
                    category="limits",
                    value_type="integer",
                )
                with self.assertRaises(ValueError):
                    service.update_matrix(
                        [
                            {"feature_id": feature.id, "plan_code": "trial", "integer_value": 10},
                            {"feature_id": feature.id, "plan_code": "trial", "integer_value": 11},
                        ],
                        actor_user_id="admin",
                        actor_email="admin@example.com",
                    )

    def test_update_matrix_rejects_wrong_typed_field(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, _repo):
                feature = self._seed_feature(
                    session,
                    feature_key="beta_toggle",
                    name_uk="Бета-перемикач",
                    category="admin",
                    value_type="boolean",
                )
                with self.assertRaises(ValueError):
                    service.update_matrix(
                        [
                            {
                                "feature_id": feature.id,
                                "plan_code": "trial",
                                "integer_value": 1,
                            }
                        ],
                        actor_user_id="admin",
                        actor_email="admin@example.com",
                    )

    def test_update_matrix_rejects_invalid_unlimited_combination(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, _repo):
                feature = self._seed_feature(
                    session,
                    feature_key="ai_scan_limit",
                    name_uk="Ліміт AI-сканів",
                    category="limits",
                    value_type="integer",
                )
                with self.assertRaises(ValueError):
                    service.update_matrix(
                        [
                            {
                                "feature_id": feature.id,
                                "plan_code": "trial",
                                "integer_value": 10,
                                "is_unlimited": True,
                                "is_not_applicable": True,
                            }
                        ],
                        actor_user_id="admin",
                        actor_email="admin@example.com",
                    )

    def test_update_matrix_is_atomic_on_error(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, _repo):
                feature = self._seed_feature(
                    session,
                    feature_key="ai_scan_limit",
                    name_uk="Ліміт AI-сканів",
                    category="limits",
                    value_type="integer",
                )

                before = service.get_matrix()["matrix"]
                with self.assertRaises(ValueError):
                    service.update_matrix(
                        [
                            {
                                "feature_id": feature.id,
                                "plan_code": "trial",
                                "integer_value": 10,
                            },
                            {
                                "feature_id": 9999,
                                "plan_code": "free",
                                "integer_value": 12,
                            },
                        ],
                        actor_user_id="admin",
                        actor_email="admin@example.com",
                    )

                after = service.get_matrix()["matrix"]
                self.assertEqual(before, after)

    def test_audit_failure_rolls_back_feature_and_matrix_changes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, service, repo):
                with patch.object(service, "_record_audit_log", side_effect=RuntimeError("audit failure")):
                    with self.assertRaises(RuntimeError):
                        service.create_feature(
                            {
                                "feature_key": "scan_limit",
                                "name_uk": "Ліміт",
                                "category": "limits",
                                "value_type": "integer",
                            },
                            actor_user_id="admin",
                            actor_email="admin@example.com",
                        )

                self.assertEqual(session.query(EntitlementFeatureModel).count(), 0)
                self.assertEqual(session.query(PlanEntitlementModel).count(), 0)
                self.assertEqual(session.query(AuditLogModel).count(), 0)

                feature = self._seed_feature(
                    session,
                    feature_key="ai_scan_limit",
                    name_uk="Ліміт AI-сканів",
                    category="limits",
                    value_type="integer",
                )
                with patch.object(service, "_record_audit_log", side_effect=RuntimeError("audit failure")):
                    with self.assertRaises(RuntimeError):
                        service.update_matrix(
                            [
                                {
                                    "feature_id": feature.id,
                                    "plan_code": "trial",
                                    "integer_value": 10,
                                }
                            ],
                            actor_user_id="admin",
                            actor_email="admin@example.com",
                        )

                self.assertIsNone(repo.get_entitlement(feature.id, "trial").integer_value)
                self.assertEqual(session.query(AuditLogModel).count(), 0)

    def test_repository_does_not_commit_itself(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, _service, repo):
                feature = EntitlementFeatureModel(
                    feature_key="repo_feature",
                    name_uk="Repo feature",
                    category="limits",
                    value_type="boolean",
                )
                with patch.object(session, "commit", side_effect=AssertionError("commit")):
                    repo.add_feature(feature)
                    session.flush()
                    repo.add_entitlements(
                        [
                            PlanEntitlementModel(
                                feature_id=feature.id,
                                plan_code="trial",
                            )
                        ]
                    )
                    repo.get_feature_by_key("repo_feature")
                    repo.list_features()

    def test_injected_session_does_not_create_private_session(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._service_context(Path(tmpdir) / "entitlements.db") as (session, _service, _repo):
                with patch(
                    "services.admin_entitlement_service.SessionLocal",
                    side_effect=AssertionError("SessionLocal should not be used when a session is injected"),
                ):
                    injected_service = AdminEntitlementService(session=session)

                self.assertIs(injected_service.session, session)
                self.assertIs(injected_service.repository.session, session)
                injected_service.close()

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
        service = AdminEntitlementService(session=session, repository=repo)
        try:
            yield session, service, repo
        finally:
            session.close()
            engine.dispose()

    @staticmethod
    def _seed_feature(
        session,
        *,
        feature_key: str,
        name_uk: str,
        category: str,
        value_type: str,
        sort_order: int = 0,
        enum_options_json: list[str] | None = None,
    ) -> EntitlementFeatureModel:
        feature = EntitlementFeatureModel(
            feature_key=feature_key,
            name_uk=name_uk,
            category=category,
            value_type=value_type,
            enum_options_json=enum_options_json,
            sort_order=sort_order,
        )
        session.add(feature)
        session.flush()
        for plan_code in ("trial", "free", "pro", "business"):
            session.add(
                PlanEntitlementModel(
                    feature_id=feature.id,
                    plan_code=plan_code,
                )
            )
        session.commit()
        return feature

    @classmethod
    def _seed_matrix_feature_set(cls, session):
        return {
            "boolean": cls._seed_feature(
                session,
                feature_key="beta_toggle",
                name_uk="Бета-перемикач",
                category="admin",
                value_type="boolean",
            ),
            "integer": cls._seed_feature(
                session,
                feature_key="ai_scan_limit",
                name_uk="Ліміт AI-сканів",
                category="limits",
                value_type="integer",
            ),
            "decimal": cls._seed_feature(
                session,
                feature_key="storage_limit",
                name_uk="Ліміт сховища",
                category="limits",
                value_type="decimal",
            ),
            "text": cls._seed_feature(
                session,
                feature_key="support_level",
                name_uk="Рівень підтримки",
                category="support",
                value_type="text",
            ),
            "enum": cls._seed_feature(
                session,
                feature_key="theme_mode",
                name_uk="Режим теми",
                category="support",
                value_type="enum",
                enum_options_json=["light", "dark", "system"],
            ),
        }


if __name__ == "__main__":
    unittest.main()
