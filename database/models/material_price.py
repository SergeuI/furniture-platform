from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    text,
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

    old_price = Column(
        Float,
        nullable=True,
    )

    is_promo = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    discount_percent = Column(
        Float,
        nullable=True,
    )

    promo_label = Column(
        Text,
        nullable=True,
    )

    promo_valid_until = Column(
        Date,
        nullable=True,
    )

    source_checked_at = Column(
        DateTime,
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
        nullable=True,
    )
