from pydantic import (
    BaseModel,
    Field
)
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
