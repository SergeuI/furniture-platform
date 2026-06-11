import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    String,
    UniqueConstraint,
)

from database.base import Base


class UserServiceCatalogPriceModel(Base):

    __tablename__ = "user_service_catalog_prices"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "service_catalog_item_id",
            name="uq_user_service_catalog_price_user_item",
        ),
    )

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    user_id = Column(
        String,
        index=True,
        nullable=False,
    )

    service_catalog_item_id = Column(
        String,
        index=True,
        nullable=False,
    )

    base_price = Column(
        Float,
        nullable=True,
    )

    currency = Column(
        String,
        nullable=True,
    )

    last_synced_at = Column(
        DateTime,
        nullable=True,
    )

    price_sync_status = Column(
        String,
        nullable=True,
    )

    price_source_label = Column(
        String,
        nullable=True,
    )
