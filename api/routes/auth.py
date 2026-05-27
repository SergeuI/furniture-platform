from fastapi import (
    APIRouter,
    Depends,
    Query
)

from api.dependencies.auth import (
    require_current_user,
    require_roles
)

from schemas.auth import (
    AuthResponseSchema,
    CurrentUserResponseSchema,
    LoginUserSchema,
    RegisterUserSchema,
    UpdateUserActiveSchema,
    UpdateUserRoleSchema,
    UserListResponseSchema,
    UserOperationResponseSchema
)

from database.repositories.user_repository import (
    count_users,
    list_users,
    set_user_active,
    update_user_role
)

from services.auth_service import (
    authenticate_user,
    create_access_token,
    register_user
)


router = APIRouter()

ALLOWED_USER_ROLES = [
    "admin",
    "manager",
    "viewer"
]

require_auth_admin = require_roles(
    [
        "admin"
    ]
)


def _serialize_user(

    user
) -> dict:

    return {

        "id": user.id,

        "email": user.email,

        "role": user.role,

        "is_active": user.is_active
    }


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

    current_user = Depends(require_current_user)
):

    return {

        "success": True,

        "user": _serialize_user(
            current_user
        )
    }


# =====================================================
# LIST USERS
# =====================================================

@router.get(
    "/users",

    response_model=UserListResponseSchema
)
async def list_users_route(

    limit: int = Query(

        default=50,

        ge=1,

        le=100
    ),

    offset: int = Query(

        default=0,

        ge=0
    ),

    current_user = Depends(require_auth_admin)
):

    users = list_users(

        limit=limit,

        offset=offset
    )

    return {

        "success": True,

        "total": count_users(),

        "limit": limit,

        "offset": offset,

        "users": [

            _serialize_user(
                user
            )

            for user in users
        ]
    }


# =====================================================
# UPDATE USER ROLE
# =====================================================

@router.put(
    "/users/{user_id}/role",

    response_model=UserOperationResponseSchema
)
async def update_user_role_route(

    user_id: str,

    payload: UpdateUserRoleSchema,

    current_user = Depends(require_auth_admin)
):

    role = payload.role.strip().lower()

    if role not in ALLOWED_USER_ROLES:

        return {

            "success": False,

            "error": "Invalid user role"
        }

    user = update_user_role(

        user_id=user_id,

        role=role
    )

    if not user:

        return {

            "success": False,

            "error": "User not found"
        }

    return {

        "success": True,

        "user": _serialize_user(
            user
        )
    }


# =====================================================
# UPDATE USER ACTIVE
# =====================================================

@router.put(
    "/users/{user_id}/active",

    response_model=UserOperationResponseSchema
)
async def update_user_active_route(

    user_id: str,

    payload: UpdateUserActiveSchema,

    current_user = Depends(require_auth_admin)
):

    user = set_user_active(

        user_id=user_id,

        is_active=payload.is_active
    )

    if not user:

        return {

            "success": False,

            "error": "User not found"
        }

    return {

        "success": True,

        "user": _serialize_user(
            user
        )
    }
