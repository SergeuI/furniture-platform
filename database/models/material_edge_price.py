from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    func,
)

from database.base import Base


class MaterialEdgePriceModel(Base):

    __tablename__ = "material_edge_prices"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    edge_option_id = Column(
        Integer,
        index=True,
        nullable=False,
    )

    city = Column(
        String,
        index=True,
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

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
