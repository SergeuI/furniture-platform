from fastapi import (
    APIRouter,
    Depends,
    Query
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
import asyncio
import os
from datetime import datetime, timedelta

from api.dependencies.auth import (
    require_current_user,
    require_roles
)

from schemas.auth import (
    AuthResponseSchema,
    ChangeOwnPasswordSchema,
    CreateEmailChangeRequestSchema,
    CreateUserSchema,
    CurrentUserResponseSchema,
    LoginUserSchema,
    PasswordResetRequestSchema,
    RegistrationConfirmRequestSchema,
    RegistrationConfirmResponseSchema,
    RegistrationStartRequestSchema,
    RegistrationStartResponseSchema,
    RegistrationTelegramStatusRequestSchema,
    RegistrationTelegramStatusResponseSchema,
    RegisterUserSchema,
    ReviewUserChangeRequestSchema,
    AdminUserDetailsResponseSchema,
    ResetUserPasswordSchema,
    UpdateOwnProfileSchema,
    UpdateOwnViyarAuthSchema,
    UpdateUserActiveSchema,
    UpdateUserRoleSchema,
    UserChangeRequestListResponseSchema,
    UserChangeRequestResponseSchema,
    UserListResponseSchema,
    UserOperationResponseSchema,
    ViyarAuthResponseSchema
)

from database.repositories.user_repository import (
    count_users,
    get_user_by_email,
    get_user_by_id,
    list_users,
    set_user_active,
    update_user_email,
    update_user_role,
    update_user_viyar_credentials,
    update_user_viyar_session
)
from database.repositories.user_change_request_repository import (
    create_user_change_request,
    get_pending_change_request,
    get_user_change_request_by_id,
    list_user_change_requests,
    review_user_change_request,
)
from database.repositories.audit_log_repository import (
    create_audit_log
)
from database.repositories.project_repository import (
    count_projects,
    list_projects_created_by_user,
)
from database.session import SessionLocal
from database.models.audit_log import AuditLogModel
from database.models.material import MaterialModel
from database.models.fitting import FittingModel
from database.models.user import UserModel

from services.auth_service import (
    authenticate_user,
    change_user_password,
    create_access_token,
    create_managed_user,
    RegistrationLoginBlockedError,
    register_user,
    reset_user_password,
    username_is_available,
)
from services.registration_onboarding_service import (
    confirm_pending_phone_registration,
    get_telegram_registration_status,
    start_pending_phone_registration,
)
from services.credential_cipher import (
    decrypt_secret,
    encrypt_secret,
)
from services.viyar_auth_service import (
    login_viyar_and_get_cookie,
)
from services.user_roles import (
    ALLOWED_USER_ROLES,
    ROLE_USER,
    normalize_user_role,
)
from services.subscription_service import (
    build_subscription_status,
)


router = APIRouter()

LOCAL_PUBLIC_REGISTRATION_ENV = "FURNITURE_ALLOW_LOCAL_PUBLIC_REGISTRATION"

require_auth_admin = require_roles(
    [
        "admin"
    ]
)


def _serialize_user(

    user
) -> dict:

    fallback_username = user.username or user.email.split("@")[0]

    return {

        "id": user.id,

        "email": user.email,

        "username": fallback_username,

        "phone": user.phone,

        "city": user.city,

        "telegram_id": user.telegram_id,

        "role": normalize_user_role(user.role),

        "last_username_change_at": user.last_username_change_at,

        **build_subscription_status(user),

        "viyar_email": user.viyar_email,

        "viyar_has_password": bool(user.viyar_password_secret),

        "viyar_has_cookie": bool(user.viyar_cookie),

        "viyar_last_auth_at": user.viyar_last_auth_at,

        "viyar_last_auth_status": user.viyar_last_auth_status,

        "viyar_last_auth_error": user.viyar_last_auth_error,

        "is_active": user.is_active
    }


def _serialize_change_request(change_request) -> dict:

    return {
        "id": change_request.id,
        "user_id": change_request.user_id,
        "change_type": change_request.change_type,
        "old_value": change_request.old_value,
        "new_value": change_request.new_value,
        "status": change_request.status,
        "created_at": change_request.created_at,
        "reviewed_at": change_request.reviewed_at,
        "reviewed_by_user_id": change_request.reviewed_by_user_id,
    }


def _serialize_viyar_auth(user) -> dict:

    return {
        "email": user.viyar_email,
        "has_password": bool(user.viyar_password_secret),
        "has_cookie": bool(user.viyar_cookie),
        "cookie_updated_at": user.viyar_cookie_updated_at,
        "last_auth_at": user.viyar_last_auth_at,
        "last_auth_status": user.viyar_last_auth_status,
        "last_auth_error": user.viyar_last_auth_error,
    }


def _serialize_project_summary(project) -> dict:

    return {
        "id": project.id,
        "project_name": project.project_name,
        "project_type": project.project_type,
        "client_name": project.client_name,
        "room_name": project.room_name,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def _normalize_route_error(error_text: str | None, fallback: str) -> str:

    text = str(error_text or "").strip()
    return text or fallback


def _is_local_public_registration_enabled() -> bool:

    value = os.getenv(
        LOCAL_PUBLIC_REGISTRATION_ENV,
        "",
    ).strip().lower()

    return value in {"1", "true", "yes", "on"}


@router.get("/public-overview")
async def public_overview_route():

    db = SessionLocal()

    try:

        materials_total = (
            db.query(MaterialModel)
            .filter(MaterialModel.is_default.is_(True))
            .count()
        )

        fittings_total = (
            db.query(FittingModel)
            .filter(FittingModel.is_system.is_(True))
            .filter(FittingModel.is_active.is_(True))
            .count()
        )

        return {
            "success": True,
            "registration_enabled": _is_local_public_registration_enabled(),
            "stats": {
                "projects_total": count_projects(),
                "materials_total": materials_total,
                "fittings_total": fittings_total,
                "users_total": count_users(),
            },
        }

    finally:

        db.close()


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

    if not _is_local_public_registration_enabled():

        return {

            "success": False,

            "error": "Public registration is disabled"
        }

    user = register_user(

        email=payload.email,

        password=payload.password,
        role=ROLE_USER,
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


@router.post(
    "/registration/start",
    response_model=RegistrationStartResponseSchema,
)
async def registration_start_route(
    payload: RegistrationStartRequestSchema,
):
    resolved_username = payload.username if payload.username is not None else payload.name

    response = start_pending_phone_registration(
        name=payload.name,
        username=resolved_username,
        email=payload.email,
        password=payload.password,
        phone=payload.phone,
    )

    return JSONResponse(
        content=jsonable_encoder(response)
    )


@router.post(
    "/registration/confirm",
    response_model=RegistrationConfirmResponseSchema,
)
async def registration_confirm_route(
    payload: RegistrationConfirmRequestSchema,
):
    return confirm_pending_phone_registration(
        challenge_id=payload.challenge_id,
        code=payload.code,
    )


@router.post(
    "/registration/telegram/status",
    response_model=RegistrationTelegramStatusResponseSchema,
)
async def registration_telegram_status_route(
    payload: RegistrationTelegramStatusRequestSchema,
):
    return get_telegram_registration_status(
        status_token=payload.status_token,
    )


# =====================================================
# CREATE USER
# =====================================================

@router.post(
    "/users",

    response_model=UserOperationResponseSchema
)
async def create_user_route(

    payload: CreateUserSchema,

    current_user = Depends(require_auth_admin)
):

    role = normalize_user_role(payload.role)

    if role not in ALLOWED_USER_ROLES:

        return {

            "success": False,

            "error": "Invalid user role"
        }

    user = create_managed_user(

        email=payload.email,

        password=payload.password,

        role=role
    )

    if not user:

        return {

            "success": False,

            "error": "User already exists"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="user.created",

        entity_type="user",

        entity_id=user.id,

        details={

            "email": user.email,

            "role": user.role
        }
    )

    return {

        "success": True,

        "user": _serialize_user(
            user
        )
    }


@router.post("/password-reset-request")
async def password_reset_request_route(
    payload: PasswordResetRequestSchema
):

    email = payload.email.strip().lower()
    user = get_user_by_email(email)

    if user:
        pending_request = get_pending_change_request(
            user.id,
            "password_reset",
        )

        if not pending_request:
            create_user_change_request(
                user_id=user.id,
                change_type="password_reset",
                old_value=None,
                new_value="Password reset requested from public site",
            )

    return {
        "success": True,
        "message": "If this email exists, a password reset request was sent to the administrator.",
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

    try:
        user = authenticate_user(

            email=payload.email,

            password=payload.password
        )
    except RegistrationLoginBlockedError as error:
        return {
            "success": False,
            "error": str(error),
        }

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


@router.put(
    "/me/profile",

    response_model=CurrentUserResponseSchema
)
async def update_own_profile_route(

    payload: UpdateOwnProfileSchema,

    current_user = Depends(require_current_user)
):

    username = None
    mark_username_changed = False

    if payload.username is not None:
        requested_username = payload.username.strip()

        if not requested_username:
            return {
                "success": False,
                "error": "Username cannot be empty",
            }

        if requested_username != (current_user.username or ""):
            if not username_is_available(requested_username, current_user.id):
                return {
                    "success": False,
                    "error": "Username is already in use",
                }

            if (
                current_user.last_username_change_at
                and current_user.last_username_change_at > datetime.utcnow() - timedelta(days=7)
            ):
                return {
                    "success": False,
                    "error": "Username can be changed only once every 7 days",
                }

            username = requested_username
            mark_username_changed = True
        else:
            username = requested_username

    supplied_fields = payload.model_fields_set

    db = SessionLocal()

    try:
        user = (
            db.query(UserModel)
            .filter(UserModel.id == current_user.id)
            .first()
        )

        if not user:
            return {
                "success": False,
                "error": "User not found",
            }

        if "phone" in supplied_fields:
            user.phone = None if payload.phone is None else payload.phone.strip()

        if "city" in supplied_fields:
            user.city = None if payload.city is None else payload.city.strip()

        if username is not None:
            user.username = username

        if mark_username_changed:
            user.last_username_change_at = datetime.utcnow()

        db.add(
            AuditLogModel(
                actor_user_id=current_user.id,
                actor_email=current_user.email,
                action="user.profile_updated",
                entity_type="user",
                entity_id=current_user.id,
                details={
                    "phone_updated": "phone" in supplied_fields,
                    "city_updated": "city" in supplied_fields,
                    "username_updated": mark_username_changed,
                },
            )
        )

        db.commit()
        db.refresh(user)

        updated_user = user

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    return {
        "success": True,
        "user": _serialize_user(updated_user),
    }


@router.post(
    "/me/email-change-request",

    response_model=UserChangeRequestResponseSchema
)
async def create_own_email_change_request_route(

    payload: CreateEmailChangeRequestSchema,

    current_user = Depends(require_current_user)
):

    new_email = payload.new_email.strip().lower()

    if new_email == current_user.email:
        return {
            "success": False,
            "error": "New email matches the current email",
        }

    if get_user_by_email(new_email):
        return {
            "success": False,
            "error": "Email is already in use",
        }

    pending_request = get_pending_change_request(current_user.id, "email")

    if pending_request:
        return {
            "success": False,
            "error": "There is already a pending email change request",
            "request": _serialize_change_request(pending_request),
        }

    change_request = create_user_change_request(
        user_id=current_user.id,
        change_type="email",
        old_value=current_user.email,
        new_value=new_email,
    )

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="user.email_change_requested",
        entity_type="user",
        entity_id=current_user.id,
        details={
            "old_email": current_user.email,
            "new_email": new_email,
        }
    )

    return {
        "success": True,
        "request": _serialize_change_request(change_request),
    }


@router.get(
    "/me/viyar",

    response_model=ViyarAuthResponseSchema
)
async def get_own_viyar_auth_route(

    current_user = Depends(require_current_user)
):

    return {
        "success": True,
        "viyar": _serialize_viyar_auth(current_user),
    }


@router.put(
    "/me/viyar",

    response_model=ViyarAuthResponseSchema
)
async def update_own_viyar_auth_route(

    payload: UpdateOwnViyarAuthSchema,

    current_user = Depends(require_current_user)
):

    password_secret = None

    if payload.password:
        password_secret = encrypt_secret(payload.password)

    user = update_user_viyar_credentials(
        user_id=current_user.id,
        viyar_email=payload.email.strip(),
        viyar_password_secret=password_secret,
    )

    if not user:
        return {
            "success": False,
            "error": "User not found",
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="user.viyar_credentials_updated",

        entity_type="user",

        entity_id=current_user.id,

        details={
            "viyar_email": user.viyar_email,
            "password_updated": bool(payload.password),
        }
    )

    return {
        "success": True,
        "viyar": _serialize_viyar_auth(user),
    }


@router.post(
    "/me/viyar/session",

    response_model=ViyarAuthResponseSchema
)
async def refresh_own_viyar_session_route(

    current_user = Depends(require_current_user)
):

    if not current_user.viyar_email or not current_user.viyar_password_secret:
        return {
            "success": False,
            "error": "Viyar credentials are not configured",
        }

    password = decrypt_secret(current_user.viyar_password_secret)

    if not password:
        user = update_user_viyar_session(
            user_id=current_user.id,
            viyar_cookie=None,
            status="error",
            error="Stored Viyar password could not be decrypted",
        )
        return {
            "success": False,
            "error": "Stored Viyar password could not be decrypted",
            "viyar": _serialize_viyar_auth(user or current_user),
        }

    try:
        result = await asyncio.wait_for(
            login_viyar_and_get_cookie(
                email=current_user.viyar_email,
                password=password,
            ),
            timeout=40,
        )
    except asyncio.TimeoutError:
        result = {
            "success": False,
            "error": "Viyar connection timed out after 40 seconds",
        }

    if not result["success"]:
        normalized_error = _normalize_route_error(
            result.get("error"),
            "Unable to authorize in Viyar. Please check your credentials and try again.",
        )
        user = update_user_viyar_session(
            user_id=current_user.id,
            viyar_cookie=None,
            status="error",
            error=normalized_error,
        )
        return {
            "success": False,
            "error": normalized_error,
            "viyar": _serialize_viyar_auth(user or current_user),
        }

    user = update_user_viyar_session(
        user_id=current_user.id,
        viyar_cookie=result["cookie"],
        status="connected",
        error=None,
    )

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="user.viyar_session_refreshed",

        entity_type="user",

        entity_id=current_user.id,

        details={
            "viyar_email": current_user.viyar_email,
            "status": "connected",
        }
    )

    return {
        "success": True,
        "viyar": _serialize_viyar_auth(user or current_user),
    }


# =====================================================
# CHANGE OWN PASSWORD
# =====================================================

@router.put(
    "/me/password",

    response_model=UserOperationResponseSchema
)
async def change_own_password_route(

    payload: ChangeOwnPasswordSchema,

    current_user = Depends(require_current_user)
):

    user = change_user_password(

        user_id=current_user.id,

        current_password=payload.current_password,

        new_password=payload.new_password
    )

    if not user:

        return {

            "success": False,

            "error": "Invalid current password"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="user.password_changed",

        entity_type="user",

        entity_id=current_user.id,

        details={

            "email": current_user.email
        }
    )

    return {

        "success": True,

        "user": _serialize_user(
            user
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


@router.get(
    "/users/{user_id}",

    response_model=AdminUserDetailsResponseSchema
)
async def get_user_details_route(

    user_id: str,

    current_user = Depends(require_auth_admin)
):

    user = get_user_by_id(user_id)

    if not user:
        return {
            "success": False,
            "error": "User not found",
        }

    change_requests = [
        request
        for request in list_user_change_requests()
        if request.user_id == user_id
    ]

    projects = list_projects_created_by_user(user_id, 20)

    return {
        "success": True,
        "details": {
            "user": _serialize_user(user),
            "change_requests": [
                _serialize_change_request(change_request)
                for change_request in change_requests
            ],
            "projects": [
                _serialize_project_summary(project)
                for project in projects
            ],
        },
    }


@router.get(
    "/change-requests",

    response_model=UserChangeRequestListResponseSchema
)
async def list_user_change_requests_route(

    limit: int = Query(default=50, ge=1, le=100),

    offset: int = Query(default=0, ge=0),

    status: str | None = Query(default=None),

    current_user = Depends(require_auth_admin)
):

    change_requests = list_user_change_requests(
        limit=limit,
        offset=offset,
        status=status,
    )

    return {
        "success": True,
        "limit": limit,
        "offset": offset,
        "requests": [
            _serialize_change_request(change_request)
            for change_request in change_requests
        ],
    }


@router.post(
    "/change-requests/{request_id}/review",

    response_model=UserChangeRequestResponseSchema
)
async def review_user_change_request_route(

    request_id: str,

    payload: ReviewUserChangeRequestSchema,

    current_user = Depends(require_auth_admin)
):

    change_request = get_user_change_request_by_id(request_id)

    if not change_request:
        return {
            "success": False,
            "error": "Change request not found",
        }

    if change_request.status != "pending":
        return {
            "success": False,
            "error": "Change request has already been reviewed",
            "request": _serialize_change_request(change_request),
        }

    decision = payload.status.strip().lower()

    if decision not in ("approved", "rejected"):
        return {
            "success": False,
            "error": "Invalid review status",
        }

    if decision == "approved" and change_request.change_type == "email":
        existing_email_owner = get_user_by_email(change_request.new_value)
        if existing_email_owner and existing_email_owner.id != change_request.user_id:
            return {
                "success": False,
                "error": "Email is already in use",
            }
        update_user_email(change_request.user_id, change_request.new_value)

    reviewed_request = review_user_change_request(
        request_id=request_id,
        status=decision,
        reviewed_by_user_id=current_user.id,
    )

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="user.change_request_reviewed",
        entity_type="user_change_request",
        entity_id=request_id,
        details={
            "status": decision,
            "change_type": change_request.change_type,
            "target_user_id": change_request.user_id,
        }
    )

    return {
        "success": True,
        "request": _serialize_change_request(reviewed_request or change_request),
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

    role = normalize_user_role(payload.role)

    if role not in ALLOWED_USER_ROLES:

        return {

            "success": False,

            "error": "Invalid user role"
        }

    if user_id == current_user.id:

        return {

            "success": False,

            "error": "Current user role cannot be changed"
        }

    existing_user = get_user_by_id(

        user_id
    )

    if not existing_user:

        return {

            "success": False,

            "error": "User not found"
        }

    previous_role = existing_user.role

    user = update_user_role(

        user_id=user_id,

        role=role
    )

    if not user:

        return {

            "success": False,

            "error": "User not found"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="user.role_updated",

        entity_type="user",

        entity_id=user.id,

        details={

            "email": user.email,

            "previous_role": previous_role,

            "new_role": user.role
        }
    )

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

    if user_id == current_user.id:

        return {

            "success": False,

            "error": "Current user access cannot be changed"
        }

    existing_user = get_user_by_id(

        user_id
    )

    if not existing_user:

        return {

            "success": False,

            "error": "User not found"
        }

    previous_is_active = existing_user.is_active

    user = set_user_active(

        user_id=user_id,

        is_active=payload.is_active
    )

    if not user:

        return {

            "success": False,

            "error": "User not found"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="user.access_updated",

        entity_type="user",

        entity_id=user.id,

        details={

            "email": user.email,

            "previous_is_active": previous_is_active,

            "new_is_active": user.is_active
        }
    )

    return {

        "success": True,

        "user": _serialize_user(
            user
        )
    }


# =====================================================
# RESET USER PASSWORD
# =====================================================

@router.put(
    "/users/{user_id}/password",

    response_model=UserOperationResponseSchema
)
async def reset_user_password_route(

    user_id: str,

    payload: ResetUserPasswordSchema,

    current_user = Depends(require_auth_admin)
):

    if user_id == current_user.id:

        return {

            "success": False,

            "error": "Use own password change endpoint"
        }

    existing_user = get_user_by_id(

        user_id
    )

    if not existing_user:

        return {

            "success": False,

            "error": "User not found"
        }

    user = reset_user_password(

        user_id=user_id,

        new_password=payload.password
    )

    if not user:

        return {

            "success": False,

            "error": "User not found"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="user.password_reset",

        entity_type="user",

        entity_id=user.id,

        details={

            "email": user.email
        }
    )

    return {

        "success": True,

        "user": _serialize_user(
            user
        )
    }
