from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
)

from database.base import Base


class MaterialPriceModel(Base):

    __tablename__ = "material_prices"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    article = Column(
        String,
        index=True,
        nullable=False,
    )

    city = Column(
        String,
        index=True,
        nullable=True,
    )

    price = Column(
        Float,
        nullable=True,
    )

    updated_at = Column(
        DateTime,
        nullable=True,
    )
