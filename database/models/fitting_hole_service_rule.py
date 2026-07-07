from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base
from database.models.service_catalog_item import ServiceCatalogItemModel


class FittingHoleServiceRuleModel(Base):

    __tablename__ = "fitting_hole_service_rules"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    operation = Column(
        String,
        index=True,
        nullable=False,
    )

    diameter_min_mm = Column(
        Float,
        nullable=True,
    )

    diameter_max_mm = Column(
        Float,
        nullable=True,
    )

    depth_min_mm = Column(
        Float,
        nullable=True,
    )

    depth_max_mm = Column(
        Float,
        nullable=True,
    )

    service_catalog_item_id = Column(
        String,
        ForeignKey("service_catalog_items.id"),
        index=True,
        nullable=False,
    )

    source = Column(
        String,
        nullable=True,
    )

    city = Column(
        String,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    priority = Column(
        Integer,
        nullable=False,
        default=0,
    )

    notes = Column(
        Text,
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

    service_catalog_item = relationship(
        ServiceCatalogItemModel,
    )
