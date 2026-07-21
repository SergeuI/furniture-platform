from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api.dependencies import auth as auth_dependencies
from api.routes import admin_entitlements
from database.base import Base
from database.models.audit_log import AuditLogModel
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel
from services.admin_entitlement_service import AdminEntitlementService


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@dataclass
class UserStub:
    id: str = "admin-1"
    email: str = "admin@example.com"
    role: str = "admin"


class AdminEntitlementsApiTests(unittest.TestCase):
    def test_unauthorized_user_gets_401(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as client:
                response = client.get("/admin/entitlements/features")
                self.assertEqual(response.status_code, 401)

    def test_non_admin_gets_403(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as client:
                with patch.object(auth_dependencies, "get_user_from_token", return_value=UserStub(role="free")):
                    response = client.get(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                    )
                self.assertEqual(response.status_code, 403)

    def test_admin_get_features_returns_200(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as client:
                with self._admin_auth():
                    response = client.get(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["features"], [])

    def test_admin_post_feature_returns_201(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as client:
                with self._admin_auth():
                    response = client.post(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                        json={
                            "feature_key": "ai_scan_limit",
                            "name_uk": "Ліміт AI-сканів",
                            "category": "limits",
                            "value_type": "integer",
                            "sort_order": 3,
                        },
                    )
                self.assertEqual(response.status_code, 201)
                body = response.json()
                self.assertTrue(body["success"])
                self.assertEqual(body["feature"]["feature_key"], "ai_scan_limit")

    def test_duplicate_feature_key_returns_conflict_without_sql_or_traceback(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as client:
                with self._admin_auth():
                    client.post(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                        json={
                            "feature_key": "ai_scan_limit",
                            "name_uk": "Ліміт AI-сканів",
                            "category": "limits",
                            "value_type": "integer",
                        },
                    )
                    response = client.post(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                        json={
                            "feature_key": "ai_scan_limit",
                            "name_uk": "Ліміт AI-сканів 2",
                            "category": "limits",
                            "value_type": "integer",
                        },
                    )
                self.assertEqual(response.status_code, 409)
                self.assertNotIn("Traceback", response.text)
                self.assertNotIn("sqlite", response.text.lower())

    def test_admin_patch_feature_returns_200(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as client:
                with self._admin_auth():
                    create_response = client.post(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                        json={
                            "feature_key": "support_level",
                            "name_uk": "Рівень підтримки",
                            "category": "support",
                            "value_type": "text",
                        },
                    )
                    feature_id = create_response.json()["feature"]["id"]
                    response = client.patch(
                        f"/admin/entitlements/features/{feature_id}",
                        headers=self._auth_headers(),
                        json={
                            "name_uk": "Новий рівень підтримки",
                            "sort_order": 11,
                        },
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["feature"]["name_uk"], "Новий рівень підтримки")

    def test_admin_get_matrix_returns_200(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as client:
                with self._admin_auth():
                    client.post(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                        json={
                            "feature_key": "ai_scan_limit",
                            "name_uk": "Ліміт AI-сканів",
                            "category": "limits",
                            "value_type": "integer",
                        },
                    )
                    response = client.get(
                        "/admin/entitlements/matrix",
                        headers=self._auth_headers(),
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json()["matrix"]), 1)

    def test_admin_put_matrix_returns_200(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as client:
                with self._admin_auth():
                    create_response = client.post(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                        json={
                            "feature_key": "ai_scan_limit",
                            "name_uk": "Ліміт AI-сканів",
                            "category": "limits",
                            "value_type": "integer",
                        },
                    )
                    feature_id = create_response.json()["feature"]["id"]
                    response = client.put(
                        "/admin/entitlements/matrix",
                        headers=self._auth_headers(),
                        json={
                            "rows": [
                                {
                                    "feature_id": feature_id,
                                    "plan_code": "trial",
                                    "integer_value": 10,
                                }
                            ]
                        },
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["updated_count"], 1)

    def test_invalid_payload_returns_422(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as client:
                with self._admin_auth():
                    response = client.post(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                        json={
                            "feature_key": "Bad Key",
                            "name_uk": "Невалідна фіча",
                            "category": "limits",
                            "value_type": "integer",
                        },
                )
                self.assertEqual(response.status_code, 422)

    def test_admin_dependency_closes_session_after_success(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._dependency_client_context(Path(tmpdir) / "entitlements.db") as (
                client,
                session,
                session_factory_mock,
                close_mock,
            ):
                with self._admin_auth():
                    response = client.post(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                        json={
                            "feature_key": "ai_scan_limit",
                            "name_uk": "Ліміт AI-сканів",
                            "category": "limits",
                            "value_type": "integer",
                        },
                    )

                self.assertEqual(response.status_code, 201)
                session_factory_mock.assert_called_once()
                close_mock.assert_called_once()
                self.assertEqual(session.query(EntitlementFeatureModel).count(), 1)
                self.assertEqual(session.query(PlanEntitlementModel).count(), 4)

    def test_admin_dependency_closes_session_after_service_error(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._dependency_client_context(Path(tmpdir) / "entitlements.db") as (
                client,
                session,
                session_factory_mock,
                close_mock,
            ):
                with patch.object(AdminEntitlementService, "_record_audit_log", side_effect=RuntimeError("audit failure")):
                    with self._admin_auth():
                        response = client.post(
                            "/admin/entitlements/features",
                            headers=self._auth_headers(),
                            json={
                                "feature_key": "ai_scan_limit",
                                "name_uk": "Ліміт AI-сканів",
                                "category": "limits",
                                "value_type": "integer",
                            },
                        )

                self.assertEqual(response.status_code, 500)
                session_factory_mock.assert_called_once()
                close_mock.assert_called_once()
                self.assertEqual(session.query(EntitlementFeatureModel).count(), 0)
                self.assertEqual(session.query(PlanEntitlementModel).count(), 0)
                self.assertEqual(session.query(AuditLogModel).count(), 0)

    def test_error_in_one_cell_does_not_save_other_cells(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as client:
                with self._admin_auth():
                    create_response = client.post(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                        json={
                            "feature_key": "ai_scan_limit",
                            "name_uk": "Ліміт AI-сканів",
                            "category": "limits",
                            "value_type": "integer",
                        },
                    )
                    feature_id = create_response.json()["feature"]["id"]
                    before = client.get(
                        "/admin/entitlements/matrix",
                        headers=self._auth_headers(),
                    ).json()
                    response = client.put(
                        "/admin/entitlements/matrix",
                        headers=self._auth_headers(),
                        json={
                            "rows": [
                                {
                                    "feature_id": feature_id,
                                    "plan_code": "trial",
                                    "integer_value": 10,
                                },
                                {
                                    "feature_id": 9999,
                                    "plan_code": "free",
                                    "integer_value": 12,
                                },
                            ]
                        },
                    )
                    after = client.get(
                        "/admin/entitlements/matrix",
                        headers=self._auth_headers(),
                    ).json()
                self.assertEqual(response.status_code, 404)
                self.assertEqual(before, after)

    def test_responses_do_not_expose_sql_or_traceback(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as client:
                with self._admin_auth():
                    client.post(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                        json={
                            "feature_key": "ai_scan_limit",
                            "name_uk": "Ліміт AI-сканів",
                            "category": "limits",
                            "value_type": "integer",
                        },
                    )
                    response = client.post(
                        "/admin/entitlements/features",
                        headers=self._auth_headers(),
                        json={
                            "feature_key": "ai_scan_limit",
                            "name_uk": "Дубль",
                            "category": "limits",
                            "value_type": "integer",
                        },
                    )
                self.assertNotIn("Traceback", response.text)
                self.assertNotIn("sqlite", response.text.lower())

    @staticmethod
    def _auth_headers() -> dict[str, str]:
        return {"Authorization": "Bearer test-token"}

    @contextmanager
    def _admin_auth(self):
        with patch.object(auth_dependencies, "get_user_from_token", return_value=UserStub()):
            yield

    @contextmanager
    def _client_context(self, database_path: Path):
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
        service = AdminEntitlementService(session=session)
        app = FastAPI()
        app.include_router(admin_entitlements.router, prefix="/admin/entitlements")
        app.dependency_overrides[admin_entitlements.get_admin_entitlement_service] = lambda: service
        client = TestClient(app)
        try:
            yield client
        finally:
            client.close()
            session.close()
            engine.dispose()

    @contextmanager
    def _dependency_client_context(self, database_path: Path):
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
        app = FastAPI()
        app.include_router(admin_entitlements.router, prefix="/admin/entitlements")
        client = TestClient(app, raise_server_exceptions=False)
        try:
            with patch.object(admin_entitlements, "SessionLocal", return_value=session) as session_factory_mock:
                with patch.object(session, "close", wraps=session.close) as close_mock:
                    yield client, session, session_factory_mock, close_mock
        finally:
            client.close()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
