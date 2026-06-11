from sqlalchemy import (
    Boolean,
    Column,
    Integer,
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

    image = Column(
        String,
        nullable=True,
    )

    source_url = Column(
        String,
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
