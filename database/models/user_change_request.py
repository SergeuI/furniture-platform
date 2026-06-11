import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
)

from database.base import Base


class UserChangeRequestModel(Base):

    __tablename__ = "user_change_requests"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    change_type = Column(
        String,
        nullable=False,
        index=True,
    )

    old_value = Column(
        String,
        nullable=True,
    )

    new_value = Column(
        String,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="pending",
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=True,
    )

    reviewed_at = Column(
        DateTime,
        nullable=True,
    )

    reviewed_by_user_id = Column(
        String,
        nullable=True,
    )
