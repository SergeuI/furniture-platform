from pydantic import (
    BaseModel,
    Field
)
from datetime import datetime
from typing import List
from typing import Optional


# =====================================================
# AUTH REQUESTS
# =====================================================

class RegisterUserSchema(BaseModel):

    email: str = Field(

        min_length=3,

        max_length=255
    )

    password: str = Field(

        min_length=8,

        max_length=128
    )


class LoginUserSchema(BaseModel):

    email: str = Field(

        min_length=3,

        max_length=255
    )

    password: str = Field(

        min_length=8,

        max_length=128
    )


class CreateUserSchema(BaseModel):

    email: str = Field(

        min_length=3,

        max_length=255
    )

    password: str = Field(

        min_length=8,

        max_length=128
    )

    role: str = Field(

        min_length=3,

        max_length=32
    )


class ChangeOwnPasswordSchema(BaseModel):

    current_password: str = Field(

        min_length=8,

        max_length=128
    )

    new_password: str = Field(

        min_length=8,

        max_length=128
    )


class ResetUserPasswordSchema(BaseModel):

    password: str = Field(

        min_length=8,

        max_length=128
    )


class PasswordResetRequestSchema(BaseModel):

    email: str = Field(

        min_length=3,

        max_length=255
    )


class UpdateUserRoleSchema(BaseModel):

    role: str = Field(

        min_length=3,

        max_length=32
    )


class UpdateUserActiveSchema(BaseModel):

    is_active: bool


class UpdateOwnViyarAuthSchema(BaseModel):

    email: str = Field(

        min_length=3,

        max_length=255
    )

    password: str | None = Field(

        default=None,

        min_length=8,

        max_length=255
    )


class UpdateOwnProfileSchema(BaseModel):

    phone: str | None = Field(
        default=None,
        min_length=3,
        max_length=64
    )

    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=64
    )

    city: str | None = Field(
        default=None,
        min_length=2,
        max_length=64
    )


class CreateEmailChangeRequestSchema(BaseModel):

    new_email: str = Field(
        min_length=3,
        max_length=255
    )


class ReviewUserChangeRequestSchema(BaseModel):

    status: str = Field(
        min_length=8,
        max_length=16
    )


class RegistrationStartRequestSchema(BaseModel):

    name: str | None = Field(
        default=None,
        min_length=3,
        max_length=64
    )

    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=64
    )

    email: str = Field(
        min_length=3,
        max_length=255
    )

    password: str = Field(
        min_length=8,
        max_length=128
    )

    phone: str = Field(
        min_length=3,
        max_length=64
    )


class RegistrationStartResponseSchema(BaseModel):

    success: bool

    challenge_id: int | None = None

    challenge_status: str | None = None

    registration_status: str | None = None

    phone_verified: bool = False

    trial_granted: bool = False

    effective_plan: str = "free"

    trial_ends_at: datetime | None = None

    message: str | None = None

    debug_verification_code: str | None = None

    telegram_confirmation_url: str | None = None

    telegram_status_token: str | None = None

    error: str | None = None


class RegistrationConfirmRequestSchema(BaseModel):

    challenge_id: int = Field(
        gt=0
    )

    code: str = Field(
        min_length=1,
        max_length=32
    )


class RegistrationConfirmResponseSchema(BaseModel):

    success: bool

    challenge_id: int | None = None

    challenge_status: str | None = None

    registration_status: str | None = None

    phone_verified: bool = False

    trial_granted: bool = False

    effective_plan: str = "free"

    trial_ends_at: datetime | None = None

    error: str | None = None


class RegistrationTelegramStatusRequestSchema(BaseModel):

    status_token: str = Field(
        min_length=1,
        max_length=128
    )


class RegistrationTelegramStatusResponseSchema(BaseModel):

    success: bool

    challenge_status: str | None = None

    registration_status: str | None = None

    phone_verified: bool = False

    trial_granted: bool = False

    effective_plan: str = "free"

    trial_ends_at: datetime | None = None

    error: str | None = None


# =====================================================
# AUTH RESPONSES
# =====================================================

class UserResponseSchema(BaseModel):

    id: str

    email: str

    username: str | None = None

    phone: str | None = None

    city: str | None = None

    telegram_id: str | None = None

    role: str

    effective_plan: str = "free"

    is_trial_active: bool = False

    trial_started_at: datetime | None = None

    trial_ends_at: datetime | None = None

    trial_seconds_remaining: int = 0

    is_active: bool

    last_username_change_at: datetime | None = None

    viyar_email: str | None = None

    viyar_has_password: bool = False

    viyar_has_cookie: bool = False

    viyar_last_auth_at: datetime | None = None

    viyar_last_auth_status: str | None = None

    viyar_last_auth_error: str | None = None


class AuthResponseSchema(BaseModel):

    success: bool

    access_token: Optional[str] = None

    token_type: Optional[str] = None

    user: Optional[UserResponseSchema] = None

    error: Optional[str] = None


class CurrentUserResponseSchema(BaseModel):

    success: bool

    user: Optional[UserResponseSchema] = None

    error: Optional[str] = None


class UserListResponseSchema(BaseModel):

    success: bool

    total: int

    limit: int

    offset: int

    users: List[UserResponseSchema]


class UserOperationResponseSchema(BaseModel):

    success: bool

    user: Optional[UserResponseSchema] = None

    error: Optional[str] = None


class ViyarAuthStatusSchema(BaseModel):

    email: str | None = None

    has_password: bool

    has_cookie: bool

    cookie_updated_at: datetime | None = None

    last_auth_at: datetime | None = None

    last_auth_status: str | None = None

    last_auth_error: str | None = None


class ViyarAuthResponseSchema(BaseModel):

    success: bool

    viyar: ViyarAuthStatusSchema | None = None

    error: str | None = None


class UserChangeRequestItemSchema(BaseModel):

    id: str

    user_id: str

    change_type: str

    old_value: str | None = None

    new_value: str

    status: str

    created_at: datetime | None = None

    reviewed_at: datetime | None = None

    reviewed_by_user_id: str | None = None


class UserChangeRequestResponseSchema(BaseModel):

    success: bool

    request: UserChangeRequestItemSchema | None = None

    error: str | None = None


class UserChangeRequestListResponseSchema(BaseModel):

    success: bool

    limit: int | None = None

    offset: int | None = None

    requests: List[UserChangeRequestItemSchema]


class AdminUserProjectSummarySchema(BaseModel):

    id: str

    project_name: str | None = None

    project_type: str | None = None

    client_name: str | None = None

    room_name: str | None = None

    created_at: datetime | None = None

    updated_at: datetime | None = None


class AdminUserDetailsSchema(BaseModel):

    user: UserResponseSchema

    change_requests: List[UserChangeRequestItemSchema]

    projects: List[AdminUserProjectSummarySchema]


class AdminUserDetailsResponseSchema(BaseModel):

    success: bool

    details: AdminUserDetailsSchema | None = None

    error: str | None = None
