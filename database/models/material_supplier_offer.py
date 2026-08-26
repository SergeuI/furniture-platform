from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


class MaterialSupplierOfferModel(Base):

    __tablename__ = "material_supplier_offers"

    __table_args__ = (
        Index("ix_material_supplier_offers_material_id", "material_id"),
        Index("ix_material_supplier_offers_supplier_id", "supplier_id"),
        Index("ix_material_supplier_offers_priority", "priority"),
        Index(
            "uq_material_supplier_offers_identity_external",
            "material_id",
            "supplier_id",
            "external_product_id",
            unique=True,
            sqlite_where=text("external_product_id IS NOT NULL"),
        ),
        Index(
            "uq_material_supplier_offers_identity_no_external",
            "material_id",
            "supplier_id",
            unique=True,
            sqlite_where=text("external_product_id IS NULL"),
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    material_id = Column(
        Integer,
        ForeignKey("materials.id", ondelete="CASCADE"),
        nullable=False,
    )

    supplier_id = Column(
        Integer,
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )

    article = Column(
        String,
        nullable=True,
    )

    external_product_id = Column(
        String,
        nullable=True,
    )

    source_url = Column(
        String,
        nullable=True,
    )

    price = Column(
        Float,
        nullable=True,
    )

    currency = Column(
        String,
        nullable=True,
        default="UAH",
    )

    unit = Column(
        String,
        nullable=True,
        default="шт",
    )

    stock = Column(
        String,
        nullable=True,
    )

    city = Column(
        String,
        nullable=True,
    )

    region = Column(
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

    parsed_at = Column(
        DateTime,
        nullable=True,
    )

    price_updated_at = Column(
        DateTime,
        nullable=True,
    )

    source_payload_json = Column(
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

    material = relationship("MaterialModel")
    supplier = relationship("SupplierModel")
