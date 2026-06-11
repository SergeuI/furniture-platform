ROLE_ADMIN = "admin"
ROLE_PRO = "pro"
ROLE_USER = "user"
ROLE_GUEST = "guest"

LEGACY_ROLE_ALIASES = {
    "manager": ROLE_USER,
    "viewer": ROLE_GUEST,
}

ALLOWED_USER_ROLES = [
    ROLE_ADMIN,
    ROLE_PRO,
    ROLE_USER,
    ROLE_GUEST,
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
