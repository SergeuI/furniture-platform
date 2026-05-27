from fastapi import (
    APIRouter,
    Header
)

from schemas.auth import (
    AuthResponseSchema,
    CurrentUserResponseSchema,
    LoginUserSchema,
    RegisterUserSchema
)

from services.auth_service import (
    authenticate_user,
    create_access_token,
    get_user_from_token,
    register_user
)


router = APIRouter()


def _serialize_user(

    user
) -> dict:

    return {

        "id": user.id,

        "email": user.email,

        "role": user.role,

        "is_active": user.is_active
    }


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
# REGISTER
# =====================================================

@router.post(
    "/register",

    response_model=AuthResponseSchema
)
async def register_route(

    payload: RegisterUserSchema
):

    user = register_user(

        email=payload.email,

        password=payload.password
    )

    if not user:

        return {

            "success": False,

            "error": "User already exists"
        }

    access_token = create_access_token(

        user_id=user.id,

        role=user.role
    )

    return {

        "success": True,

        "access_token": access_token,

        "token_type": "bearer",

        "user": _serialize_user(
            user
        )
    }


# =====================================================
# LOGIN
# =====================================================

@router.post(
    "/login",

    response_model=AuthResponseSchema
)
async def login_route(

    payload: LoginUserSchema
):

    user = authenticate_user(

        email=payload.email,

        password=payload.password
    )

    if not user:

        return {

            "success": False,

            "error": "Invalid email or password"
        }

    access_token = create_access_token(

        user_id=user.id,

        role=user.role
    )

    return {

        "success": True,

        "access_token": access_token,

        "token_type": "bearer",

        "user": _serialize_user(
            user
        )
    }


# =====================================================
# CURRENT USER
# =====================================================

@router.get(
    "/me",

    response_model=CurrentUserResponseSchema
)
async def me_route(

    authorization: str | None = Header(default=None)
):

    token = _extract_bearer_token(
        authorization
    )

    if not token:

        return {

            "success": False,

            "error": "Missing bearer token"
        }

    user = get_user_from_token(
        token
    )

    if not user:

        return {

            "success": False,

            "error": "Invalid or expired token"
        }

    return {

        "success": True,

        "user": _serialize_user(
            user
        )
    }
