import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    JSON,
    String
)

from database.base import Base


# =====================================================
# AUDIT LOG MODEL
# =====================================================

class AuditLogModel(Base):

    __tablename__ = "audit_logs"

    id = Column(

        String,

        primary_key=True,

        default=lambda: str(uuid.uuid4())
    )

    actor_user_id = Column(

        String,

        nullable=False,

        index=True
    )

    actor_email = Column(

        String,

        nullable=False,

        index=True
    )

    action = Column(

        String,

        nullable=False,

        index=True
    )

    entity_type = Column(

        String,

        nullable=False,

        index=True
    )

    entity_id = Column(

        String,

        nullable=False,

        index=True
    )

    details = Column(

        JSON,

        nullable=True
    )

    created_at = Column(

        DateTime,

        default=datetime.utcnow,

        nullable=False,

        index=True
    )
