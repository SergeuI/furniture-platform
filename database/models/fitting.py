from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    LargeBinary,
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

    fitting_type = Column(
        String,
        index=True,
        nullable=True,
    )

    fitting_group = Column(
        String,
        index=True,
        nullable=True,
    )

    image_url = Column(
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

    owner_user_id = Column(
        String,
        index=True,
        nullable=True,
    )

    is_system = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
    )
