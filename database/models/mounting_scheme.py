from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text

from database.base import Base


class MountingSchemeModel(Base):
    __tablename__ = "mounting_schemes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_mounting_schemes_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(128), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    nodes = relationship(
        "MountingSchemeNodeModel",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="scheme",
    )
    placement_rules = relationship(
        "MountingSchemePlacementRuleModel",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="scheme",
    )


class MountingSchemeNodeModel(Base):
    __tablename__ = "mounting_scheme_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scheme_id = Column(
        Integer,
        ForeignKey("mounting_schemes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id = Column(
        Integer,
        ForeignKey("mounting_nodes.id"),
        nullable=False,
        index=True,
    )
    group_key = Column(String(64), nullable=False, index=True)
    quantity_per_group = Column(Integer, nullable=False, default=1, server_default=text("1"))
    role_code = Column(String(64), nullable=True, index=True)
    order_index = Column(Integer, nullable=False, default=0, server_default=text("0"))
    is_required = Column(Boolean, nullable=False, default=True, server_default=text("1"))

    scheme = relationship("MountingSchemeModel", back_populates="nodes")
    node = relationship("MountingNodeModel")


class MountingSchemePlacementRuleModel(Base):
    __tablename__ = "mounting_scheme_placement_rules"
    __table_args__ = (
        UniqueConstraint("scheme_id", "group_key", name="uq_mounting_scheme_placement_rules_scheme_group"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    scheme_id = Column(
        Integer,
        ForeignKey("mounting_schemes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_key = Column(String(64), nullable=False, index=True)
    distribution_mode = Column(String(32), nullable=False, default="equal", server_default=text("'equal'"))
    min_group_count = Column(Integer, nullable=False, default=1, server_default=text("1"))
    max_group_count = Column(Integer, nullable=True)
    fixed_group_count = Column(Integer, nullable=True)
    start_offset_mm = Column(Integer, nullable=True)
    end_offset_mm = Column(Integer, nullable=True)
    max_spacing_mm = Column(Integer, nullable=True)
    fixed_spacing_mm = Column(Integer, nullable=True)

    scheme = relationship("MountingSchemeModel", back_populates="placement_rules")


__all__ = [
    "MountingSchemeModel",
    "MountingSchemeNodeModel",
    "MountingSchemePlacementRuleModel",
]
