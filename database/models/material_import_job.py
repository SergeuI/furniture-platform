from sqlalchemy import Column, DateTime, Integer, String, Text

from database.base import Base


class MaterialImportJobModel(Base):

    __tablename__ = "material_import_jobs"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    article = Column(
        String,
        index=True,
        nullable=False,
    )

    category = Column(
        String,
        index=True,
        nullable=False,
    )

    city = Column(
        String,
        index=True,
        nullable=False,
    )

    owner_user_id = Column(
        String,
        index=True,
        nullable=True,
    )

    status = Column(
        String,
        index=True,
        nullable=False,
        default="queued",
    )

    attempt_count = Column(
        Integer,
        nullable=False,
        default=0,
    )

    max_attempts = Column(
        Integer,
        nullable=False,
        default=5,
    )

    next_retry_at = Column(
        DateTime,
        nullable=True,
    )

    last_error = Column(
        String,
        nullable=True,
    )

    last_strategy = Column(
        String,
        nullable=True,
    )

    last_source_url = Column(
        String,
        nullable=True,
    )

    preferred_url = Column(
        String,
        nullable=True,
    )

    debug_trace = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=True,
    )

    updated_at = Column(
        DateTime,
        nullable=True,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )
