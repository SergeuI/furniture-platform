from fastapi import (
    Header,
    HTTPException,
    status
)

from services.auth_service import (
    get_user_from_token
)


# =====================================================
# BEARER TOKEN
# =====================================================

def _extract_bearer_token(

    authorization: str | None
) -> str | None:

    if not authorization:

        return None

    token_type, _, token = authorization.partition(" ")

    if token_type.lower() != "bearer":

        return None

    if not token:

        return None

    return token


# =====================================================
# CURRENT USER DEPENDENCY
# =====================================================

def require_current_user(

    authorization: str | None = Header(default=None)
):

    token = _extract_bearer_token(
        authorization
    )

    if not token:

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail={

                "success": False,

                "error": "Missing bearer token"
            }
        )

    user = get_user_from_token(
        token
    )

    if not user:

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail={

                "success": False,

                "error": "Invalid or expired token"
            }
        )

    return user
