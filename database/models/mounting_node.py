from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text

from database.base import Base


class MountingNodeModel(Base):

    __tablename__ = "mounting_nodes"

    __table_args__ = (
        UniqueConstraint(
            "code",
            name="uq_mounting_nodes_code",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    code = Column(
        String(128),
        nullable=False,
        index=True,
    )

    name = Column(
        String(255),
        nullable=False,
        index=True,
    )

    description = Column(
        Text,
        nullable=True,
    )

    owner_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )

    created_by_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    updated_by_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    is_archived = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        index=True,
    )

    archived_at = Column(
        DateTime,
        nullable=True,
        index=True,
    )

    archived_by_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    items = relationship(
        "MountingNodeItemModel",
        back_populates="node",
        cascade="all, delete-orphan",
    )

    templates = relationship(
        "MountingNodeTemplateModel",
        back_populates="node",
        cascade="all, delete-orphan",
    )


class MountingNodeItemModel(Base):

    __tablename__ = "mounting_node_items"

    __table_args__ = (
        UniqueConstraint(
            "node_id",
            "fitting_id",
            name="uq_mounting_node_items_node_fitting",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    node_id = Column(
        Integer,
        ForeignKey("mounting_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    fitting_id = Column(
        Integer,
        ForeignKey("fittings.id"),
        nullable=False,
        index=True,
    )

    role = Column(
        String(64),
        nullable=True,
        index=True,
    )

    quantity = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    is_required = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )

    affects_processing = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )

    order_index = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    node = relationship(
        "MountingNodeModel",
        back_populates="items",
    )

    fitting = relationship(
        "FittingModel",
    )


class MountingNodeTemplateModel(Base):

    __tablename__ = "mounting_node_templates"

    __table_args__ = (
        UniqueConstraint(
            "node_id",
            "template_id",
            name="uq_mounting_node_templates_node_template",
        ),
        UniqueConstraint(
            "template_id",
            name="uq_mounting_node_templates_template",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    node_id = Column(
        Integer,
        ForeignKey("mounting_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    template_id = Column(
        Integer,
        ForeignKey("fitting_hole_templates.id"),
        nullable=False,
        index=True,
    )

    is_default = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    order_index = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    node = relationship(
        "MountingNodeModel",
        back_populates="templates",
    )

    template = relationship(
        "FittingHoleTemplateModel",
    )


class MountingNodeVersionModel(Base):

    __tablename__ = "mounting_node_versions"

    __table_args__ = (
        UniqueConstraint(
            "node_id",
            "version_number",
            name="uq_mounting_node_versions_node_version",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    node_id = Column(
        Integer,
        nullable=False,
        index=True,
    )

    node_code = Column(
        String(128),
        nullable=False,
        index=True,
    )

    node_name = Column(
        String(255),
        nullable=False,
        index=True,
    )

    version_number = Column(
        Integer,
        nullable=False,
        index=True,
    )

    event_type = Column(
        String(32),
        nullable=False,
        default="update",
        server_default=text("'update'"),
    )

    snapshot = Column(
        JSON,
        nullable=False,
    )

    created_by_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


__all__ = [
    "MountingNodeItemModel",
    "MountingNodeModel",
    "MountingNodeVersionModel",
    "MountingNodeTemplateModel",
]
