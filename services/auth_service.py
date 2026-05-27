import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from database.repositories.user_repository import (
    count_users,
    create_user,
    get_user_by_email,
    get_user_by_id
)


PASSWORD_HASH_ITERATIONS = 260000

TOKEN_TTL_SECONDS = 60 * 60 * 24

TOKEN_SECRET = os.getenv(

    "AUTH_SECRET_KEY",

    "furniture-platform-local-dev-secret"
)


# =====================================================
# PASSWORD HASHING
# =====================================================

def hash_password(

    password: str
) -> str:

    salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(

        "sha256",

        password.encode("utf-8"),

        salt.encode("utf-8"),

        PASSWORD_HASH_ITERATIONS
    ).hex()

    return (
        f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${password_hash}"
    )


def verify_password(

    password: str,

    password_hash: str
) -> bool:

    try:

        algorithm, iterations, salt, expected_hash = (
            password_hash.split("$")
        )

    except ValueError:

        return False

    if algorithm != "pbkdf2_sha256":

        return False

    candidate_hash = hashlib.pbkdf2_hmac(

        "sha256",

        password.encode("utf-8"),

        salt.encode("utf-8"),

        int(iterations)
    ).hex()

    return hmac.compare_digest(

        candidate_hash,

        expected_hash
    )


# =====================================================
# TOKEN SERVICE
# =====================================================

def _base64url_encode(

    data: bytes
) -> str:

    return (

        base64.urlsafe_b64encode(data)

        .decode("utf-8")

        .rstrip("=")
    )


def _base64url_decode(

    data: str
) -> bytes:

    padding = "=" * (-len(data) % 4)

    return base64.urlsafe_b64decode(
        data + padding
    )


def create_access_token(

    user_id: str,

    role: str
) -> str:

    payload = {

        "sub": user_id,

        "role": role,

        "exp": int(time.time()) + TOKEN_TTL_SECONDS
    }

    payload_part = _base64url_encode(

        json.dumps(

            payload,

            separators=(",", ":")
        ).encode("utf-8")
    )

    signature = hmac.new(

        TOKEN_SECRET.encode("utf-8"),

        payload_part.encode("utf-8"),

        hashlib.sha256
    ).digest()

    signature_part = _base64url_encode(
        signature
    )

    return f"{payload_part}.{signature_part}"


def decode_access_token(

    token: str
) -> dict | None:

    try:

        payload_part, signature_part = token.split(".")

    except ValueError:

        return None

    expected_signature = hmac.new(

        TOKEN_SECRET.encode("utf-8"),

        payload_part.encode("utf-8"),

        hashlib.sha256
    ).digest()

    received_signature = _base64url_decode(
        signature_part
    )

    if not hmac.compare_digest(

        expected_signature,

        received_signature
    ):

        return None

    payload = json.loads(
        _base64url_decode(payload_part)
    )

    if payload.get("exp", 0) < int(time.time()):

        return None

    return payload


# =====================================================
# AUTH OPERATIONS
# =====================================================

def register_user(

    email: str,

    password: str
):

    normalized_email = email.strip().lower()

    if count_users() > 0:

        return None

    if get_user_by_email(
        normalized_email
    ):

        return None

    role = "admin" if count_users() == 0 else "manager"

    return create_user(

        email=normalized_email,

        password_hash=hash_password(
            password
        ),

        role=role
    )


def create_managed_user(

    email: str,

    password: str,

    role: str
):

    normalized_email = email.strip().lower()

    if get_user_by_email(
        normalized_email
    ):

        return None

    return create_user(

        email=normalized_email,

        password_hash=hash_password(
            password
        ),

        role=role
    )


def authenticate_user(

    email: str,

    password: str
):

    user = get_user_by_email(
        email.strip().lower()
    )

    if not user:

        return None

    if not user.is_active:

        return None

    if not verify_password(

        password,

        user.password_hash
    ):

        return None

    return user


def get_user_from_token(

    token: str
):

    payload = decode_access_token(
        token
    )

    if not payload:

        return None

    user = get_user_by_id(
        payload.get("sub")
    )

    if not user:

        return None

    if not user.is_active:

        return None

    return user
