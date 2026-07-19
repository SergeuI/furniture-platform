from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func

from database.base import Base


class RegistrationIdentityModel(Base):

    __tablename__ = "registration_identities"

    __table_args__ = (
        UniqueConstraint(
            "identity_type",
            "identity_value_normalized",
            name="uq_registration_identities_type_value",
        ),
        Index(
            "ix_registration_identities_identity_type",
            "identity_type",
        ),
        Index(
            "ix_registration_identities_identity_value_normalized",
            "identity_value_normalized",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    identity_type = Column(
        String,
        nullable=False,
    )

    identity_value_normalized = Column(
        String,
        nullable=False,
    )

    first_user_id = Column(
        String,
        nullable=True,
        index=True,
    )

    verified_at = Column(
        DateTime,
        nullable=True,
    )

    trial_used_at = Column(
        DateTime,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class RegistrationChallengeModel(Base):

    __tablename__ = "registration_challenges"

    __table_args__ = (
        UniqueConstraint(
            "token_hash",
            name="uq_registration_challenges_token_hash",
        ),
        Index(
            "ix_registration_challenges_user_id",
            "user_id",
        ),
        Index(
            "ix_registration_challenges_status",
            "status",
        ),
        Index(
            "ix_registration_challenges_expires_at",
            "expires_at",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id = Column(
        String,
        nullable=True,
    )

    channel = Column(
        String,
        nullable=False,
    )

    token_hash = Column(
        String(64),
        nullable=False,
        unique=True,
    )

    expected_identity_type = Column(
        String,
        nullable=False,
    )

    expected_identity_value_normalized = Column(
        String,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="pending",
    )

    attempts_count = Column(
        Integer,
        nullable=False,
        default=0,
    )

    max_attempts = Column(
        Integer,
        nullable=False,
        default=5,
    )

    expires_at = Column(
        DateTime,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    verified_at = Column(
        DateTime,
        nullable=True,
    )

    consumed_at = Column(
        DateTime,
        nullable=True,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
