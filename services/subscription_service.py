from __future__ import annotations

from datetime import datetime, timedelta

from services.user_roles import (
    ROLE_ADMIN,
    ROLE_FREE,
    ROLE_PREMIUM,
    ROLE_PRO,
    normalize_user_role,
)


TRIAL_DURATION_DAYS = 7
TRIAL_DURATION = timedelta(days=TRIAL_DURATION_DAYS)
PAID_FEATURE_ROLES = {
    ROLE_PREMIUM,
    ROLE_PRO,
    ROLE_ADMIN,
}


def _utcnow() -> datetime:
    return datetime.utcnow()


def build_trial_window(
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    started_at = now or _utcnow()
    return started_at, started_at + TRIAL_DURATION


def should_grant_trial_on_create(
    role: str | None,
) -> bool:
    return normalize_user_role(role) == ROLE_FREE


def is_trial_active(
    user,
    now: datetime | None = None,
) -> bool:
    started_at = getattr(user, "trial_started_at", None)
    ends_at = getattr(user, "trial_ends_at", None)

    if not started_at or not ends_at:
        return False

    current_time = now or _utcnow()
    return started_at <= current_time < ends_at


def trial_seconds_remaining(
    user,
    now: datetime | None = None,
) -> int:
    if not is_trial_active(user, now=now):
        return 0

    ends_at = getattr(user, "trial_ends_at", None)
    current_time = now or _utcnow()

    if not ends_at:
        return 0

    return max(0, int((ends_at - current_time).total_seconds()))


def get_effective_plan(
    user,
    now: datetime | None = None,
) -> str:
    role = normalize_user_role(getattr(user, "role", None))

    if role in PAID_FEATURE_ROLES:
        return role

    if is_trial_active(user, now=now):
        return "trial"

    return ROLE_FREE


def has_paid_feature_access(
    user,
    now: datetime | None = None,
) -> bool:
    role = normalize_user_role(getattr(user, "role", None))
    return role in PAID_FEATURE_ROLES or is_trial_active(user, now=now)


def has_required_role_access(
    user,
    allowed_roles: list[str],
    now: datetime | None = None,
) -> bool:
    normalized_allowed_roles = {
        normalize_user_role(role)
        for role in allowed_roles
    }
    current_role = normalize_user_role(getattr(user, "role", None))

    if current_role in normalized_allowed_roles:
        return True

    if is_trial_active(user, now=now) and any(role != ROLE_ADMIN for role in normalized_allowed_roles):
        return True

    return False


def build_subscription_status(
    user,
    now: datetime | None = None,
) -> dict:
    effective_plan = get_effective_plan(user, now=now)
    trial_active = is_trial_active(user, now=now)

    return {
        "effective_plan": effective_plan,
        "is_trial_active": trial_active,
        "trial_started_at": getattr(user, "trial_started_at", None),
        "trial_ends_at": getattr(user, "trial_ends_at", None),
        "trial_seconds_remaining": trial_seconds_remaining(user, now=now),
    }
