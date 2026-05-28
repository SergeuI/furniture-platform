import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    UniqueConstraint
)

from database.base import Base


# =====================================================
# CATALOG ITEM MODEL
# =====================================================

class CatalogItemModel(Base):

    __tablename__ = "catalog_items"

    __table_args__ = (
        UniqueConstraint(
            "category",
            "value",
            name="uq_catalog_items_category_value"
        ),
    )

    id = Column(

        String,

        primary_key=True,

        default=lambda: str(uuid.uuid4())
    )

    category = Column(

        String,

        index=True,

        nullable=False
    )

    value = Column(

        String,

        nullable=False
    )

    sort_order = Column(

        Integer,

        nullable=False,

        default=0
    )

    is_active = Column(

        Boolean,

        nullable=False,

        default=True
    )
