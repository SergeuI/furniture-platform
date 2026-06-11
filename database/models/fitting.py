from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
)

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
