from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


class MaterialCategoryModel(Base):

    __tablename__ = "material_categories"

    __table_args__ = (
        Index("uq_material_categories_code", "code", unique=True),
        Index("ix_material_categories_owner_user_id", "owner_user_id"),
        Index("ix_material_categories_parent_id", "parent_id"),
        Index("ix_material_categories_is_active", "is_active"),
        Index("ix_material_categories_is_system", "is_system"),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    code = Column(
        String,
        nullable=False,
    )

    name = Column(
        String,
        nullable=False,
    )

    description = Column(
        String,
        nullable=True,
    )

    image_url = Column(
        String,
        nullable=True,
    )

    owner_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
    )

    parent_id = Column(
        Integer,
        ForeignKey("material_categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    is_system = Column(
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

    parent = relationship(
        "MaterialCategoryModel",
        remote_side=[id],
        back_populates="children",
    )

    children = relationship(
        "MaterialCategoryModel",
        back_populates="parent",
    )


class MaterialManufacturerModel(Base):

    __tablename__ = "material_manufacturers"

    __table_args__ = (
        Index("uq_material_manufacturers_normalized_name", "normalized_name", unique=True),
        Index("uq_material_manufacturers_code", "code", unique=True),
        Index("ix_material_manufacturers_owner_user_id", "owner_user_id"),
        Index("ix_material_manufacturers_is_active", "is_active"),
        Index("ix_material_manufacturers_is_system", "is_system"),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    normalized_name = Column(
        String,
        nullable=False,
    )

    code = Column(
        String,
        nullable=True,
    )

    website_url = Column(
        String,
        nullable=True,
    )

    logo_url = Column(
        String,
        nullable=True,
    )

    owner_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    is_system = Column(
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

    aliases = relationship(
        "MaterialManufacturerAliasModel",
        back_populates="manufacturer",
        cascade="all, delete-orphan",
    )


class MaterialManufacturerAliasModel(Base):

    __tablename__ = "material_manufacturer_aliases"

    __table_args__ = (
        Index("uq_material_manufacturer_aliases_normalized_alias", "normalized_alias", unique=True),
        Index("ix_material_manufacturer_aliases_manufacturer_id", "manufacturer_id"),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    manufacturer_id = Column(
        Integer,
        ForeignKey("material_manufacturers.id", ondelete="CASCADE"),
        nullable=False,
    )

    alias = Column(
        String,
        nullable=False,
    )

    normalized_alias = Column(
        String,
        nullable=False,
    )

    source = Column(
        String,
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

    manufacturer = relationship(
        "MaterialManufacturerModel",
        back_populates="aliases",
    )
