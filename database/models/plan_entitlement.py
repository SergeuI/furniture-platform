from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from database.base import Base


ALLOWED_PLAN_CODES = (
    "trial",
    "free",
    "pro",
    "business",
)


class PlanEntitlementModel(Base):

    __tablename__ = "plan_entitlements"

    __table_args__ = (
        UniqueConstraint(
            "feature_id",
            "plan_code",
            name="uq_plan_entitlements_feature_id_plan_code",
        ),
        CheckConstraint(
            "trim(plan_code) <> ''",
            name="ck_plan_entitlements_plan_code_not_blank",
        ),
        CheckConstraint(
            "plan_code IN ('trial', 'free', 'pro', 'business')",
            name="ck_plan_entitlements_plan_code_allowed",
        ),
        CheckConstraint(
            "NOT (is_unlimited AND is_not_applicable)",
            name="ck_plan_entitlements_flags_not_both_true",
        ),
        Index(
            "ix_plan_entitlements_feature_id",
            "feature_id",
        ),
        Index(
            "ix_plan_entitlements_plan_code",
            "plan_code",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    feature_id = Column(
        Integer,
        ForeignKey("entitlement_features.id"),
        nullable=False,
    )

    plan_code = Column(
        String,
        nullable=False,
    )

    bool_value = Column(
        Boolean,
        nullable=True,
    )

    integer_value = Column(
        Integer,
        nullable=True,
    )

    decimal_value = Column(
        Numeric,
        nullable=True,
    )

    text_value = Column(
        Text,
        nullable=True,
    )

    is_unlimited = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_not_applicable = Column(
        Boolean,
        nullable=False,
        default=False,
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
