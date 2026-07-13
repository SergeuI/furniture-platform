from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func

from database.base import Base


class MaterialUserLinkModel(Base):

    __tablename__ = "material_user_links"

    __table_args__ = (
        UniqueConstraint(
            "material_article",
            "user_id",
            name="uq_material_user_links_material_user",
        ),
    )

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

    user_id = Column(
        String,
        index=True,
        nullable=False,
    )

    source = Column(
        String,
        nullable=True,
    )

    product_type = Column(
        String,
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
