import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    String
)

from database.base import Base


# =====================================================
# USER MODEL
# =====================================================

class UserModel(Base):

    __tablename__ = "users"

    id = Column(

        String,

        primary_key=True,

        default=lambda: str(uuid.uuid4())
    )

    email = Column(

        String,

        unique=True,

        index=True,

        nullable=False
    )

    username = Column(

        String,

        unique=True,

        index=True,

        nullable=True
    )

    phone = Column(

        String,

        nullable=True
    )

    city = Column(

        String,

        nullable=True
    )

    telegram_id = Column(

        String,

        unique=True,

        index=True,

        nullable=True
    )

    password_hash = Column(

        String,

        nullable=False
    )

    role = Column(

        String,

        nullable=False,

        default="free"
    )

    is_active = Column(

        Boolean,

        nullable=False,

        default=True
    )

    last_username_change_at = Column(

        DateTime,

        nullable=True
    )

    viyar_email = Column(

        String,

        nullable=True
    )

    viyar_password_secret = Column(

        String,

        nullable=True
    )

    viyar_cookie = Column(

        String,

        nullable=True
    )

    viyar_cookie_updated_at = Column(

        DateTime,

        nullable=True
    )

    viyar_last_auth_at = Column(

        DateTime,

        nullable=True
    )

    viyar_last_auth_status = Column(

        String,

        nullable=True
    )

    viyar_last_auth_error = Column(

        String,

        nullable=True
    )
