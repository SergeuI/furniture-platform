from __future__ import annotations

import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from api.routes import auth
from schemas.auth import RegisterUserSchema
from services.user_roles import ROLE_USER


class DummyQuery:
    def filter(self, *args, **kwargs):
        return self

    def count(self) -> int:
        return 0


class DummyDatabase:
    def query(self, _model):
        return DummyQuery()

    def close(self) -> None:
        return None


class PublicRegistrationToggleTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_overview_reflects_local_toggle(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch.object(auth, "SessionLocal", lambda: DummyDatabase()), patch.object(
            auth,
            "count_users",
            return_value=0,
        ), patch.object(
            auth,
            "count_projects",
            return_value=0,
        ):
            disabled_payload = await auth.public_overview_route()

        with patch.dict(
            os.environ,
            {auth.LOCAL_PUBLIC_REGISTRATION_ENV: "1"},
            clear=True,
        ), patch.object(auth, "SessionLocal", lambda: DummyDatabase()), patch.object(
            auth,
            "count_users",
            return_value=0,
        ), patch.object(
            auth,
            "count_projects",
            return_value=0,
        ):
            enabled_payload = await auth.public_overview_route()

        self.assertFalse(disabled_payload["registration_enabled"])
        self.assertTrue(enabled_payload["registration_enabled"])

    async def test_register_route_requires_local_toggle(self) -> None:
        payload = RegisterUserSchema(
            email="trial@example.com",
            password="Password123",
        )

        with patch.dict(os.environ, {}, clear=True):
            response = await auth.register_route(payload)

        self.assertFalse(response["success"])
        self.assertEqual(response["error"], "Public registration is disabled")

    async def test_register_route_forces_free_role_when_enabled(self) -> None:
        payload = RegisterUserSchema(
            email="trial@example.com",
            password="Password123",
        )
        fake_user = SimpleNamespace(
            id="user-id",
            email="trial@example.com",
            username="trial",
            phone=None,
            city=None,
            telegram_id=None,
            role="free",
            last_username_change_at=None,
            trial_started_at=datetime(2026, 7, 19, 10, 0, 0),
            trial_ends_at=datetime(2026, 7, 26, 10, 0, 0),
            viyar_email=None,
            viyar_password_secret=None,
            viyar_cookie=None,
            viyar_last_auth_at=None,
            viyar_last_auth_status=None,
            viyar_last_auth_error=None,
            is_active=True,
        )

        with patch.dict(
            os.environ,
            {auth.LOCAL_PUBLIC_REGISTRATION_ENV: "true"},
            clear=True,
        ), patch.object(auth, "register_user", return_value=fake_user) as register_mock, patch.object(
            auth,
            "create_access_token",
            return_value="token",
        ), patch.object(
            auth,
            "_serialize_user",
            return_value={"id": "user-id", "role": "free"},
        ):
            response = await auth.register_route(payload)

        self.assertTrue(response["success"])
        self.assertEqual(response["access_token"], "token")
        register_mock.assert_called_once()
        self.assertEqual(register_mock.call_args.kwargs["role"], ROLE_USER)


if __name__ == "__main__":
    unittest.main()
