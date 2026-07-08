from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base
from database.models.service_catalog_item import ServiceCatalogItemModel


class ServiceDrillingRuleModel(Base):
    __tablename__ = "service_drilling_rules"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    service_catalog_item_id = Column(
        String,
        ForeignKey("service_catalog_items.id"),
        index=True,
        nullable=False,
    )

    rule_name = Column(
        String,
        nullable=False,
    )

    operation_type = Column(
        String,
        index=True,
        nullable=False,
    )

    hole_type = Column(
        String,
        index=True,
        nullable=False,
    )

    allowed_diameters = Column(
        JSON,
        nullable=False,
        default=list,
    )

    allowed_depths = Column(
        JSON,
        nullable=False,
        default=list,
    )

    material_thickness_min = Column(
        Float,
        nullable=True,
    )

    material_thickness_max = Column(
        Float,
        nullable=True,
    )

    max_blind_depth_formula = Column(
        String,
        nullable=True,
    )

    max_blind_depth_mm = Column(
        Float,
        nullable=True,
    )

    min_edge_offset_mm = Column(
        Float,
        nullable=True,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    source = Column(
        String,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
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
