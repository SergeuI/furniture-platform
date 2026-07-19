from __future__ import annotations

import tempfile
import unittest
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.registration_identity import (
    RegistrationChallengeModel,
    RegistrationIdentityModel,
)
from services import registration_identity_service as service


class RegistrationIdentityServiceTests(unittest.TestCase):
    def test_normalize_phone_removes_separators_and_keeps_plus(self) -> None:
        self.assertEqual(
            service.normalize_phone_identity(" +380 (50) 123-45-67 "),
            "+380501234567",
        )

    def test_normalize_phone_rejects_invalid_format(self) -> None:
        with self.assertRaisesRegex(ValueError, "must start with \\+"):
            service.normalize_phone_identity("380501234567")

        with self.assertRaisesRegex(ValueError, "8 to 15 digits"):
            service.normalize_phone_identity("+38012")

    def test_identity_rows_are_unique_per_normalized_value(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "identity.db")

            with mock.patch.object(service, "SessionLocal", session_factory):
                first = service.create_registration_identity(
                    "phone",
                    "+380 (50) 123-45-67",
                    first_user_id="user-1",
                )
                second = service.create_registration_identity(
                    "phone",
                    "+380501234567",
                    first_user_id="user-2",
                )

                self.assertEqual(first.id, second.id)
                self.assertEqual(first.identity_value_normalized, "+380501234567")

                db = session_factory()
                try:
                    count = db.query(RegistrationIdentityModel).count()
                finally:
                    db.close()
                self.assertEqual(count, 1)

    def test_phone_and_telegram_are_separate_identities(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "identity.db")

            with mock.patch.object(service, "SessionLocal", session_factory):
                phone_identity = service.create_registration_identity(
                    "phone",
                    "+380501234567",
                    first_user_id="user-1",
                )
                telegram_identity = service.create_registration_identity(
                    "telegram",
                    "tg-123456",
                    first_user_id="user-2",
                )

                self.assertNotEqual(phone_identity.id, telegram_identity.id)

                db = session_factory()
                try:
                    count = db.query(RegistrationIdentityModel).count()
                finally:
                    db.close()
                self.assertEqual(count, 2)

    def test_create_challenge_stores_only_hash_and_finds_by_raw_token(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "identity.db")

            with mock.patch.object(service, "SessionLocal", session_factory):
                challenge, raw_token = service.create_registration_challenge(
                    user_id="user-1",
                    channel="telegram",
                    expected_identity_type="phone",
                    expected_identity_value="+380501234567",
                    raw_token="secret-token",
                )

                self.assertNotEqual(challenge.token_hash, raw_token)
                self.assertEqual(len(challenge.token_hash), 64)

                fetched = service.get_registration_challenge_by_token("secret-token")
                self.assertIsNotNone(fetched)
                assert fetched is not None
                self.assertEqual(fetched.id, challenge.id)

    def test_expired_challenge_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "identity.db")

            with mock.patch.object(service, "SessionLocal", session_factory):
                challenge, raw_token = service.create_registration_challenge(
                    user_id="user-1",
                    channel="telegram",
                    expected_identity_type="phone",
                    expected_identity_value="+380501234567",
                    raw_token="expired-token",
                    expires_in_seconds=1,
                    created_at=datetime(2026, 7, 19, 10, 0, 0),
                )

                result = service.verify_registration_challenge(
                    raw_token,
                    "+380501234567",
                    now=datetime(2026, 7, 19, 10, 0, 3),
                )

                self.assertFalse(result["success"])
                self.assertEqual(result["error"], "Challenge expired")
                self.assertEqual(result["challenge"].status, service.CHALLENGE_EXPIRED)

    def test_failed_attempts_block_challenge(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "identity.db")

            with mock.patch.object(service, "SessionLocal", session_factory):
                challenge, raw_token = service.create_registration_challenge(
                    user_id="user-1",
                    channel="telegram",
                    expected_identity_type="phone",
                    expected_identity_value="+380501234567",
                    raw_token="blocked-token",
                    max_attempts=2,
                )

                first = service.verify_registration_challenge(raw_token, "+380509999999")
                second = service.verify_registration_challenge(raw_token, "+380508888888")

                self.assertFalse(first["success"])
                self.assertEqual(first["challenge"].status, service.CHALLENGE_PENDING)
                self.assertFalse(second["success"])
                self.assertEqual(second["challenge"].status, service.CHALLENGE_BLOCKED)

    def test_same_identity_can_only_use_trial_once(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "identity.db")

            with mock.patch.object(service, "SessionLocal", session_factory):
                _first_challenge, first_raw_token = service.create_registration_challenge(
                    user_id="user-1",
                    channel="telegram",
                    expected_identity_type="phone",
                    expected_identity_value="+380501234567",
                    raw_token="trial-token-1",
                )
                first = service.consume_registration_challenge(
                    first_raw_token,
                    "+380501234567",
                    user_id="user-1",
                )

                self.assertTrue(first["success"])
                self.assertTrue(service.identity_has_used_trial("phone", "+380501234567"))

                _second_challenge, second_raw_token = service.create_registration_challenge(
                    user_id="user-2",
                    channel="telegram",
                    expected_identity_type="phone",
                    expected_identity_value="+380501234567",
                    raw_token="trial-token-2",
                )
                second = service.consume_registration_challenge(
                    second_raw_token,
                    "+380501234567",
                    user_id="user-2",
                )
                stored_challenge = service.get_registration_challenge_by_token(second_raw_token)

                self.assertFalse(second["success"])
                self.assertEqual(second["error"], "trial already used")
                self.assertIsNotNone(stored_challenge)
                assert stored_challenge is not None
                self.assertEqual(stored_challenge.status, service.CHALLENGE_PENDING)

    def test_concurrent_trial_claims_are_atomic(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "identity.db")

            with mock.patch.object(service, "SessionLocal", session_factory):
                service.create_registration_identity(
                    "phone",
                    "+380501234567",
                    first_user_id="user-1",
                )

                start_barrier = threading.Barrier(2)
                results: list[bool] = []
                errors: list[BaseException] = []

                def worker() -> None:
                    db = session_factory()
                    try:
                        start_barrier.wait(timeout=5)
                        granted = service._claim_registration_identity_trial_in_session(
                            db,
                            "phone",
                            "+380501234567",
                            trial_used_at=datetime(2026, 7, 19, 10, 0, 0),
                        )
                        db.commit()
                        results.append(granted)
                    except BaseException as error:  # pragma: no cover - debug aid if test flakes
                        errors.append(error)
                    finally:
                        db.close()

                threads = [threading.Thread(target=worker) for _ in range(2)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=10)

                self.assertFalse(errors, f"Unexpected concurrency errors: {errors!r}")
                self.assertEqual(sorted(results), [False, True])

                db = session_factory()
                try:
                    identities = db.query(RegistrationIdentityModel).all()
                finally:
                    db.close()

                self.assertEqual(len(identities), 1)
                self.assertIsNotNone(identities[0].trial_used_at)

    def test_parallel_identity_creation_does_not_duplicate(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "identity.db")

            with mock.patch.object(service, "SessionLocal", session_factory):
                start_barrier = threading.Barrier(2)
                results: list[int] = []
                errors: list[BaseException] = []

                def worker(user_id: str) -> None:
                    try:
                        start_barrier.wait(timeout=5)
                        identity = service.create_registration_identity(
                            "phone",
                            "+380501234567",
                            first_user_id=user_id,
                        )
                        results.append(identity.id)
                    except BaseException as error:  # pragma: no cover - debug aid if test flakes
                        errors.append(error)

                threads = [
                    threading.Thread(target=worker, args=("user-1",)),
                    threading.Thread(target=worker, args=("user-2",)),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=10)

                self.assertFalse(errors, f"Unexpected concurrency errors: {errors!r}")
                self.assertEqual(len(results), 2)
                self.assertEqual(len(set(results)), 1)

                db = session_factory()
                try:
                    count = db.query(RegistrationIdentityModel).count()
                finally:
                    db.close()
                self.assertEqual(count, 1)

    def test_write_error_rolls_back_changes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "identity.db")
            session = session_factory()
            session.commit = mock.Mock(side_effect=RuntimeError("boom"))
            session.rollback = mock.Mock(wraps=session.rollback)

            with mock.patch.object(service, "SessionLocal", lambda: session):
                with self.assertRaises(RuntimeError):
                    service.create_registration_identity(
                        "phone",
                        "+380501234567",
                        first_user_id="user-1",
                    )

            self.assertTrue(session.rollback.called)

            db = session_factory()
            try:
                count = db.query(RegistrationIdentityModel).count()
            finally:
                db.close()
            self.assertEqual(count, 0)

    def test_consumed_challenge_cannot_be_reused(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "identity.db")

            with mock.patch.object(service, "SessionLocal", session_factory):
                _challenge, raw_token = service.create_registration_challenge(
                    user_id="user-1",
                    channel="telegram",
                    expected_identity_type="phone",
                    expected_identity_value="+380501234567",
                    raw_token="reuse-token",
                )
                first = service.consume_registration_challenge(
                    raw_token,
                    "+380501234567",
                    user_id="user-1",
                )
                second = service.consume_registration_challenge(
                    raw_token,
                    "+380501234567",
                    user_id="user-1",
                )

                self.assertTrue(first["success"])
                self.assertFalse(second["success"])
                self.assertEqual(second["error"], "Challenge is consumed")

    def test_invalid_token_returns_expected_error(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "identity.db")

            with mock.patch.object(service, "SessionLocal", session_factory):
                result = service.verify_registration_challenge("missing-token", "+380501234567")

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "Challenge not found")

    @staticmethod
    def _create_session_factory(database_path: Path):
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(
            engine,
            tables=[
                RegistrationIdentityModel.__table__,
                RegistrationChallengeModel.__table__,
            ],
        )
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)


if __name__ == "__main__":
    unittest.main()
