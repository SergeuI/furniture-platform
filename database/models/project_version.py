import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Integer,
    JSON,
    ForeignKey
)

from database.base import Base


# =====================================================
# PROJECT VERSION MODEL
# =====================================================

class ProjectVersionModel(Base):

    __tablename__ = "project_versions"

    id = Column(

        String,

        primary_key=True,

        default=lambda: str(uuid.uuid4())
    )

    project_id = Column(

        String,

        ForeignKey("projects.id")
    )

    width = Column(Integer)

    height = Column(Integer)

    depth = Column(Integer)

    sections = Column(Integer)

    drawers = Column(JSON)

    created_at = Column(

        DateTime,

        default=datetime.utcnow,

        nullable=True
    )
