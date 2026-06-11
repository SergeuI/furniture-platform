import secrets

from database.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_telegram_id,
    get_user_by_username,
    update_user_email,
    update_user_profile,
    update_user_role,
)
from services.auth_service import (
    hash_password,
)
from services.user_roles import (
    ROLE_ADMIN,
    ROLE_GUEST,
    ROLE_PRO,
    ROLE_USER,
    normalize_user_role,
)


ROLE_PRIORITY = {
    ROLE_GUEST: 0,
    ROLE_USER: 1,
    ROLE_PRO: 2,
    ROLE_ADMIN: 3,
}


def _normalize_username_seed(value: str | None, fallback: str) -> str:

    raw = (value or "").strip().lower()

    if not raw:
        return fallback

    normalized = "".join(
        character
        for character in raw
        if character.isalnum() or character in ("_", ".", "-")
    )

    return normalized[:64] or fallback


def _allocate_username(preferred: str | None, telegram_id: int) -> str:

    fallback = f"tg_{telegram_id}"
    base = _normalize_username_seed(preferred, fallback)

    if not get_user_by_username(base):
        return base

    suffix = 2

    while True:
        candidate = f"{base[:58]}_{suffix}"
        if not get_user_by_username(candidate):
            return candidate
        suffix += 1


def ensure_telegram_identity(

    telegram_id: int,

    email: str,

    display_name: str | None = None,

    phone: str | None = None,

    role: str = ROLE_GUEST,
):

    normalized_email = email.strip().lower()
    normalized_role = normalize_user_role(role)
    username_seed = normalized_email.split("@")[0] if "@" in normalized_email else display_name

    user = get_user_by_telegram_id(telegram_id)

    if user:
        if ROLE_PRIORITY.get(normalized_role, 0) > ROLE_PRIORITY.get(normalize_user_role(user.role), 0):
            user = update_user_role(user.id, normalized_role)
        if normalized_email and user.email != normalized_email:
            existing_email_user = get_user_by_email(normalized_email)
            if not existing_email_user or existing_email_user.id == user.id:
                update_user_email(user.id, normalized_email)
        return update_user_profile(
            user_id=user.id,
            phone=phone if phone is not None else user.phone,
            username=user.username or _allocate_username(username_seed, telegram_id),
            telegram_id=str(telegram_id),
        )

    user = get_user_by_email(normalized_email)

    if user:
        if ROLE_PRIORITY.get(normalized_role, 0) > ROLE_PRIORITY.get(normalize_user_role(user.role), 0):
            user = update_user_role(user.id, normalized_role)
        return update_user_profile(
            user_id=user.id,
            phone=phone if phone is not None else user.phone,
            username=user.username or _allocate_username(username_seed, telegram_id),
            telegram_id=str(telegram_id),
        )

    user = create_user(
        email=normalized_email,
        password_hash=hash_password(secrets.token_urlsafe(24)),
        role=normalized_role,
    )

    return update_user_profile(
        user_id=user.id,
        phone=phone,
        username=user.username or _allocate_username(username_seed, telegram_id),
        telegram_id=str(telegram_id),
    )
