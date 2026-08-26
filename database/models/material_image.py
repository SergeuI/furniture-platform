from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from database.base import Base


class MaterialImageModel(Base):

    __tablename__ = "material_images"

    __table_args__ = (
        UniqueConstraint(
            "material_id",
            "sort_order",
            name="uq_material_images_material_id_sort_order",
        ),
        UniqueConstraint(
            "material_id",
            "image_sha256",
            name="uq_material_images_material_id_image_sha256",
        ),
        Index(
            "ix_material_images_material_id_sort_order",
            "material_id",
            "sort_order",
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

    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
    )

    is_primary = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    source_url = Column(
        Text,
        nullable=True,
    )

    image_cached_bytes = Column(
        LargeBinary,
        nullable=False,
    )

    image_cached_content_type = Column(
        String,
        nullable=False,
    )

    image_sha256 = Column(
        String(64),
        nullable=False,
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
