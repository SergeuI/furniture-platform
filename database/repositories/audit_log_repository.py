from datetime import datetime
from typing import Optional

from database.session import (
    SessionLocal
)

from database.models.audit_log import (
    AuditLogModel
)


def _make_json_safe(

    value
):

    if isinstance(value, datetime):

        return value.isoformat()

    if isinstance(value, dict):

        return {

            key: _make_json_safe(
                item
            )

            for key, item in value.items()
        }

    if isinstance(value, list):

        return [

            _make_json_safe(
                item
            )

            for item in value
        ]

    return value


# =====================================================
# CREATE AUDIT LOG
# =====================================================

def create_audit_log(

    actor_user_id: str,

    actor_email: str,

    action: str,

    entity_type: str,

    entity_id: str,

    details: Optional[dict] = None
):

    db = SessionLocal()

    try:

        audit_log = AuditLogModel(

            actor_user_id=actor_user_id,

            actor_email=actor_email,

            action=action,

            entity_type=entity_type,

            entity_id=entity_id,

            details=_make_json_safe(
                details or {}
            )
        )

        db.add(audit_log)

        db.commit()

        db.refresh(audit_log)

        return audit_log

    finally:

        db.close()


# =====================================================
# LIST AUDIT LOGS
# =====================================================

def list_audit_logs(

    limit: int = 50,

    offset: int = 0
):

    db = SessionLocal()

    try:

        return (

            db.query(AuditLogModel)

            .order_by(

                AuditLogModel.created_at.desc(),

                AuditLogModel.id.asc()
            )

            .offset(offset)

            .limit(limit)

            .all()
        )

    finally:

        db.close()


# =====================================================
# COUNT AUDIT LOGS
# =====================================================

def count_audit_logs() -> int:

    db = SessionLocal()

    try:

        return (

            db.query(AuditLogModel)

            .count()
        )

    finally:

        db.close()
