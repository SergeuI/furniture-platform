import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Integer,
    JSON
)

from database.base import Base


class ProjectModel(Base):

    __tablename__ = "projects"

    id = Column(

        String,

        primary_key=True,

        default=lambda: str(uuid.uuid4())
    )

    width = Column(
        Integer
    )

    height = Column(
        Integer
    )

    depth = Column(
        Integer
    )

    sections = Column(
        Integer
    )

    drawers = Column(
        JSON
    )

    project_name = Column(
        String,
        nullable=True
    )

    project_type = Column(
        String,
        nullable=True
    )

    client_name = Column(
        String,
        nullable=True
    )

    room_name = Column(
        String,
        nullable=True
    )

    facade_material = Column(
        String,
        nullable=True
    )

    inside_material = Column(
        String,
        nullable=True
    )

    edge_banding = Column(
        String,
        nullable=True
    )

    edge_overrides = Column(
        JSON,
        nullable=True
    )

    machining_overrides = Column(
        JSON,
        nullable=True
    )

    material_thickness = Column(
        Integer,
        nullable=True
    )

    slide_type = Column(
        String,
        nullable=True
    )

    bottom_type = Column(
        String,
        nullable=True
    )

    handle_type = Column(
        String,
        nullable=True
    )

    handle_position = Column(
        String,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    created_by_user_id = Column(

        String,

        nullable=True
    )

    updated_by_user_id = Column(

        String,

        nullable=True
    )

    created_at = Column(

        DateTime,

        default=datetime.utcnow,

        nullable=True
    )

    updated_at = Column(

        DateTime,

        default=datetime.utcnow,

        onupdate=datetime.utcnow,

        nullable=True
    )
