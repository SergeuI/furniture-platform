from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func

from database.base import Base


ALLOWED_ENTITLEMENT_VALUE_TYPES = (
    "boolean",
    "integer",
    "decimal",
    "text",
    "enum",
)


class EntitlementFeatureModel(Base):

    __tablename__ = "entitlement_features"

    __table_args__ = (
        UniqueConstraint(
            "feature_key",
            name="uq_entitlement_features_feature_key",
        ),
        CheckConstraint(
            "trim(feature_key) <> ''",
            name="ck_entitlement_features_feature_key_not_blank",
        ),
        CheckConstraint(
            "trim(name_uk) <> ''",
            name="ck_entitlement_features_name_uk_not_blank",
        ),
        CheckConstraint(
            "trim(category) <> ''",
            name="ck_entitlement_features_category_not_blank",
        ),
        CheckConstraint(
            "value_type IN ('boolean', 'integer', 'decimal', 'text', 'enum')",
            name="ck_entitlement_features_value_type_allowed",
        ),
        Index(
            "ix_entitlement_features_category",
            "category",
        ),
        Index(
            "ix_entitlement_features_is_system",
            "is_system",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    feature_key = Column(
        String,
        nullable=False,
    )

    name_uk = Column(
        String,
        nullable=False,
    )

    description_uk = Column(
        Text,
        nullable=True,
    )

    category = Column(
        String,
        nullable=False,
    )

    value_type = Column(
        String,
        nullable=False,
    )

    enum_options_json = Column(
        JSON,
        nullable=True,
    )

    is_system = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
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
