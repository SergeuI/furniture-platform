from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base
from database.models.service_catalog_item import ServiceCatalogItemModel
from database.models.service_drilling_rule import ServiceDrillingRuleModel


class HoleLibraryTypeModel(Base):
    __tablename__ = "hole_library_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_hole_library_types_code"),
        Index("ix_hole_library_types_name", "name"),
        Index("ix_hole_library_types_owner_user_id", "owner_user_id"),
        Index("ix_hole_library_types_is_system", "is_system"),
        Index("ix_hole_library_types_operation_type", "operation_type"),
        Index("ix_hole_library_types_surface_type", "surface_type"),
        Index("ix_hole_library_types_is_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(128), nullable=False)
    name = Column(String(255), nullable=False)
    owner_user_id = Column(String, nullable=True)
    is_system = Column(Boolean, nullable=False, default=True)
    operation_type = Column(String(64), nullable=False)
    surface_type = Column(String(32), nullable=False)
    diameter_mm = Column(Float, nullable=True)
    depth_mode = Column(String(32), nullable=False)
    fixed_depth_mm = Column(Float, nullable=True)
    min_depth_mm = Column(Float, nullable=True)
    max_depth_mm = Column(Float, nullable=True)
    material_depth_offset_mm = Column(Float, nullable=True)
    is_countersink = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    service_mappings = relationship(
        "HoleLibraryServiceMappingModel",
        back_populates="hole_type",
        cascade="all, delete-orphan",
    )


class HoleLibraryServiceMappingModel(Base):
    __tablename__ = "hole_library_service_mappings"
    __table_args__ = (
        UniqueConstraint(
            "hole_type_id",
            "supplier_code",
            "service_external_code",
            name="uq_hole_library_service_mappings_identity",
        ),
        Index("ix_hole_library_service_mappings_hole_type_id", "hole_type_id"),
        Index("ix_hole_library_service_mappings_supplier_code", "supplier_code"),
        Index("ix_hole_library_service_mappings_service_article", "service_article"),
        Index("ix_hole_library_service_mappings_service_external_code", "service_external_code"),
        Index("ix_hole_library_service_mappings_is_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    hole_type_id = Column(Integer, ForeignKey("hole_library_types.id", ondelete="CASCADE"), nullable=False)
    supplier_code = Column(String(64), nullable=False)
    service_external_code = Column(String(255), nullable=False)
    service_article = Column(String(64), nullable=True)
    service_catalog_item_id = Column(String, ForeignKey("service_catalog_items.id", ondelete="SET NULL"), nullable=True)
    service_drilling_rule_id = Column(Integer, ForeignKey("service_drilling_rules.id", ondelete="SET NULL"), nullable=True)
    mapping_status = Column(String(64), nullable=False, default="missing_service")
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    hole_type = relationship("HoleLibraryTypeModel", back_populates="service_mappings")
    service_catalog_item = relationship(ServiceCatalogItemModel)
    service_drilling_rule = relationship(ServiceDrillingRuleModel)
