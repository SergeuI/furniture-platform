from __future__ import annotations

import hmac
import hashlib
import secrets
import re
from datetime import datetime, timedelta

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from database.models.registration_identity import (
    RegistrationChallengeModel,
    RegistrationIdentityModel,
)
from database.session import SessionLocal
from services.auth_service import TOKEN_SECRET


IDENTITY_PHONE = "phone"
IDENTITY_TELEGRAM = "telegram"
SUPPORTED_IDENTITY_TYPES = {
    IDENTITY_PHONE,
    IDENTITY_TELEGRAM,
}

CHALLENGE_PENDING = "pending"
CHALLENGE_VERIFIED = "verified"
CHALLENGE_EXPIRED = "expired"
CHALLENGE_BLOCKED = "blocked"
CHALLENGE_CONSUMED = "consumed"

DEFAULT_CHALLENGE_TTL_SECONDS = 10 * 60
DEFAULT_CHALLENGE_MAX_ATTEMPTS = 5


def _utcnow() -> datetime:
    return datetime.utcnow()


def normalize_phone_identity(raw_phone: str) -> str:
    text = str(raw_phone or "").strip()
    if not text:
        raise ValueError("Phone number is required")

    normalized = re.sub(r"[\s().-]+", "", text)

    if not normalized.startswith("+"):
        raise ValueError("Phone number must start with +")

    digits = normalized[1:]
    if not digits.isdigit():
        raise ValueError("Phone number may contain only digits after +")

    if not 8 <= len(digits) <= 15:
        raise ValueError("Phone number must contain 8 to 15 digits after +")

    return f"+{digits}"


def normalize_identity_type(identity_type: str) -> str:
    normalized = str(identity_type or "").strip().lower()
    if normalized == "phone_number":
        normalized = IDENTITY_PHONE
    elif normalized in {"telegram_id", "tg"}:
        normalized = IDENTITY_TELEGRAM

    if normalized not in SUPPORTED_IDENTITY_TYPES:
        raise ValueError(f"Unsupported identity type: {identity_type}")

    return normalized


def normalize_registration_identity_value(identity_type: str, value: str) -> str:
    normalized_type = normalize_identity_type(identity_type)

    if normalized_type == IDENTITY_PHONE:
        return normalize_phone_identity(value)

    normalized_value = str(value or "").strip().lower()
    if not normalized_value:
        raise ValueError("Telegram identity is required")

    return normalized_value


def hash_registration_token(raw_token: str) -> str:
    token = str(raw_token or "").strip()
    if not token:
        raise ValueError("Registration token is required")
    return hmac.new(
        TOKEN_SECRET.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _get_session():
    return SessionLocal()


def _get_registration_identity_in_session(
    db,
    identity_type: str,
    identity_value: str,
):
    normalized_type = normalize_identity_type(identity_type)
    normalized_value = normalize_registration_identity_value(normalized_type, identity_value)
    return (
        db.query(RegistrationIdentityModel)
        .filter(RegistrationIdentityModel.identity_type == normalized_type)
        .filter(RegistrationIdentityModel.identity_value_normalized == normalized_value)
        .first()
    )


def _upsert_registration_identity_in_session(
    db,
    identity_type: str,
    identity_value: str,
    *,
    first_user_id: str | None = None,
    verified_at: datetime | None = None,
    trial_used_at: datetime | None = None,
):
    normalized_type = normalize_identity_type(identity_type)
    normalized_value = normalize_registration_identity_value(normalized_type, identity_value)
    identity = _get_registration_identity_in_session(db, normalized_type, normalized_value)

    if not identity:
        identity = RegistrationIdentityModel(
            identity_type=normalized_type,
            identity_value_normalized=normalized_value,
            first_user_id=first_user_id,
            verified_at=verified_at,
            trial_used_at=trial_used_at,
        )
        db.add(identity)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            identity = _get_registration_identity_in_session(db, normalized_type, normalized_value)
            if not identity:
                raise
        else:
            return identity

    if first_user_id and not identity.first_user_id:
        identity.first_user_id = first_user_id
    if verified_at and not identity.verified_at:
        identity.verified_at = verified_at
    if trial_used_at and not identity.trial_used_at:
        identity.trial_used_at = trial_used_at

    return identity


def _claim_registration_identity_trial_in_session(
    db,
    identity_type: str,
    identity_value: str,
    *,
    trial_used_at: datetime | None = None,
) -> bool:
    normalized_type = normalize_identity_type(identity_type)
    normalized_value = normalize_registration_identity_value(normalized_type, identity_value)
    current_time = trial_used_at or _utcnow()

    result = db.execute(
        update(RegistrationIdentityModel)
        .where(RegistrationIdentityModel.identity_type == normalized_type)
        .where(RegistrationIdentityModel.identity_value_normalized == normalized_value)
        .where(RegistrationIdentityModel.trial_used_at.is_(None))
        .values(trial_used_at=current_time)
    )
    return result.rowcount == 1


def get_registration_identity(
    identity_type: str,
    identity_value: str,
):
    db = _get_session()

    try:
        return _get_registration_identity_in_session(db, identity_type, identity_value)
    finally:
        db.close()


def create_registration_identity(
    identity_type: str,
    identity_value: str,
    *,
    first_user_id: str | None = None,
    verified_at: datetime | None = None,
    trial_used_at: datetime | None = None,
):
    db = _get_session()

    try:
        identity = _upsert_registration_identity_in_session(
            db,
            identity_type,
            identity_value,
            first_user_id=first_user_id,
            verified_at=verified_at,
            trial_used_at=trial_used_at,
        )
        db.commit()
        db.refresh(identity)
        return identity
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def mark_registration_identity_verified(
    identity_type: str,
    identity_value: str,
    *,
    first_user_id: str | None = None,
    verified_at: datetime | None = None,
):
    return create_registration_identity(
        identity_type,
        identity_value,
        first_user_id=first_user_id,
        verified_at=verified_at or _utcnow(),
    )


def identity_has_used_trial(
    identity_type: str,
    identity_value: str,
) -> bool:
    identity = get_registration_identity(identity_type, identity_value)
    return bool(identity and identity.trial_used_at)


def mark_registration_identity_trial_used(
    identity_type: str,
    identity_value: str,
    *,
    first_user_id: str | None = None,
    trial_used_at: datetime | None = None,
):
    return create_registration_identity(
        identity_type,
        identity_value,
        first_user_id=first_user_id,
        trial_used_at=trial_used_at or _utcnow(),
    )


def create_registration_challenge(
    *,
    user_id: str | None,
    channel: str,
    expected_identity_type: str,
    expected_identity_value: str,
    expires_in_seconds: int = DEFAULT_CHALLENGE_TTL_SECONDS,
    max_attempts: int = DEFAULT_CHALLENGE_MAX_ATTEMPTS,
    raw_token: str | None = None,
    created_at: datetime | None = None,
):
    normalized_type = normalize_identity_type(expected_identity_type)
    normalized_value = normalize_registration_identity_value(normalized_type, expected_identity_value)
    token = raw_token or secrets.token_urlsafe(32)
    now = created_at or _utcnow()
    db = _get_session()

    try:
        challenge = RegistrationChallengeModel(
            user_id=user_id,
            channel=str(channel or "").strip().lower() or "unknown",
            token_hash=hash_registration_token(token),
            expected_identity_type=normalized_type,
            expected_identity_value_normalized=normalized_value,
            status=CHALLENGE_PENDING,
            attempts_count=0,
            max_attempts=max_attempts,
            expires_at=now + timedelta(seconds=max(1, int(expires_in_seconds))),
        )
        db.add(challenge)
        db.commit()
        db.refresh(challenge)
        return challenge, token
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_registration_challenge_by_token(raw_token: str):
    token_hash = hash_registration_token(raw_token)
    db = _get_session()

    try:
        return (
            db.query(RegistrationChallengeModel)
            .filter(RegistrationChallengeModel.token_hash == token_hash)
            .first()
        )
    finally:
        db.close()


def verify_registration_challenge(
    raw_token: str,
    supplied_identity_value: str,
    *,
    now: datetime | None = None,
):
    token_hash = hash_registration_token(raw_token)
    current_time = now or _utcnow()
    db = _get_session()

    try:
        challenge = (
            db.query(RegistrationChallengeModel)
            .filter(RegistrationChallengeModel.token_hash == token_hash)
            .first()
        )

        if not challenge:
            return {
                "success": False,
                "error": "Challenge not found",
            }

        if challenge.status in {CHALLENGE_BLOCKED, CHALLENGE_CONSUMED}:
            return {
                "success": False,
                "error": f"Challenge is {challenge.status}",
                "challenge": challenge,
            }

        if challenge.expires_at and challenge.expires_at <= current_time:
            challenge.status = CHALLENGE_EXPIRED
            db.commit()
            db.refresh(challenge)
            return {
                "success": False,
                "error": "Challenge expired",
                "challenge": challenge,
            }

        try:
            normalized_supplied_value = normalize_registration_identity_value(
                challenge.expected_identity_type,
                supplied_identity_value,
            )
        except ValueError as error:
            challenge.attempts_count += 1
            if challenge.attempts_count >= challenge.max_attempts:
                challenge.status = CHALLENGE_BLOCKED
            db.commit()
            db.refresh(challenge)
            return {
                "success": False,
                "error": str(error),
                "challenge": challenge,
            }

        if normalized_supplied_value != challenge.expected_identity_value_normalized:
            challenge.attempts_count += 1
            if challenge.attempts_count >= challenge.max_attempts:
                challenge.status = CHALLENGE_BLOCKED
            db.commit()
            db.refresh(challenge)
            return {
                "success": False,
                "error": "Identity does not match challenge",
                "challenge": challenge,
            }

        challenge.status = CHALLENGE_VERIFIED
        challenge.verified_at = current_time
        db.commit()
        db.refresh(challenge)
        return {
            "success": True,
            "challenge": challenge,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def consume_registration_challenge(
    raw_token: str,
    supplied_identity_value: str,
    *,
    user_id: str | None = None,
    now: datetime | None = None,
):
    token_hash = hash_registration_token(raw_token)
    current_time = now or _utcnow()
    db = _get_session()

    try:
        challenge = (
            db.query(RegistrationChallengeModel)
            .filter(RegistrationChallengeModel.token_hash == token_hash)
            .first()
        )

        if not challenge:
            return {
                "success": False,
                "error": "Challenge not found",
            }

        if challenge.status in {CHALLENGE_BLOCKED, CHALLENGE_CONSUMED}:
            return {
                "success": False,
                "error": f"Challenge is {challenge.status}",
                "challenge": challenge,
            }

        if challenge.expires_at and challenge.expires_at <= current_time:
            challenge.status = CHALLENGE_EXPIRED
            db.commit()
            db.refresh(challenge)
            return {
                "success": False,
                "error": "Challenge expired",
                "challenge": challenge,
            }

        try:
            normalized_supplied_value = normalize_registration_identity_value(
                challenge.expected_identity_type,
                supplied_identity_value,
            )
        except ValueError as error:
            challenge.attempts_count += 1
            if challenge.attempts_count >= challenge.max_attempts:
                challenge.status = CHALLENGE_BLOCKED
            db.commit()
            db.refresh(challenge)
            return {
                "success": False,
                "error": str(error),
                "challenge": challenge,
            }

        if normalized_supplied_value != challenge.expected_identity_value_normalized:
            challenge.attempts_count += 1
            if challenge.attempts_count >= challenge.max_attempts:
                challenge.status = CHALLENGE_BLOCKED
            db.commit()
            db.refresh(challenge)
            return {
                "success": False,
                "error": "Identity does not match challenge",
                "challenge": challenge,
            }

        identity = _upsert_registration_identity_in_session(
            db,
            challenge.expected_identity_type,
            challenge.expected_identity_value_normalized,
            first_user_id=user_id or challenge.user_id,
            verified_at=challenge.verified_at or current_time,
        )

        if not _claim_registration_identity_trial_in_session(
            db,
            challenge.expected_identity_type,
            challenge.expected_identity_value_normalized,
            trial_used_at=current_time,
        ):
            db.rollback()
            return {
                "success": False,
                "error": "trial already used",
                "identity": identity,
            }

        db.refresh(identity)
        if not identity.first_user_id:
            identity.first_user_id = user_id or challenge.user_id
        challenge.status = CHALLENGE_CONSUMED
        challenge.verified_at = challenge.verified_at or current_time
        challenge.consumed_at = current_time
        db.commit()
        db.refresh(challenge)
        db.refresh(identity)

        return {
            "success": True,
            "challenge": challenge,
            "identity": identity,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
