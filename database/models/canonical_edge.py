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
    func,
    text,
)
from sqlalchemy.orm import relationship

from database.base import Base


class CanonicalEdgeModel(Base):

    __tablename__ = "canonical_edges"

    __table_args__ = (
        Index("ix_canonical_edges_manufacturer_id", "manufacturer_id"),
        Index("ix_canonical_edges_manufacturer_article", "manufacturer_article"),
        Index("ix_canonical_edges_name", "name"),
        Index("ix_canonical_edges_is_active", "is_active"),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    manufacturer_id = Column(
        Integer,
        ForeignKey("material_manufacturers.id", ondelete="SET NULL"),
        nullable=True,
    )

    manufacturer_article = Column(
        String,
        nullable=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    decor_code = Column(
        String,
        nullable=True,
    )

    color = Column(
        String,
        nullable=True,
    )

    material_type = Column(
        String,
        nullable=True,
    )

    width_mm = Column(
        Float,
        nullable=True,
    )

    thickness_mm = Column(
        Float,
        nullable=True,
    )

    finish = Column(
        String,
        nullable=True,
    )

    image_url = Column(
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

    material_relations = relationship(
        "MaterialEdgeRelationModel",
        back_populates="edge",
        cascade="all, delete-orphan",
    )

    supplier_offers = relationship(
        "EdgeSupplierOfferModel",
        back_populates="edge",
        cascade="all, delete-orphan",
    )


class MaterialEdgeRelationModel(Base):

    __tablename__ = "material_edge_relations"

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

    edge_id = Column(
        Integer,
        ForeignKey("canonical_edges.id", ondelete="CASCADE"),
        nullable=False,
    )

    relation_type = Column(
        String,
        nullable=False,
        default="recommended",
    )

    source_supplier_id = Column(
        Integer,
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )

    source_url = Column(
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_material_edge_relations_material_id", "material_id"),
        Index("ix_material_edge_relations_edge_id", "edge_id"),
        Index("ix_material_edge_relations_relation_type", "relation_type"),
        Index("ix_material_edge_relations_source_supplier_id", "source_supplier_id"),
    )

    edge = relationship(
        "CanonicalEdgeModel",
        back_populates="material_relations",
    )


class EdgeSupplierOfferModel(Base):

    __tablename__ = "edge_supplier_offers"

    __table_args__ = (
        Index("ix_edge_supplier_offers_edge_id", "edge_id"),
        Index("ix_edge_supplier_offers_supplier_id", "supplier_id"),
        Index("ix_edge_supplier_offers_priority", "priority"),
        Index(
            "uq_edge_supplier_offers_identity_external",
            "edge_id",
            "supplier_id",
            "external_product_id",
            unique=True,
            sqlite_where=text("external_product_id IS NOT NULL"),
        ),
        Index(
            "uq_edge_supplier_offers_identity_no_external",
            "edge_id",
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

    edge_id = Column(
        Integer,
        ForeignKey("canonical_edges.id", ondelete="CASCADE"),
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

    unit = Column(
        String,
        nullable=True,
    )

    stock = Column(
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

    edge = relationship(
        "CanonicalEdgeModel",
        back_populates="supplier_offers",
    )
    prices = relationship(
        "EdgeSupplierOfferPriceModel",
        back_populates="offer",
        cascade="all, delete-orphan",
    )


class EdgeSupplierOfferPriceModel(Base):

    __tablename__ = "edge_supplier_offer_prices"

    __table_args__ = (
        Index("ix_edge_supplier_offer_prices_offer_id", "offer_id"),
        Index("ix_edge_supplier_offer_prices_city", "city"),
        Index(
            "uq_edge_supplier_offer_prices_offer_city",
            "offer_id",
            "city",
            unique=True,
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    offer_id = Column(
        Integer,
        ForeignKey("edge_supplier_offers.id", ondelete="CASCADE"),
        nullable=False,
    )

    city = Column(
        String,
        nullable=False,
    )

    price = Column(
        Float,
        nullable=True,
    )

    currency = Column(
        String,
        nullable=True,
    )

    availability = Column(
        String,
        nullable=True,
    )

    checked_at = Column(
        DateTime,
        nullable=True,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    offer = relationship(
        "EdgeSupplierOfferModel",
        back_populates="prices",
    )
