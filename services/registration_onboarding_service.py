from __future__ import annotations

import logging
import hmac
import os
import re
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
    IDENTITY_TELEGRAM,
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
TELEGRAM_CHANNEL = "telegram"
LOCAL_TEST_ENV = "FURNITURE_REGISTRATION_LOCAL_TEST_MODE"
TELEGRAM_REGISTRATION_ENV = "FURNITURE_TELEGRAM_REGISTRATION_ENABLED"
TELEGRAM_BOT_USERNAME_ENV = "TELEGRAM_BOT_USERNAME"
PUBLIC_APP_URL_ENV = "PUBLIC_APP_URL"
TELEGRAM_TEST_EMAILS_ENV = "FURNITURE_REGISTRATION_TEST_EMAILS"
LOCAL_DEV_AUTH_SECRET_FALLBACK = "furniture-platform-local-dev-secret"


logger = logging.getLogger(__name__)


class TelegramRegistrationSecurityConfigError(RuntimeError):
    pass


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


def _generate_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def _normalize_opaque_token(token: str) -> str:
    normalized = str(token or "").strip()
    if not normalized:
        raise ValueError("Token is required")
    return normalized


def _hash_opaque_token(token: str) -> str:
    return hash_registration_token(_normalize_opaque_token(token))


def _normalize_bot_username(raw_username: str | None) -> str:
    normalized = str(raw_username or "").strip().lstrip("@")
    if not normalized:
        raise ValueError("Telegram bot username is required")
    return normalized


def _build_telegram_confirmation_url(bot_username: str, payload: str) -> str:
    normalized_username = _normalize_bot_username(bot_username)
    normalized_payload = _normalize_opaque_token(payload)
    return f"https://t.me/{normalized_username}?start={normalized_payload}"


def _parse_registration_email_allowlist(raw_value: str | None) -> set[str]:
    return {
        _normalize_email(item)
        for item in re.split(r"[,\n;]+", str(raw_value or ""))
        if str(item or "").strip()
    }


def _is_telegram_registration_enabled() -> bool:
    return _is_enabled(os.getenv(TELEGRAM_REGISTRATION_ENV))


def validate_telegram_registration_security_config() -> bool:
    telegram_enabled = _is_telegram_registration_enabled()
    auth_secret = os.getenv("AUTH_SECRET_KEY", "").strip()
    bot_username = os.getenv(TELEGRAM_BOT_USERNAME_ENV, "").strip()
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    auth_secret_configured = (
        bool(auth_secret)
        and auth_secret != LOCAL_DEV_AUTH_SECRET_FALLBACK
        and len(auth_secret) >= 32
    )
    bot_username_configured = bool(bot_username)
    bot_token_configured = bool(bot_token)

    logger.info(
        "Telegram registration: %s; AUTH_SECRET_KEY configured: %s; Telegram bot username configured: %s; Bot token configured: %s",
        "enabled" if telegram_enabled else "disabled",
        "yes" if auth_secret_configured else "no",
        "yes" if bot_username_configured else "no",
        "yes" if bot_token_configured else "no",
    )

    if telegram_enabled and not (
        auth_secret_configured
        and bot_username_configured
        and bot_token_configured
    ):
        raise TelegramRegistrationSecurityConfigError(
            "Telegram registration security config is invalid"
        )

    return telegram_enabled


def _is_telegram_registration_allowed_for_email(email: str) -> bool:
    allowlist = _parse_registration_email_allowlist(os.getenv(TELEGRAM_TEST_EMAILS_ENV))
    if not allowlist:
        return True
    return _normalize_email(email) in allowlist


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


def _build_registration_response_v2(
    *,
    success: bool,
    user,
    challenge,
    include_challenge_id: bool = True,
    message: str | None = None,
    debug_verification_code: str | None = None,
    telegram_confirmation_url: str | None = None,
    telegram_status_token: str | None = None,
    error: str | None = None,
    now: datetime | None = None,
) -> dict:
    response = {
        "success": success,
        "challenge_status": getattr(challenge, "status", None),
        "message": message,
        "error": error,
    }

    if include_challenge_id:
        response["challenge_id"] = getattr(challenge, "id", None)

    if user:
        response.update(_build_user_status_payload(user, now=now))

    if debug_verification_code is not None:
        response["debug_verification_code"] = debug_verification_code

    if telegram_confirmation_url is not None:
        response["telegram_confirmation_url"] = telegram_confirmation_url

    if telegram_status_token is not None:
        response["telegram_status_token"] = telegram_status_token

    return response


def _build_registration_not_allowed_response() -> dict:
    return _build_duplicate_email_response()


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
    telegram_mode = False
    telegram_payload = None
    telegram_status_token = None
    telegram_confirmation_url = None

    if not debug_mode:
        try:
            telegram_enabled = validate_telegram_registration_security_config()
        except TelegramRegistrationSecurityConfigError as error:
            return {
                "success": False,
                "error": str(error),
            }

        if not telegram_enabled:
            return _build_registration_not_allowed_response()

        if not _is_telegram_registration_allowed_for_email(normalized_email):
            return _build_registration_not_allowed_response()

        bot_username = os.getenv(TELEGRAM_BOT_USERNAME_ENV, "").strip()
        if not bot_username:
            return _build_registration_not_allowed_response()

        telegram_mode = True
        telegram_payload = _generate_opaque_token()
        telegram_status_token = _generate_opaque_token()
        telegram_confirmation_url = _build_telegram_confirmation_url(bot_username, telegram_payload)

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
            channel=TELEGRAM_CHANNEL if telegram_mode else LOCAL_TEST_CHANNEL,
            token_hash=(
                _hash_opaque_token(telegram_payload)
                if telegram_mode
                else secrets.token_hex(32)
            ),
            status_token_hash=_hash_opaque_token(telegram_status_token) if telegram_status_token else None,
            expected_identity_type=IDENTITY_PHONE,
            expected_identity_value_normalized=normalized_phone,
            status=CHALLENGE_PENDING,
            attempts_count=0,
            max_attempts=DEFAULT_CHALLENGE_MAX_ATTEMPTS,
            expires_at=current_time + timedelta(seconds=DEFAULT_CHALLENGE_TTL_SECONDS),
        )
        db.add(challenge)
        db.flush()
        if not telegram_mode:
            challenge.token_hash = _hash_registration_code(challenge.id, verification_code)
        db.commit()
        db.refresh(user)
        db.refresh(challenge)

        return _build_registration_response_v2(
            success=True,
            user=user,
            challenge=challenge,
            include_challenge_id=not telegram_mode,
            message=(
                "Local verification code returned for local test mode"
                if debug_mode
                else "Telegram confirmation link created"
            ),
            debug_verification_code=verification_code if debug_mode else None,
            telegram_confirmation_url=telegram_confirmation_url,
            telegram_status_token=telegram_status_token,
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


def _finalize_pending_registration_session(
    db,
    *,
    challenge,
    user,
    normalized_phone: str,
    current_time: datetime,
    telegram_user_id: str | None = None,
) -> dict:
    identity = _upsert_registration_identity_in_session(
        db,
        IDENTITY_PHONE,
        normalized_phone,
        first_user_id=user.id,
        verified_at=current_time,
    )

    if telegram_user_id is not None:
        _upsert_registration_identity_in_session(
            db,
            IDENTITY_TELEGRAM,
            str(telegram_user_id),
            first_user_id=user.id,
            verified_at=current_time,
        )
        user.telegram_id = str(telegram_user_id)

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
        return _finalize_pending_registration_session(
            db,
            challenge=challenge,
            user=user,
            normalized_phone=normalized_phone,
            current_time=current_time,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _get_challenge_by_status_token_in_session(db, status_token_hash: str):
    return (
        db.query(RegistrationChallengeModel)
        .filter(RegistrationChallengeModel.status_token_hash == status_token_hash)
        .first()
    )


def get_telegram_registration_status(
    *,
    status_token: str,
    now: datetime | None = None,
) -> dict:
    try:
        normalized_status_token = _normalize_opaque_token(status_token)
    except ValueError as error:
        return {
            "success": False,
            "error": str(error),
        }

    current_time = now or _utcnow()
    db = SessionLocal()

    try:
        challenge = _get_challenge_by_status_token_in_session(
            db,
            _hash_opaque_token(normalized_status_token),
        )

        if not challenge:
            return {
                "success": False,
                "error": "Registration status not found",
            }

        if challenge.expires_at and challenge.expires_at <= current_time:
            challenge.status = CHALLENGE_EXPIRED
            db.commit()
            db.refresh(challenge)

        user = (
            db.query(UserModel)
            .filter(UserModel.id == challenge.user_id)
            .first()
        )

        if not user:
            return {
                "success": False,
                "error": "Registration status not found",
            }

        return {
            "success": True,
            "challenge_status": challenge.status,
            **_build_user_status_payload(user, now=current_time),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def confirm_pending_phone_registration_via_telegram(
    *,
    payload: str,
    telegram_user_id: int,
    contact_phone: str,
    now: datetime | None = None,
) -> dict:
    try:
        normalized_payload = _normalize_opaque_token(payload)
        normalized_phone = normalize_phone_identity(contact_phone)
    except ValueError as error:
        return {
            "success": False,
            "error": str(error),
        }

    current_time = now or _utcnow()
    try:
        validate_telegram_registration_security_config()
    except TelegramRegistrationSecurityConfigError as error:
        return {
            "success": False,
            "error": str(error),
        }

    db = SessionLocal()

    try:
        challenge = _get_challenge_by_token_hash_in_session(
            db,
            _hash_opaque_token(normalized_payload),
        )

        if not challenge:
            return {
                "success": False,
                "error": "Challenge not found",
            }

        if challenge.channel != TELEGRAM_CHANNEL:
            return {
                "success": False,
                "error": "Challenge is not a Telegram challenge",
                "challenge_id": challenge.id,
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

        expected_phone = normalize_phone_identity(user.phone or challenge.expected_identity_value_normalized)
        if normalized_phone != expected_phone:
            return {
                "success": False,
                "error": "Phone number does not match pending registration",
                "challenge_id": challenge.id,
            }

        return _finalize_pending_registration_session(
            db,
            challenge=challenge,
            user=user,
            normalized_phone=normalized_phone,
            current_time=current_time,
            telegram_user_id=str(int(telegram_user_id)),
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
