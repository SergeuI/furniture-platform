from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text

from database.base import Base


class FittingModel(Base):

    __tablename__ = "fittings"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    city = Column(
        String,
        index=True,
        nullable=True,
    )

    code = Column(
        String,
        index=True,
        nullable=True,
    )

    article = Column(
        String,
        index=True,
        nullable=True,
    )

    name = Column(
        String,
        nullable=True,
    )

    price = Column(
        Float,
        nullable=True,
    )

    stock = Column(
        String,
        nullable=True,
    )

    fitting_type = Column(
        String,
        index=True,
        nullable=True,
    )

    fitting_group = Column(
        String,
        index=True,
        nullable=True,
    )

    image_url = Column(
        String,
        nullable=True,
    )

    image_cached_bytes = Column(
        LargeBinary,
        nullable=True,
    )

    image_cached_content_type = Column(
        String,
        nullable=True,
    )

    source_url = Column(
        String,
        nullable=True,
    )

    source = Column(
        String,
        index=True,
        nullable=True,
    )

    brand = Column(
        String,
        index=True,
        nullable=True,
    )

    description = Column(
        Text,
        nullable=True,
    )

    unit = Column(
        String,
        nullable=True,
        default="шт",
    )

    currency = Column(
        String,
        nullable=True,
        default="UAH",
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

    owner_user_id = Column(
        String,
        index=True,
        nullable=True,
    )

    is_system = Column(
        Boolean,
        nullable=False,
        default=True,
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

    hole_templates = relationship(
        "FittingHoleTemplateModel",
        back_populates="fitting",
        cascade="all, delete-orphan",
    )


class FittingHoleTemplateModel(Base):

    __tablename__ = "fitting_hole_templates"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    fitting_id = Column(
        Integer,
        ForeignKey("fittings.id"),
        index=True,
        nullable=False,
    )

    name = Column(
        String,
        nullable=True,
    )

    bundle_key = Column(
        String,
        index=True,
        nullable=True,
    )

    bundle_name = Column(
        String,
        index=True,
        nullable=True,
    )

    bundle_order_index = Column(
        Integer,
        nullable=False,
        default=0,
    )

    template_type = Column(
        String,
        index=True,
        nullable=True,
    )

    side = Column(
        String,
        index=True,
        nullable=True,
    )

    coordinate_system = Column(
        String,
        nullable=True,
    )

    mounting_variant_key = Column(
        String,
        nullable=False,
        default="surface_mount",
        server_default=text("'surface_mount'"),
    )

    is_default = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    notes = Column(
        Text,
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

    fitting = relationship(
        "FittingModel",
        back_populates="hole_templates",
    )

    points = relationship(
        "FittingHolePointModel",
        back_populates="template",
        cascade="all, delete-orphan",
    )


class FittingHolePointModel(Base):

    __tablename__ = "fitting_hole_points"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    template_id = Column(
        Integer,
        ForeignKey("fitting_hole_templates.id"),
        index=True,
        nullable=False,
    )

    label = Column(
        String,
        nullable=True,
    )

    x_mm = Column(
        Float,
        nullable=True,
    )

    y_mm = Column(
        Float,
        nullable=True,
    )

    z_mm = Column(
        Float,
        nullable=True,
    )

    diameter_mm = Column(
        Float,
        nullable=True,
    )

    depth_mm = Column(
        Float,
        nullable=True,
    )

    side = Column(
        String,
        index=True,
        nullable=True,
    )

    operation = Column(
        String,
        index=True,
        nullable=True,
    )

    order_index = Column(
        Integer,
        nullable=False,
        default=0,
    )

    quantity = Column(
        Integer,
        nullable=False,
        default=1,
    )

    mirrored = Column(
        Boolean,
        nullable=False,
        default=False,
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

    template = relationship(
        "FittingHoleTemplateModel",
        back_populates="points",
    )
