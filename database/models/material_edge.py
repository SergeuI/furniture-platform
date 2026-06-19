from sqlalchemy import (
    Column,
    Integer,
    LargeBinary,
    String,
)

from database.base import Base


class MaterialEdgeModel(Base):

    __tablename__ = "material_edge_options"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    material_article = Column(
        String,
        index=True,
        nullable=False,
    )

    edge_key = Column(
        String,
        index=True,
        nullable=False,
    )

    article = Column(
        String,
        nullable=True,
    )

    name = Column(
        String,
        nullable=True,
    )

    thickness_label = Column(
        String,
        nullable=True,
    )

    image = Column(
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
