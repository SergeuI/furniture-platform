from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from database.models.registration_identity import (
    RegistrationChallengeModel,
    RegistrationIdentityModel,
)
from database.models.user import UserModel
from database.session import SessionLocal
from services.auth_service import hash_password
from services.registration_identity_service import (
    CHALLENGE_CONSUMED,
    CHALLENGE_EXPIRED,
    CHALLENGE_PENDING,
    CHALLENGE_BLOCKED,
    DEFAULT_CHALLENGE_MAX_ATTEMPTS,
    DEFAULT_CHALLENGE_TTL_SECONDS,
    IDENTITY_PHONE,
    _claim_registration_identity_trial_in_session,
    _upsert_registration_identity_in_session,
    hash_registration_token,
    normalize_phone_identity,
)
from services.subscription_service import build_subscription_status


REGISTRATION_STATUS_PENDING_PHONE = "pending_phone"
REGISTRATION_STATUS_ACTIVE = "active"
REGISTRATION_STATUS_BLOCKED = "blocked"

LOCAL_TEST_CHANNEL = "local_test"
LOCAL_TEST_ENV = "FURNITURE_REGISTRATION_LOCAL_TEST_MODE"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _is_enabled(value: bool | None = None) -> bool:
    if value is not None:
        return bool(value)

    import os

    return os.getenv(LOCAL_TEST_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_email(email: str) -> str:
    text = str(email or "").strip().lower()
    if not text:
        raise ValueError("Email is required")
    return text


def _resolve_username(name: str | None = None, username: str | None = None) -> str:
    candidate = username if username is not None else name
    text = str(candidate or "").strip()
    if not text:
        raise ValueError("Username is required")
    return text


def _generate_registration_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _normalize_registration_code(code: str) -> str:
    normalized = "".join(str(code or "").split())
    if len(normalized) != 6 or not normalized.isdigit():
        raise ValueError("Verification code must contain exactly 6 digits")
    return normalized


def _format_registration_code(code: str) -> str:
    normalized = _normalize_registration_code(code)
    return f"{normalized[:3]} {normalized[3:]}"


def _hash_registration_code(challenge_id: int, code: str) -> str:
    normalized_code = _normalize_registration_code(code)
    return hash_registration_token(f"{challenge_id}:{normalized_code}")


def _build_user_status_payload(user, *, now: datetime | None = None) -> dict:
    subscription = build_subscription_status(user, now=now)
    return {
        "registration_status": user.registration_status,
        "phone_verified": bool(user.phone_verified_at),
        "trial_granted": bool(user.trial_started_at and user.trial_ends_at),
        "effective_plan": subscription["effective_plan"],
        "trial_ends_at": user.trial_ends_at,
    }


def _get_challenge_by_id_in_session(db, challenge_id: int):
    return (
        db.query(RegistrationChallengeModel)
        .filter(RegistrationChallengeModel.id == challenge_id)
        .first()
    )


def _get_challenge_by_token_hash_in_session(db, token_hash: str):
    return (
        db.query(RegistrationChallengeModel)
        .filter(RegistrationChallengeModel.token_hash == token_hash)
        .first()
    )


def _build_registration_response(
    *,
    success: bool,
    user,
    challenge,
    message: str | None = None,
    debug_verification_code: str | None = None,
    error: str | None = None,
    now: datetime | None = None,
) -> dict:
    response = {
        "success": success,
        "challenge_id": getattr(challenge, "id", None),
        "challenge_status": getattr(challenge, "status", None),
        "message": message,
        "error": error,
    }

    if user:
        response.update(_build_user_status_payload(user, now=now))

    if debug_verification_code is not None:
        response["debug_verification_code"] = debug_verification_code

    return response


def _build_duplicate_email_response() -> dict:
    return {
        "success": False,
        "error": "Не вдалося розпочати реєстрацію з указаними даними.",
    }


def start_pending_phone_registration(
    *,
    email: str,
    password: str,
    phone: str,
    name: str | None = None,
    username: str | None = None,
    local_test_mode: bool | None = None,
    debug_verification_code: str | None = None,
    now: datetime | None = None,
) -> dict:
    try:
        normalized_email = _normalize_email(email)
        normalized_phone = normalize_phone_identity(phone)
        resolved_username = _resolve_username(name=name, username=username)
    except ValueError as error:
        return {
            "success": False,
            "error": str(error),
        }

    current_time = now or _utcnow()
    debug_mode = _is_enabled(local_test_mode)
    verification_code = _normalize_registration_code(
        debug_verification_code if debug_verification_code is not None else _generate_registration_code()
    )
    db = SessionLocal()

    try:
        existing_user = (
            db.query(UserModel)
            .filter(UserModel.email == normalized_email)
            .first()
        )

        if existing_user:
            return _build_duplicate_email_response()

        user = UserModel(
            email=normalized_email,
            username=resolved_username,
            phone=normalized_phone,
            password_hash=hash_password(password),
            role="free",
            registration_status=REGISTRATION_STATUS_PENDING_PHONE,
            phone_verified_at=None,
            trial_started_at=None,
            trial_ends_at=None,
            is_active=True,
        )
        db.add(user)
        db.flush()

        challenge = RegistrationChallengeModel(
            user_id=user.id,
            channel=LOCAL_TEST_CHANNEL,
            token_hash=secrets.token_hex(32),
            expected_identity_type=IDENTITY_PHONE,
            expected_identity_value_normalized=normalized_phone,
            status=CHALLENGE_PENDING,
            attempts_count=0,
            max_attempts=DEFAULT_CHALLENGE_MAX_ATTEMPTS,
            expires_at=current_time + timedelta(seconds=DEFAULT_CHALLENGE_TTL_SECONDS),
        )
        db.add(challenge)
        db.flush()
        challenge.token_hash = _hash_registration_code(challenge.id, verification_code)
        db.commit()
        db.refresh(user)
        db.refresh(challenge)

        return _build_registration_response(
            success=True,
            user=user,
            challenge=challenge,
            message=(
                "Local verification code returned for local test mode"
                if debug_mode
                else "Pending registration created; delivery channel is not connected yet"
            ),
            debug_verification_code=verification_code if debug_mode else None,
            now=current_time,
        )
    except IntegrityError:
        db.rollback()
        existing_user = (
            db.query(UserModel)
            .filter(UserModel.email == normalized_email)
            .first()
        )
        if existing_user:
            return _build_duplicate_email_response()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def confirm_pending_phone_registration(
    *,
    challenge_id: int,
    code: str,
    now: datetime | None = None,
) -> dict:
    try:
        normalized_code = _normalize_registration_code(code)
    except ValueError as error:
        return {
            "success": False,
            "error": str(error),
        }

    current_time = now or _utcnow()
    db = SessionLocal()

    try:
        challenge = _get_challenge_by_id_in_session(db, challenge_id)

        if not challenge:
            return {
                "success": False,
                "error": "Challenge not found",
            }

        if challenge.status in {CHALLENGE_BLOCKED, CHALLENGE_CONSUMED}:
            return {
                "success": False,
                "error": f"Challenge is {challenge.status}",
                "challenge_id": challenge.id,
            }

        if challenge.expires_at and challenge.expires_at <= current_time:
            challenge.status = CHALLENGE_EXPIRED
            db.commit()
            db.refresh(challenge)
            return {
                "success": False,
                "error": "Challenge expired",
                "challenge_id": challenge.id,
            }

        expected_hash = _hash_registration_code(challenge.id, normalized_code)
        if not hmac.compare_digest(challenge.token_hash or "", expected_hash):
            challenge.attempts_count += 1
            if challenge.attempts_count >= challenge.max_attempts:
                challenge.status = CHALLENGE_BLOCKED
            db.commit()
            db.refresh(challenge)
            return {
                "success": False,
                "error": "Verification code does not match challenge",
                "challenge_id": challenge.id,
            }

        user = (
            db.query(UserModel)
            .filter(UserModel.id == challenge.user_id)
            .first()
        )

        if not user:
            return {
                "success": False,
                "error": "User not found",
                "challenge_id": challenge.id,
            }

        if (user.registration_status or "").strip().lower() != REGISTRATION_STATUS_PENDING_PHONE:
            return {
                "success": False,
                "error": "User registration is not pending",
                "challenge_id": challenge.id,
            }

        normalized_phone = normalize_phone_identity(user.phone or challenge.expected_identity_value_normalized)
        identity = _upsert_registration_identity_in_session(
            db,
            IDENTITY_PHONE,
            normalized_phone,
            first_user_id=user.id,
            verified_at=current_time,
        )

        trial_granted = _claim_registration_identity_trial_in_session(
            db,
            IDENTITY_PHONE,
            normalized_phone,
            trial_used_at=current_time,
        )

        user.registration_status = REGISTRATION_STATUS_ACTIVE
        user.phone_verified_at = current_time
        user.phone = normalized_phone
        if trial_granted:
            user.trial_started_at = current_time
            user.trial_ends_at = current_time + timedelta(days=7)
        else:
            user.trial_started_at = None
            user.trial_ends_at = None

        if not identity.first_user_id:
            identity.first_user_id = user.id
        if not identity.verified_at:
            identity.verified_at = current_time

        challenge.status = CHALLENGE_CONSUMED
        challenge.consumed_at = current_time
        challenge.verified_at = challenge.verified_at or current_time

        db.commit()
        db.refresh(user)
        db.refresh(challenge)
        db.refresh(identity)

        return {
            "success": True,
            "challenge_id": challenge.id,
            "challenge_status": challenge.status,
            **_build_user_status_payload(user, now=current_time),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
