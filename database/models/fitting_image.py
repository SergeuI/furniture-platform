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


class FittingImageModel(Base):

    __tablename__ = "fitting_images"

    __table_args__ = (
        UniqueConstraint(
            "fitting_id",
            "sort_order",
            name="uq_fitting_images_fitting_id_sort_order",
        ),
        UniqueConstraint(
            "fitting_id",
            "image_sha256",
            name="uq_fitting_images_fitting_id_image_sha256",
        ),
        Index(
            "ix_fitting_images_fitting_id_sort_order",
            "fitting_id",
            "sort_order",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    fitting_id = Column(
        Integer,
        ForeignKey("fittings.id", ondelete="CASCADE"),
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
