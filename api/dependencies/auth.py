from fastapi import (
    Depends,
    HTTPException,
    status
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer
)

from services.auth_service import (
    get_user_from_token
)


# =====================================================
# HTTP BEARER SECURITY
# =====================================================

bearer_scheme = HTTPBearer(
    auto_error=False
)


# =====================================================
# CURRENT USER DEPENDENCY
# =====================================================

def require_current_user(

    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    )
):

    if not credentials:

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail={

                "success": False,

                "error": "Missing bearer token"
            }
        )

    token = credentials.credentials

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


# =====================================================
# OPTIONAL CURRENT USER DEPENDENCY
# =====================================================

def optional_current_user(

    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    )
):

    if not credentials:

        return None

    token = credentials.credentials

    return get_user_from_token(
        token
    )


# =====================================================
# ROLE DEPENDENCY
# =====================================================

def require_roles(

    allowed_roles: list[str]
):

    def dependency(

        current_user = Depends(require_current_user)
    ):

        if current_user.role not in allowed_roles:

            raise HTTPException(

                status_code=status.HTTP_403_FORBIDDEN,

                detail={

                    "success": False,

                    "error": "Insufficient permissions"
                }
            )

        return current_user

    return dependency
