from pydantic import (
    BaseModel,
    Field
)
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


class UpdateUserRoleSchema(BaseModel):

    role: str = Field(

        min_length=3,

        max_length=32
    )


class UpdateUserActiveSchema(BaseModel):

    is_active: bool


# =====================================================
# AUTH RESPONSES
# =====================================================

class UserResponseSchema(BaseModel):

    id: str

    email: str

    role: str

    is_active: bool


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
