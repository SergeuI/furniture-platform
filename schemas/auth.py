from pydantic import (
    BaseModel,
    Field
)


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

    access_token: str

    token_type: str = "bearer"

    user: UserResponseSchema
