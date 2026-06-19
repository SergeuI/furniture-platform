ROLE_ADMIN = "admin"
ROLE_PRO = "pro"
ROLE_PREMIUM = "premium"
ROLE_FREE = "free"
ROLE_USER = ROLE_FREE
ROLE_GUEST = ROLE_FREE

LEGACY_ROLE_ALIASES = {
    "user": ROLE_FREE,
    "guest": ROLE_FREE,
    "manager": ROLE_FREE,
    "viewer": ROLE_FREE,
}

ALLOWED_USER_ROLES = [
    ROLE_ADMIN,
    ROLE_PREMIUM,
    ROLE_PRO,
    ROLE_FREE,
]


def normalize_user_role(
    role: str | None,
) -> str:

    normalized = str(role or ROLE_GUEST).strip().lower()

    return LEGACY_ROLE_ALIASES.get(
        normalized,
        normalized
    )


def normalize_allowed_roles(
    roles: list[str],
) -> list[str]:

    return [
        normalize_user_role(role)
        for role in roles
    ]
