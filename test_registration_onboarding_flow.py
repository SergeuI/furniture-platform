from __future__ import annotations

import os
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

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
from services.registration_identity_service import CHALLENGE_BLOCKED, CHALLENGE_CONSUMED, CHALLENGE_PENDING


class RegistrationOnboardingFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_creates_pending_user_without_trial(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
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
            self.assertIsNotNone(response.get("debug_verification_code"))

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
            self.assertIn("error", login_response)

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
                        challenge_id=start_response["challenge_id"],
                        code=start_response["debug_verification_code"],
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
                    RegistrationConfirmRequestSchema(
                        challenge_id=first_start["challenge_id"],
                        code=first_start["debug_verification_code"],
                    )
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
                    RegistrationConfirmRequestSchema(
                        challenge_id=second_start["challenge_id"],
                        code=second_start["debug_verification_code"],
                    )
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
            self.assertIn("error", duplicate_response)
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

            self.assertIsNone(disabled_response.get("debug_verification_code"))
            self.assertIsNotNone(enabled_response.get("debug_verification_code"))

    async def test_registration_code_supports_leading_zero_and_is_hashed_in_db(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")
            fixed_now = datetime(2026, 1, 1, 12, 0, 0)

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.object(
                onboarding.secrets,
                "randbelow",
                return_value=4271,
            ), mock.patch.object(
                onboarding,
                "_utcnow",
                return_value=fixed_now,
            ), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                start_response = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="Leading Zero",
                        email="leading-zero@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                ))

                confirm_response = await auth.registration_confirm_route(
                    RegistrationConfirmRequestSchema(
                        challenge_id=start_response["challenge_id"],
                        code=start_response["debug_verification_code"],
                    )
                )

            self.assertEqual(start_response["debug_verification_code"], "004271")
            self.assertTrue(confirm_response["success"])

            db = session_factory()
            try:
                challenge = db.query(RegistrationChallengeModel).first()
            finally:
                db.close()

            self.assertIsNotNone(challenge)
            assert challenge is not None
            self.assertEqual(challenge.expires_at - fixed_now, timedelta(minutes=10))
            self.assertNotEqual(challenge.token_hash, "004271")
            self.assertEqual(len(challenge.token_hash), 64)
            self.assertTrue(all(char in "0123456789abcdef" for char in challenge.token_hash))

    async def test_same_code_stays_bound_to_challenge_id(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.object(
                onboarding.secrets,
                "randbelow",
                side_effect=[123456, 123456],
            ), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                first_start = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="First Code User",
                        email="first-code@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                ))
                second_start = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="Second Code User",
                        email="second-code@example.com",
                        password="Password123",
                        phone="+380501234568",
                    )
                ))

                first_confirm = await auth.registration_confirm_route(
                    RegistrationConfirmRequestSchema(
                        challenge_id=first_start["challenge_id"],
                        code=first_start["debug_verification_code"],
                    )
                )
                second_confirm = await auth.registration_confirm_route(
                    RegistrationConfirmRequestSchema(
                        challenge_id=second_start["challenge_id"],
                        code=second_start["debug_verification_code"],
                    )
                )

            self.assertTrue(first_confirm["success"])
            self.assertTrue(second_confirm["success"])
            self.assertEqual(first_start["debug_verification_code"], second_start["debug_verification_code"])

    async def test_wrong_code_blocks_after_five_attempts(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.object(
                onboarding.secrets,
                "randbelow",
                return_value=123456,
            ), mock.patch.dict(
                os.environ,
                {onboarding.LOCAL_TEST_ENV: "true"},
                clear=True,
            ):
                start_response = self._response_json(await auth.registration_start_route(
                    RegistrationStartRequestSchema(
                        name="Blocked Attempts",
                        email="blocked-attempts@example.com",
                        password="Password123",
                        phone="+380501234567",
                    )
                ))

                wrong_attempts = []
                for _ in range(5):
                    wrong_attempts.append(await auth.registration_confirm_route(
                        RegistrationConfirmRequestSchema(
                            challenge_id=start_response["challenge_id"],
                            code="000000",
                        )
                    ))

            self.assertEqual(wrong_attempts[-1]["error"], "Verification code does not match challenge")

            db = session_factory()
            try:
                challenge = db.query(RegistrationChallengeModel).first()
            finally:
                db.close()

            self.assertIsNotNone(challenge)
            assert challenge is not None
            self.assertEqual(challenge.attempts_count, 5)
            self.assertEqual(challenge.status, CHALLENGE_BLOCKED)

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
                                challenge_id=start_response["challenge_id"],
                                code=start_response["debug_verification_code"],
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
                        challenge_id=start_response["challenge_id"],
                        code=start_response["debug_verification_code"],
                    )
                )
                invalid_response = await auth.registration_confirm_route(
                    RegistrationConfirmRequestSchema(
                        challenge_id=start_response["challenge_id"],
                        code="123456",
                    )
                )
                consumed_response = await auth.registration_confirm_route(
                    RegistrationConfirmRequestSchema(
                        challenge_id=start_response["challenge_id"],
                        code=start_response["debug_verification_code"],
                    )
                )

            self.assertTrue(confirm_response["success"])
            self.assertFalse(invalid_response["success"])
            self.assertEqual(invalid_response["error"], "Challenge is consumed")
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
                    self.assertNotIn("user_id", start_payload)
                    self.assertEqual(start_payload["registration_status"], onboarding.REGISTRATION_STATUS_PENDING_PHONE)
                    self.assertIn("debug_verification_code", start_payload)

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
                    self.assertIn("error", duplicate_payload)
                    self.assertNotIn("user_id", duplicate_payload)
                    self.assertNotIn("challenge_id", duplicate_payload)
                    self.assertNotIn("challenge_status", duplicate_payload)
                    self.assertNotIn("registration_status", duplicate_payload)
                    self.assertNotIn("trial_granted", duplicate_payload)

                    confirm_response = client.post(
                        "/auth/registration/confirm",
                        json={
                            "challenge_id": start_payload["challenge_id"],
                            "code": start_payload["debug_verification_code"],
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
                    self.assertIn("error", pending_login_response.json())

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
                    self.assertIn("error", blocked_login_response.json())

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
                    challenge_id = start_response.json()["challenge_id"]
                    code = start_response.json()["debug_verification_code"]

                    with mock.patch.object(
                        onboarding,
                        "_utcnow",
                        return_value=datetime.utcnow() + timedelta(minutes=11),
                    ):
                        confirm_response = client.post(
                            "/auth/registration/confirm",
                            json={
                                "challenge_id": challenge_id,
                                "code": code,
                            },
                        )

            self.assertEqual(confirm_response.status_code, 200)
            self.assertFalse(confirm_response.json()["success"])
            self.assertEqual(confirm_response.json()["error"], "Challenge expired")

    def test_telegram_registration_start_and_status_are_private(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")
            app = self._build_test_app()

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {
                    onboarding.TELEGRAM_REGISTRATION_ENV: "true",
                    onboarding.TELEGRAM_BOT_USERNAME_ENV: "furniture_bot",
                    "BOT_TOKEN": "123456:telegram-test-bot-token",
                    "AUTH_SECRET_KEY": "0123456789abcdef0123456789abcdef",
                    onboarding.TELEGRAM_TEST_EMAILS_ENV: "telegram@example.com",
                },
                clear=True,
            ):
                with TestClient(app) as client:
                    start_response = client.post(
                        "/auth/registration/start",
                        json={
                            "name": "Telegram User",
                            "email": "telegram@example.com",
                            "password": "Password123",
                            "phone": "+380501234567",
                        },
                    )
                    self.assertEqual(start_response.status_code, 200)
                    start_payload = start_response.json()
                    self.assertTrue(start_payload["success"])
                    self.assertNotIn("challenge_id", start_payload)
                    self.assertNotIn("debug_verification_code", start_payload)
                    self.assertIn("telegram_confirmation_url", start_payload)
                    self.assertIn("telegram_status_token", start_payload)

                    confirmation_url = start_payload["telegram_confirmation_url"]
                    parsed = urlparse(confirmation_url)
                    query = parse_qs(parsed.query)
                    self.assertEqual(parsed.netloc, "t.me")
                    self.assertEqual(parsed.path.strip("/"), "furniture_bot")
                    self.assertIn("start", query)
                    payload = query["start"][0]
                    self.assertNotIn("telegram@example.com", confirmation_url)
                    self.assertNotIn("+380501234567", confirmation_url)
                    self.assertLessEqual(len(payload), 64)

                    db = session_factory()
                    try:
                        challenge = db.query(RegistrationChallengeModel).first()
                    finally:
                        db.close()

                    self.assertIsNotNone(challenge)
                    assert challenge is not None
                    self.assertIsNotNone(challenge.token_hash)
                    self.assertIsNotNone(challenge.status_token_hash)
                    self.assertEqual(len(challenge.token_hash or ""), 64)
                    self.assertEqual(len(challenge.status_token_hash or ""), 64)

                    status_response = client.post(
                        "/auth/registration/telegram/status",
                        json={"status_token": start_payload["telegram_status_token"]},
                    )
                    self.assertEqual(status_response.status_code, 200)
                    status_payload = status_response.json()
                    self.assertTrue(status_payload["success"])
                    self.assertEqual(status_payload["challenge_status"], CHALLENGE_PENDING)
                    self.assertEqual(status_payload["registration_status"], onboarding.REGISTRATION_STATUS_PENDING_PHONE)
                    self.assertFalse(status_payload["phone_verified"])
                    self.assertFalse(status_payload["trial_granted"])
                    self.assertEqual(status_payload["effective_plan"], "free")
                    self.assertIsNone(status_payload["trial_ends_at"])
                    self.assertNotIn("user_id", status_payload)
                    self.assertNotIn("challenge_id", status_payload)
                    self.assertNotIn("email", status_payload)
                    self.assertNotIn("phone", status_payload)
                    self.assertNotIn("telegram_id", status_payload)

    def test_telegram_registration_confirm_grants_trial_and_blocks_reuse(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {
                    onboarding.TELEGRAM_REGISTRATION_ENV: "true",
                    onboarding.TELEGRAM_BOT_USERNAME_ENV: "furniture_bot",
                    "BOT_TOKEN": "123456:telegram-test-bot-token",
                    "AUTH_SECRET_KEY": "0123456789abcdef0123456789abcdef",
                    onboarding.TELEGRAM_TEST_EMAILS_ENV: "telegram-confirm@example.com",
                },
                clear=True,
            ):
                start_response = onboarding.start_pending_phone_registration(
                    name="Telegram Confirm",
                    email="telegram-confirm@example.com",
                    password="Password123",
                    phone="+380501234567",
                )

                confirmation_url = start_response["telegram_confirmation_url"]
                payload = parse_qs(urlparse(confirmation_url).query)["start"][0]
                first_confirm = onboarding.confirm_pending_phone_registration_via_telegram(
                    payload=payload,
                    telegram_user_id=987654321,
                    contact_phone="+380501234567",
                )
                second_confirm = onboarding.confirm_pending_phone_registration_via_telegram(
                    payload=payload,
                    telegram_user_id=987654321,
                    contact_phone="+380501234567",
                )

            self.assertTrue(first_confirm["success"])
            self.assertTrue(first_confirm["trial_granted"])
            self.assertEqual(first_confirm["effective_plan"], "trial")
            self.assertEqual(first_confirm["challenge_status"], CHALLENGE_CONSUMED)
            self.assertFalse(second_confirm["success"])
            self.assertEqual(second_confirm["error"], "Challenge is consumed")

            db = session_factory()
            try:
                user = db.query(UserModel).filter(UserModel.email == "telegram-confirm@example.com").first()
                identity = db.query(RegistrationIdentityModel).filter(
                    RegistrationIdentityModel.identity_value_normalized == "+380501234567",
                ).first()
            finally:
                db.close()

            self.assertIsNotNone(user)
            assert user is not None
            self.assertEqual(user.registration_status, onboarding.REGISTRATION_STATUS_ACTIVE)
            self.assertIsNotNone(user.phone_verified_at)
            self.assertIsNotNone(user.trial_started_at)
            self.assertIsNotNone(user.trial_ends_at)
            self.assertEqual(user.trial_ends_at - user.trial_started_at, timedelta(days=7))
            self.assertIsNotNone(identity)
            assert identity is not None
            self.assertIsNotNone(identity.trial_used_at)

    def test_telegram_registration_rejects_non_allowlisted_email(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")
            app = self._build_test_app()

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {
                    onboarding.TELEGRAM_REGISTRATION_ENV: "true",
                    onboarding.TELEGRAM_BOT_USERNAME_ENV: "furniture_bot",
                    "BOT_TOKEN": "123456:telegram-test-bot-token",
                    "AUTH_SECRET_KEY": "0123456789abcdef0123456789abcdef",
                    onboarding.TELEGRAM_TEST_EMAILS_ENV: "allowed@example.com",
                },
                clear=True,
            ):
                with TestClient(app) as client:
                    response = client.post(
                        "/auth/registration/start",
                        json={
                            "name": "Blocked Telegram User",
                            "email": "blocked@example.com",
                            "password": "Password123",
                            "phone": "+380501234567",
                        },
                    )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertFalse(payload["success"])
            self.assertIn("error", payload)
            self.assertNotIn("telegram_confirmation_url", payload)
            self.assertNotIn("telegram_status_token", payload)

    def test_telegram_confirmation_rejects_wrong_phone(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {
                    onboarding.TELEGRAM_REGISTRATION_ENV: "true",
                    onboarding.TELEGRAM_BOT_USERNAME_ENV: "furniture_bot",
                    "BOT_TOKEN": "123456:telegram-test-bot-token",
                    "AUTH_SECRET_KEY": "0123456789abcdef0123456789abcdef",
                    onboarding.TELEGRAM_TEST_EMAILS_ENV: "telegram-wrong-phone@example.com",
                },
                clear=True,
            ):
                start_response = onboarding.start_pending_phone_registration(
                    name="Telegram Wrong Phone",
                    email="telegram-wrong-phone@example.com",
                    password="Password123",
                    phone="+380501234567",
                )

                confirmation_url = start_response["telegram_confirmation_url"]
                payload = parse_qs(urlparse(confirmation_url).query)["start"][0]
                confirm_response = onboarding.confirm_pending_phone_registration_via_telegram(
                    payload=payload,
                    telegram_user_id=987654321,
                    contact_phone="+380501234568",
                )

            self.assertFalse(confirm_response["success"])
            self.assertEqual(confirm_response["error"], "Phone number does not match pending registration")

            db = session_factory()
            try:
                user = db.query(UserModel).filter(UserModel.email == "telegram-wrong-phone@example.com").first()
                challenge = db.query(RegistrationChallengeModel).first()
            finally:
                db.close()

            self.assertIsNotNone(user)
            assert user is not None
            self.assertEqual(user.registration_status, onboarding.REGISTRATION_STATUS_PENDING_PHONE)
            self.assertIsNotNone(challenge)
            assert challenge is not None
            self.assertEqual(challenge.status, CHALLENGE_PENDING)

    def test_telegram_registration_rejects_fallback_secret_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {
                    onboarding.TELEGRAM_REGISTRATION_ENV: "true",
                    onboarding.TELEGRAM_BOT_USERNAME_ENV: "furniture_bot",
                    "BOT_TOKEN": "123456:telegram-test-bot-token",
                    "AUTH_SECRET_KEY": "furniture-platform-local-dev-secret",
                    onboarding.TELEGRAM_TEST_EMAILS_ENV: "security@example.com",
                },
                clear=True,
            ):
                response = onboarding.start_pending_phone_registration(
                    name="Security User",
                    email="security@example.com",
                    password="Password123",
                    phone="+380501234567",
                )

            self.assertFalse(response["success"])
            self.assertEqual(response["error"], "Telegram registration security config is invalid")

    def test_telegram_registration_security_logging_is_safe(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {
                    onboarding.TELEGRAM_REGISTRATION_ENV: "true",
                    onboarding.TELEGRAM_BOT_USERNAME_ENV: "furniture_bot",
                    "BOT_TOKEN": "123456:telegram-test-bot-token",
                    "AUTH_SECRET_KEY": "0123456789abcdef0123456789abcdef",
                    onboarding.TELEGRAM_TEST_EMAILS_ENV: "log-safe@example.com",
                },
                clear=True,
            ), self.assertLogs(onboarding.logger, level="INFO") as logs:
                start_response = onboarding.start_pending_phone_registration(
                    name="Log Safe",
                    email="log-safe@example.com",
                    password="Password123",
                    phone="+380501234567",
                )
                onboarding.confirm_pending_phone_registration_via_telegram(
                    payload=start_response["telegram_confirmation_url"].split("start=")[1],
                    telegram_user_id=987654321,
                    contact_phone="+380501234567",
                )

            log_output = "\n".join(logs.output)
            self.assertIn("Telegram registration: enabled", log_output)
            self.assertIn("AUTH_SECRET_KEY configured: yes", log_output)
            self.assertIn("Telegram bot username configured: yes", log_output)
            self.assertIn("Bot token configured: yes", log_output)
            self.assertNotIn("0123456789abcdef0123456789abcdef", log_output)
            self.assertNotIn("123456:telegram-test-bot-token", log_output)
            self.assertNotIn("log-safe@example.com", log_output)
            self.assertNotIn("telegram_confirmation_url", log_output)

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
