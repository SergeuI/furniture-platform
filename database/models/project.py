import uuid

from sqlalchemy import (
    Column,
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