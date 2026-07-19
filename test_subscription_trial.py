from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.routes.auth import _serialize_user
from database.base import Base
from database.models.user import UserModel
from database.repositories import user_repository
from services.subscription_service import (
    build_subscription_status,
    build_trial_window,
    has_required_role_access,
    is_trial_active,
    trial_seconds_remaining,
)


class SubscriptionTrialTests(unittest.TestCase):
    def test_create_user_grants_seven_day_trial_to_free_users(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "trial.db"
            session_factory = self._create_temp_session(database_path)

            with patch.object(user_repository, "SessionLocal", session_factory):
                user = user_repository.create_user(
                    email="new@example.com",
                    password_hash="hash",
                    role="free",
                )

            self.assertIsNotNone(user)
            assert user is not None
            self.assertIsNotNone(user.trial_started_at)
            self.assertIsNotNone(user.trial_ends_at)
            self.assertTrue(user.trial_started_at < user.trial_ends_at)
            self.assertEqual(
                user.trial_ends_at - user.trial_started_at,
                timedelta(days=7),
            )

    def test_create_user_does_not_grant_trial_to_admin(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "trial.db"
            session_factory = self._create_temp_session(database_path)

            with patch.object(user_repository, "SessionLocal", session_factory):
                user = user_repository.create_user(
                    email="admin@example.com",
                    password_hash="hash",
                    role="admin",
                )

            self.assertIsNotNone(user)
            assert user is not None
            self.assertIsNone(user.trial_started_at)
            self.assertIsNone(user.trial_ends_at)

    def test_subscription_status_reports_trial_fields(self) -> None:
        started_at, ends_at = build_trial_window(now=datetime(2026, 7, 1, 12, 0, 0))
        user = SimpleNamespace(
            role="free",
            trial_started_at=started_at,
            trial_ends_at=ends_at,
        )

        status = build_subscription_status(user, now=datetime(2026, 7, 3, 12, 0, 0))

        self.assertEqual(status["effective_plan"], "trial")
        self.assertTrue(status["is_trial_active"])
        self.assertEqual(status["trial_started_at"], started_at)
        self.assertEqual(status["trial_ends_at"], ends_at)
        self.assertGreater(status["trial_seconds_remaining"], 0)
        self.assertEqual(trial_seconds_remaining(user, now=datetime(2026, 7, 3, 12, 0, 0)), status["trial_seconds_remaining"])

    def test_serialize_user_includes_subscription_state(self) -> None:
        now = datetime.utcnow()
        started_at, ends_at = build_trial_window(now=now - timedelta(days=1))
        user = SimpleNamespace(
            id="user-id",
            email="user@example.com",
            username="user",
            phone=None,
            city="Kyiv",
            telegram_id=None,
            role="free",
            last_username_change_at=None,
            trial_started_at=started_at,
            trial_ends_at=ends_at,
            viyar_email=None,
            viyar_password_secret=None,
            viyar_cookie=None,
            viyar_last_auth_at=None,
            viyar_last_auth_status=None,
            viyar_last_auth_error=None,
            is_active=True,
        )

        payload = _serialize_user(user)

        self.assertEqual(payload["effective_plan"], "trial")
        self.assertTrue(payload["is_trial_active"])
        self.assertEqual(payload["trial_started_at"], started_at)
        self.assertEqual(payload["trial_ends_at"], ends_at)
        self.assertGreater(payload["trial_seconds_remaining"], 0)

    def test_trial_access_is_allowed_for_paid_routes_but_not_admin_only(self) -> None:
        started_at, ends_at = build_trial_window(now=datetime(2026, 7, 1, 12, 0, 0))
        user = SimpleNamespace(
            role="free",
            trial_started_at=started_at,
            trial_ends_at=ends_at,
        )

        check_time = datetime(2026, 7, 3, 12, 0, 0)

        self.assertTrue(has_required_role_access(user, ["premium", "pro"], now=check_time))
        self.assertTrue(has_required_role_access(user, ["admin", "premium", "pro"], now=check_time))
        self.assertFalse(has_required_role_access(user, ["admin"], now=check_time))
        self.assertTrue(is_trial_active(user, now=datetime(2026, 7, 2, 12, 0, 0)))
        self.assertFalse(is_trial_active(user, now=datetime(2026, 7, 10, 12, 0, 0)))

    @staticmethod
    def _create_temp_session(database_path: Path):
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine, tables=[UserModel.__table__])
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)


if __name__ == "__main__":
    unittest.main()
