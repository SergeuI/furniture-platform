from __future__ import annotations

import os
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.routes import auth
from database.base import Base
from database.models.registration_identity import (
    RegistrationChallengeModel,
    RegistrationIdentityModel,
)
from database.models.user import UserModel
from database.repositories import user_repository
from schemas.auth import (
    LoginUserSchema,
    RegistrationConfirmRequestSchema,
    RegistrationStartRequestSchema,
)
from services.auth_service import hash_password
from services import registration_onboarding_service as onboarding
from services.registration_identity_service import CHALLENGE_CONSUMED, CHALLENGE_PENDING


class RegistrationOnboardingFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_creates_pending_user_without_trial(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {},
                clear=True,
            ):
                response = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="New User",
                        email="new@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                ))

            self.assertTrue(response["success"])
            self.assertEqual(response["registration_status"], onboarding.REGISTRATION_STATUS_PENDING_PHONE)
            self.assertFalse(response["phone_verified"])
            self.assertFalse(response["trial_granted"])
            self.assertEqual(response["effective_plan"], "free")
            self.assertIsNone(response.get("debug_verification_token"))

            db = session_factory()
            try:
                user = db.query(UserModel).filter(UserModel.email == "new@example.com").first()
                challenge = db.query(RegistrationChallengeModel).first()
            finally:
                db.close()

            self.assertIsNotNone(user)
            assert user is not None
            self.assertEqual(user.registration_status, onboarding.REGISTRATION_STATUS_PENDING_PHONE)
            self.assertIsNone(user.trial_started_at)
            self.assertIsNone(user.trial_ends_at)
            self.assertEqual(user.phone, "+380501234567")
            self.assertIsNotNone(challenge)
            assert challenge is not None
            self.assertEqual(challenge.status, CHALLENGE_PENDING)

    async def test_pending_user_cannot_login_and_old_user_can_login(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.object(
                auth,
                "create_access_token",
                return_value="token",
            ), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        username="Pending User",
                        email="pending@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                )

            with mock.patch(
                "database.repositories.user_repository.SessionLocal",
                session_factory,
            ):
                login_response = await auth.login_route(
                    LoginUserSchema(
                        email="pending@example.com",
                        password="Password123",
                    )
                )

            self.assertFalse(login_response["success"])
            self.assertEqual(
                login_response["error"],
                "Підтвердьте номер телефону, щоб завершити реєстрацію.",
            )

            db = session_factory()
            try:
                db.add(
                    UserModel(
                        email="legacy@example.com",
                        username="legacy",
                        password_hash=hash_password("Password123"),
                        role="free",
                        is_active=True,
                    )
                )
                db.commit()
            finally:
                db.close()

            with mock.patch(
                "database.repositories.user_repository.SessionLocal",
                session_factory,
            ), mock.patch.object(
                auth,
                "create_access_token",
                return_value="token",
            ):
                legacy_login_response = await auth.login_route(
                    LoginUserSchema(
                        email="legacy@example.com",
                        password="Password123",
                    )
                )

            self.assertTrue(legacy_login_response["success"])
            self.assertEqual(legacy_login_response["access_token"], "token")

    async def test_confirm_activates_user_and_grants_trial(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                start_response = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="New User",
                        email="trial@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                ))

                confirm_response = await auth.registration_confirm_route(
                    RegistrationConfirmRequestSchema(
                        token=start_response["debug_verification_token"],
                    )
                )

            self.assertTrue(confirm_response["success"])
            self.assertEqual(confirm_response["registration_status"], onboarding.REGISTRATION_STATUS_ACTIVE)
            self.assertTrue(confirm_response["phone_verified"])
            self.assertTrue(confirm_response["trial_granted"])
            self.assertEqual(confirm_response["effective_plan"], "trial")
            self.assertIsNotNone(confirm_response["trial_ends_at"])
            self.assertEqual(confirm_response["challenge_status"], CHALLENGE_CONSUMED)

            db = session_factory()
            try:
                user = db.query(UserModel).filter(UserModel.email == "trial@example.com").first()
                challenge = db.query(RegistrationChallengeModel).first()
                identity = db.query(RegistrationIdentityModel).first()
            finally:
                db.close()

            self.assertIsNotNone(user)
            assert user is not None
            self.assertEqual(user.registration_status, onboarding.REGISTRATION_STATUS_ACTIVE)
            self.assertIsNotNone(user.phone_verified_at)
            self.assertIsNotNone(user.trial_started_at)
            self.assertIsNotNone(user.trial_ends_at)
            self.assertEqual(user.trial_ends_at - user.trial_started_at, timedelta(days=7))
            self.assertIsNotNone(challenge)
            assert challenge is not None
            self.assertEqual(challenge.status, CHALLENGE_CONSUMED)
            self.assertIsNotNone(identity)
            assert identity is not None
            self.assertIsNotNone(identity.trial_used_at)

    async def test_same_phone_second_email_becomes_free_without_trial(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                first_start = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="First",
                        email="first@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                ))
                await auth.registration_confirm_route(
                    RegistrationConfirmRequestSchema(token=first_start["debug_verification_token"])
                )

                second_start = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="Second",
                        email="second@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                ))
                second_confirm = await auth.registration_confirm_route(
                    RegistrationConfirmRequestSchema(token=second_start["debug_verification_token"])
                )

            self.assertTrue(second_confirm["success"])
            self.assertFalse(second_confirm["trial_granted"])
            self.assertEqual(second_confirm["effective_plan"], "free")
            self.assertIsNone(second_confirm["trial_ends_at"])

            db = session_factory()
            try:
                users = db.query(UserModel).order_by(UserModel.email.asc()).all()
                identities = db.query(RegistrationIdentityModel).all()
            finally:
                db.close()

            self.assertEqual(len(users), 2)
            self.assertEqual(len(identities), 1)
            self.assertIsNotNone(identities[0].trial_used_at)

    async def test_duplicate_email_is_neutral_and_does_not_reveal_existing_user(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                first_response = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="Duplicate User",
                        email="duplicate@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                ))
                duplicate_response = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="Duplicate User 2",
                        email="duplicate@example.com",
                        password="Password123",
                        phone="+380501234568",
                    )
                ))

            self.assertTrue(first_response["success"])
            self.assertFalse(duplicate_response["success"])
            self.assertEqual(
                duplicate_response["error"],
                "Не вдалося розпочати реєстрацію з указаними даними.",
            )
            self.assertNotIn("user_id", duplicate_response)
            self.assertNotIn("challenge_id", duplicate_response)
            self.assertNotIn("challenge_status", duplicate_response)
            self.assertNotIn("registration_status", duplicate_response)
            self.assertNotIn("trial_granted", duplicate_response)

            db = session_factory()
            try:
                users = db.query(UserModel).filter(UserModel.email == "duplicate@example.com").all()
            finally:
                db.close()

            self.assertEqual(len(users), 1)

    async def test_debug_token_depends_on_local_test_mode(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {},
                clear=True,
            ):
                disabled_response = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="No Debug",
                        email="nodebug@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                ))

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                enabled_response = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="Debug",
                        email="debug@example.com",
                        password="Password123",
                        phone="+380501234568",
                    )
                ))

            self.assertIsNone(disabled_response.get("debug_verification_token"))
            self.assertIsNotNone(enabled_response.get("debug_verification_token"))

    async def test_confirm_rolls_back_on_failure_after_atomic_claim(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                start_response = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="Rollback",
                        email="rollback@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                ))

            session = session_factory()
            commit = session.commit
            session.commit = mock.Mock(side_effect=RuntimeError("boom"))

            try:
                with mock.patch.object(onboarding, "SessionLocal", lambda: session):
                    with self.assertRaises(RuntimeError):
                        await auth.registration_confirm_route(
                            RegistrationConfirmRequestSchema(
                                token=start_response["debug_verification_token"],
                            )
                        )
            finally:
                session.commit = commit
                session.close()

            db = session_factory()
            try:
                user = db.query(UserModel).filter(UserModel.email == "rollback@example.com").first()
                challenge = db.query(RegistrationChallengeModel).first()
                identity = db.query(RegistrationIdentityModel).first()
            finally:
                db.close()

            self.assertIsNotNone(user)
            assert user is not None
            self.assertEqual(user.registration_status, onboarding.REGISTRATION_STATUS_PENDING_PHONE)
            self.assertIsNone(user.phone_verified_at)
            self.assertIsNone(user.trial_started_at)
            self.assertIsNone(user.trial_ends_at)
            self.assertIsNotNone(challenge)
            assert challenge is not None
            self.assertEqual(challenge.status, CHALLENGE_PENDING)
            self.assertIsNone(identity.trial_used_at if identity else None)

    async def test_confirm_rejects_invalid_and_consumed_tokens(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                start_response = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="Token User",
                        email="token@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                ))
                confirm_response = await auth.registration_confirm_route(
                    RegistrationConfirmRequestSchema(
                        token=start_response["debug_verification_token"],
                    )
                )
                invalid_response = await auth.registration_confirm_route(
                    RegistrationConfirmRequestSchema(
                        token="missing-token",
                    )
                )
                consumed_response = await auth.registration_confirm_route(
                    RegistrationConfirmRequestSchema(
                        token=start_response["debug_verification_token"],
                    )
                )

            self.assertTrue(confirm_response["success"])
            self.assertFalse(invalid_response["success"])
            self.assertEqual(invalid_response["error"], "Challenge not found")
            self.assertFalse(consumed_response["success"])
            self.assertEqual(consumed_response["error"], "Challenge is consumed")

    @staticmethod
    def _response_json(response):
        if hasattr(response, "body"):
            return json.loads(response.body)
        return response

    @staticmethod
    def _create_session_factory(database_path: Path):
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(
            engine,
            tables=[
                UserModel.__table__,
                RegistrationIdentityModel.__table__,
                RegistrationChallengeModel.__table__,
            ],
        )
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)


class RegistrationOnboardingHttpTests(unittest.TestCase):
    def test_http_registration_flow_and_missing_status_endpoint(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")
            app = self._build_test_app()

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.object(
                user_repository,
                "SessionLocal",
                session_factory,
            ), mock.patch.object(
                auth,
                "create_access_token",
                return_value="token",
            ), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                with TestClient(app) as client:
                    start_response = client.post(
                        "/auth/registration/start",
                        json={
                            "name": "HTTP User",
                            "email": "http@example.com",
                            "password": "Password123",
                            "phone": "+380501234567",
                        },
                    )
                    self.assertEqual(start_response.status_code, 200)
                    start_payload = start_response.json()
                    self.assertTrue(start_payload["success"])
                    self.assertEqual(start_payload["registration_status"], onboarding.REGISTRATION_STATUS_PENDING_PHONE)
                    self.assertIn("debug_verification_token", start_payload)

                    duplicate_response = client.post(
                        "/auth/registration/start",
                        json={
                            "name": "HTTP User 2",
                            "email": "http@example.com",
                            "password": "Password123",
                            "phone": "+380501234568",
                        },
                    )
                    self.assertEqual(duplicate_response.status_code, 200)
                    duplicate_payload = duplicate_response.json()
                    self.assertFalse(duplicate_payload["success"])
                    self.assertEqual(
                        duplicate_payload["error"],
                        "Не вдалося розпочати реєстрацію з указаними даними.",
                    )
                    self.assertNotIn("user_id", duplicate_payload)
                    self.assertNotIn("challenge_id", duplicate_payload)
                    self.assertNotIn("challenge_status", duplicate_payload)
                    self.assertNotIn("registration_status", duplicate_payload)
                    self.assertNotIn("trial_granted", duplicate_payload)

                    confirm_response = client.post(
                        "/auth/registration/confirm",
                        json={
                            "token": start_payload["debug_verification_token"],
                        },
                    )
                    self.assertEqual(confirm_response.status_code, 200)
                    confirm_payload = confirm_response.json()
                    self.assertTrue(confirm_payload["success"])
                    self.assertEqual(confirm_payload["effective_plan"], "trial")
                    self.assertTrue(confirm_payload["trial_granted"])

                    login_response = client.post(
                        "/auth/login",
                        json={
                            "email": "http@example.com",
                            "password": "Password123",
                        },
                    )
                    self.assertEqual(login_response.status_code, 200)
                    login_payload = login_response.json()
                    self.assertTrue(login_payload["success"])
                    self.assertEqual(login_payload["access_token"], "token")

                    status_response = client.get(
                        f"/auth/registration/status/{start_payload['challenge_id']}"
                    )
                    self.assertEqual(status_response.status_code, 404)

    def test_http_login_blocks_pending_blocked_and_allows_active_and_legacy_users(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")
            app = self._build_test_app()

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.object(
                user_repository,
                "SessionLocal",
                session_factory,
            ), mock.patch.object(
                auth,
                "create_access_token",
                return_value="token",
            ), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                with TestClient(app) as client:
                    client.post(
                        "/auth/registration/start",
                        json={
                            "name": "Pending User",
                            "email": "pending@example.com",
                            "password": "Password123",
                            "phone": "+380501234567",
                        },
                    )

                    pending_login_response = client.post(
                        "/auth/login",
                        json={
                            "email": "pending@example.com",
                            "password": "Password123",
                        },
                    )
                    self.assertEqual(pending_login_response.status_code, 200)
                    self.assertEqual(
                        pending_login_response.json()["error"],
                        "Підтвердьте номер телефону, щоб завершити реєстрацію.",
                    )

                    wrong_password_response = client.post(
                        "/auth/login",
                        json={
                            "email": "pending@example.com",
                            "password": "WrongPassword123",
                        },
                    )
                    self.assertEqual(wrong_password_response.status_code, 200)
                    self.assertEqual(wrong_password_response.json()["error"], "Invalid email or password")

                    db = session_factory()
                    try:
                        db.add(
                            UserModel(
                                email="blocked@example.com",
                                username="blocked",
                                password_hash=hash_password("Password123"),
                                role="free",
                                registration_status=onboarding.REGISTRATION_STATUS_BLOCKED,
                                is_active=True,
                            )
                        )
                        db.add(
                            UserModel(
                                email="active@example.com",
                                username="active",
                                password_hash=hash_password("Password123"),
                                role="free",
                                registration_status=onboarding.REGISTRATION_STATUS_ACTIVE,
                                is_active=True,
                            )
                        )
                        db.add(
                            UserModel(
                                email="legacy@example.com",
                                username="legacy",
                                password_hash=hash_password("Password123"),
                                role="free",
                                registration_status=None,
                                is_active=True,
                            )
                        )
                        db.commit()
                    finally:
                        db.close()

                    blocked_login_response = client.post(
                        "/auth/login",
                        json={
                            "email": "blocked@example.com",
                            "password": "Password123",
                        },
                    )
                    self.assertEqual(blocked_login_response.status_code, 200)
                    self.assertEqual(
                        blocked_login_response.json()["error"],
                        "Обліковий запис заблоковано.",
                    )

                    active_login_response = client.post(
                        "/auth/login",
                        json={
                            "email": "active@example.com",
                            "password": "Password123",
                        },
                    )
                    self.assertEqual(active_login_response.status_code, 200)
                    self.assertTrue(active_login_response.json()["success"])

                    legacy_login_response = client.post(
                        "/auth/login",
                        json={
                            "email": "legacy@example.com",
                            "password": "Password123",
                        },
                    )
                    self.assertEqual(legacy_login_response.status_code, 200)
                    self.assertTrue(legacy_login_response.json()["success"])

    def test_expired_onboarding_challenge_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")
            app = self._build_test_app()

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                with TestClient(app) as client:
                    start_response = client.post(
                        "/auth/registration/start",
                        json={
                            "name": "Expired User",
                            "email": "expired@example.com",
                            "password": "Password123",
                            "phone": "+380501234567",
                        },
                    )
                    self.assertEqual(start_response.status_code, 200)
                    token = start_response.json()["debug_verification_token"]

                    with mock.patch.object(
                        onboarding,
                        "_utcnow",
                        return_value=datetime.utcnow() + timedelta(days=2),
                    ):
                        confirm_response = client.post(
                            "/auth/registration/confirm",
                            json={
                                "token": token,
                            },
                        )

            self.assertEqual(confirm_response.status_code, 200)
            self.assertFalse(confirm_response.json()["success"])
            self.assertEqual(confirm_response.json()["error"], "Challenge expired")

    @staticmethod
    def _build_test_app() -> FastAPI:
        app = FastAPI()
        app.include_router(auth.router, prefix="/auth")
        return app

    @staticmethod
    def _create_session_factory(database_path: Path):
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(
            engine,
            tables=[
                UserModel.__table__,
                RegistrationIdentityModel.__table__,
                RegistrationChallengeModel.__table__,
            ],
        )
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)


if __name__ == "__main__":
    unittest.main()
