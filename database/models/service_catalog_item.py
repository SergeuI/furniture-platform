import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from database.base import Base


class ServiceCatalogItemModel(Base):

    __tablename__ = "service_catalog_items"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_code",
            name="uq_service_catalog_items_source_code",
        ),
    )

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    source = Column(
        String,
        index=True,
        nullable=False,
    )

    external_code = Column(
        String,
        index=True,
        nullable=False,
    )

    parent_external_code = Column(
        String,
        index=True,
        nullable=True,
    )

    owner_user_id = Column(
        String,
        index=True,
        nullable=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    slug = Column(
        String,
        nullable=False,
    )

    item_type = Column(
        String,
        nullable=False,
        default="service",
    )

    folder_path = Column(
        String,
        nullable=True,
    )

    description = Column(
        Text,
        nullable=True,
    )

    article = Column(
        String,
        nullable=True,
    )

    unit = Column(
        String,
        nullable=True,
    )

    base_price = Column(
        Float,
        nullable=True,
    )

    currency = Column(
        String,
        nullable=True,
    )

    source_url = Column(
        String,
        nullable=True,
    )

    is_calculable = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
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
