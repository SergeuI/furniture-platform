import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)

from database.base import Base


class AssistantUnknownPhraseModel(Base):

    __tablename__ = "assistant_unknown_phrases"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    normalized_phrase = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )

    original_phrase = Column(
        String,
        nullable=False,
    )

    count = Column(
        Integer,
        nullable=False,
        default=1,
    )

    status = Column(
        String,
        nullable=False,
        default="new",
        index=True,
    )

    first_seen = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    last_seen = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    last_user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
