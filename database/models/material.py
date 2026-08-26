from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
)

from database.base import Base


class MaterialModel(Base):

    __tablename__ = "materials"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    article = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    name = Column(
        String,
        nullable=True,
    )

    description = Column(
        String,
        nullable=True,
    )

    color = Column(
        String,
        nullable=True,
    )

    dimensions = Column(
        String,
        nullable=True,
    )

    thickness = Column(
        String,
        nullable=True,
    )

    manufacturer_id = Column(
        Integer,
        ForeignKey("material_manufacturers.id"),
        nullable=True,
    )

    image = Column(
        String,
        nullable=True,
    )

    source_url = Column(
        String,
        nullable=True,
    )

    source = Column(
        String,
        nullable=True,
    )

    product_type = Column(
        String,
        nullable=True,
    )

    owner_user_id = Column(
        String,
        index=True,
        nullable=True,
    )

    category = Column(
        String,
        index=True,
        nullable=True,
    )

    tg_file_id = Column(
        String,
        nullable=True,
    )

    is_default = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    image_cached_bytes = Column(
        LargeBinary,
        nullable=True,
    )

    image_cached_content_type = Column(
        String,
        nullable=True,
    )

    image_source_url = Column(
        String,
        nullable=True,
    )

    image_cached_hash = Column(
        String,
        nullable=True,
    )

    imported_at = Column(
        DateTime,
        nullable=True,
    )

    static_updated_at = Column(
        DateTime,
        nullable=True,
    )
