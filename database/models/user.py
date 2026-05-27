import uuid

from sqlalchemy import (
    Boolean,
    Column,
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

    password_hash = Column(

        String,

        nullable=False
    )

    role = Column(

        String,

        nullable=False,

        default="manager"
    )

    is_active = Column(

        Boolean,

        nullable=False,

        default=True
    )
