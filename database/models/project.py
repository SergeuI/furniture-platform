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
