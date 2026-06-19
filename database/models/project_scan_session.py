import uuid
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import JSON
from sqlalchemy import String

from database.base import Base


class ProjectScanSessionModel(Base):

    __tablename__ = "project_scan_sessions"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    owner_user_id = Column(
        String,
        nullable=False,
        index=True
    )

    status = Column(
        String,
        default="draft",
        nullable=False,
        index=True
    )

    filename = Column(
        String,
        nullable=True
    )

    file_path = Column(
        String,
        nullable=True
    )

    detected_type = Column(
        String,
        nullable=True
    )

    project_data = Column(
        JSON,
        nullable=False,
        default=dict
    )

    ocr_data = Column(
        JSON,
        nullable=True
    )

    detection_data = Column(
        JSON,
        nullable=True
    )

    confirmed_project_id = Column(
        String,
        nullable=True,
        index=True
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
