from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text

from database.base import Base


class ConstructionRuleModel(Base):
    __tablename__ = "construction_rules"
    __table_args__ = (UniqueConstraint("code", name="uq_construction_rules_code"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(128), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    primary_part_role = Column(String(64), nullable=False)
    secondary_part_role = Column(String(64), nullable=False)
    connection_type = Column(String(64), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    variants = relationship("ConstructionRuleVariantModel", back_populates="rule", cascade="all, delete-orphan", passive_deletes=True)


class ConstructionRuleVariantModel(Base):
    __tablename__ = "construction_rule_variants"
    __table_args__ = (UniqueConstraint("rule_id", "code", name="uq_construction_rule_variants_rule_code"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("construction_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(128), nullable=False)
    name = Column(String(255), nullable=False)
    parameters_json = Column(JSON, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    order_index = Column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    rule = relationship("ConstructionRuleModel", back_populates="variants")
    mounting_options = relationship("ConstructionRuleMountingOptionModel", back_populates="variant", cascade="all, delete-orphan", passive_deletes=True)


class ConstructionRuleMountingOptionModel(Base):
    __tablename__ = "construction_rule_mounting_options"
    __table_args__ = (
        CheckConstraint("mounting_scheme_id IS NOT NULL OR mounting_node_id IS NOT NULL", name="ck_construction_rule_mounting_options_has_solution"),
        UniqueConstraint("variant_id", "mounting_scheme_id", "mounting_node_id", name="uq_construction_rule_mounting_options_identity"),
        Index(
            "uq_construction_rule_mounting_options_variant_node_only",
            "variant_id",
            "mounting_node_id",
            unique=True,
            sqlite_where=text("mounting_scheme_id IS NULL AND mounting_node_id IS NOT NULL"),
        ),
        Index(
            "uq_construction_rule_mounting_options_variant_scheme_only",
            "variant_id",
            "mounting_scheme_id",
            unique=True,
            sqlite_where=text("mounting_scheme_id IS NOT NULL AND mounting_node_id IS NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    variant_id = Column(Integer, ForeignKey("construction_rule_variants.id", ondelete="CASCADE"), nullable=False, index=True)
    mounting_scheme_id = Column(Integer, ForeignKey("mounting_schemes.id", ondelete="RESTRICT"), nullable=True, index=True)
    mounting_node_id = Column(Integer, ForeignKey("mounting_nodes.id", ondelete="RESTRICT"), nullable=True, index=True)
    is_preferred = Column(Boolean, nullable=False, default=False, server_default=text("0"))
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    order_index = Column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    variant = relationship("ConstructionRuleVariantModel", back_populates="mounting_options")
    mounting_scheme = relationship("MountingSchemeModel")
    mounting_node = relationship("MountingNodeModel")


__all__ = ["ConstructionRuleModel", "ConstructionRuleVariantModel", "ConstructionRuleMountingOptionModel"]
