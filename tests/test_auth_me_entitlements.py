from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from api.dependencies import auth as auth_dependencies
from api.routes import auth as auth_route
from database.base import Base
from database.models.audit_log import AuditLogModel
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel
from services import entitlement_service
from services.entitlement_registry import get_system_entitlement_registry_keys
from services.entitlement_registry_sync_service import EntitlementRegistrySyncService


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@dataclass
class UserStub:
    id: str
    email: str
    role: str
    username: str | None = None
    phone: str | None = None
    city: str | None = None
    telegram_id: str | None = None
    trial_started_at: datetime | None = None
    trial_ends_at: datetime | None = None
    is_active: bool = True
    last_username_change_at: datetime | None = None
    viyar_email: str | None = None
    viyar_password_secret: str | None = None
    viyar_cookie: str | None = None
    viyar_last_auth_at: datetime | None = None
    viyar_last_auth_status: str | None = None
    viyar_last_auth_error: str | None = None


class AuthMeEntitlementsTests(unittest.TestCase):
    def test_me_returns_entitlements_for_current_user(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as (client, _session_factory):
                response = client.get("/auth/me", headers=self._auth_headers("free-token"))

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["success"])
            self.assertEqual(set(payload["user"]["entitlements"]), set(get_system_entitlement_registry_keys()))
            self.assertTrue({"mounting_nodes.view", "mounting_nodes.create", "mounting_nodes.edit", "mounting_nodes.delete"}.issubset(payload["user"]["entitlements"]))
            self.assertEqual(
                payload["user"]["entitlements"]["materials.view"],
                {
                    "allowed": True,
                    "value_type": "boolean",
                    "value": True,
                    "is_unlimited": False,
                    "is_not_applicable": False,
                },
            )
            self.assertEqual(
                payload["user"]["entitlements"]["materials.max_owned"],
                {
                    "allowed": True,
                    "value_type": "integer",
                    "value": 3,
                    "is_unlimited": False,
                    "is_not_applicable": False,
                },
            )
            self.assertEqual(payload["user"]["effective_plan"], "free")

    def test_me_keeps_admin_bypass_in_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "entitlements.db") as (client, _session_factory):
                response = client.get("/auth/me", headers=self._auth_headers("admin-token"))

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["success"])
            self.assertEqual(payload["user"]["effective_plan"], "admin")
            self.assertEqual(
                payload["user"]["entitlements"]["materials.max_owned"],
                {
                    "allowed": True,
                    "value_type": "integer",
                    "value": None,
                    "is_unlimited": True,
                    "is_not_applicable": False,
                },
            )
            self.assertEqual(
                payload["user"]["entitlements"]["materials.view"],
                {
                    "allowed": True,
                    "value_type": "boolean",
                    "value": True,
                    "is_unlimited": False,
                    "is_not_applicable": False,
                },
            )

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
        session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        with session_factory() as session:
            service = EntitlementRegistrySyncService(session=session)
            service.apply_sync(actor_user_id="admin", actor_email="admin@example.com")
            feature_ids = {
                row.feature_key: row.id
                for row in session.query(EntitlementFeatureModel).all()
            }
            for feature_key in ("materials.view", "materials.create", "materials.edit", "materials.delete"):
                for plan_code in ("trial", "free", "pro", "business"):
                    entitlement = session.query(PlanEntitlementModel).filter(
                        PlanEntitlementModel.feature_id == feature_ids[feature_key],
                        PlanEntitlementModel.plan_code == plan_code,
                    ).one()
                    entitlement.bool_value = True
            session.query(PlanEntitlementModel).filter(
                PlanEntitlementModel.feature_id == feature_ids["materials.max_owned"],
                PlanEntitlementModel.plan_code == "free",
            ).one().integer_value = 3
            for plan_code in ("trial", "pro", "business"):
                entitlement = session.query(PlanEntitlementModel).filter(
                    PlanEntitlementModel.feature_id == feature_ids["materials.max_owned"],
                    PlanEntitlementModel.plan_code == plan_code,
                ).one()
                entitlement.is_unlimited = True
                entitlement.integer_value = None
            session.commit()

        app = FastAPI()
        app.include_router(auth_route.router, prefix="/auth")

        trial_user = UserStub(
            id="trial-user",
            email="trial@example.com",
            role="trial",
            trial_started_at=datetime.utcnow() - timedelta(hours=1),
            trial_ends_at=datetime.utcnow() + timedelta(days=6),
        )
        free_user = UserStub(
            id="free-user",
            email="free@example.com",
            role="free",
        )
        admin_user = UserStub(
            id="admin-user",
            email="admin@example.com",
            role="admin",
        )
        token_map = {
            "free-token": free_user,
            "trial-token": trial_user,
            "admin-token": admin_user,
        }

        def _resolve_user(token: str):
            return token_map.get(token, trial_user)

        with (
            patch.object(auth_dependencies, "get_user_from_token", side_effect=_resolve_user),
            patch.object(entitlement_service, "SessionLocal", side_effect=session_factory),
        ):
            with TestClient(app) as client:
                yield client, session_factory

    @staticmethod
    def _auth_headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
        }


if __name__ == "__main__":
    unittest.main()
