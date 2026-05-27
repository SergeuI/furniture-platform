from fastapi import (
    APIRouter,
    Depends,
    Query
)

from api.dependencies.auth import (
    require_roles
)

from database.repositories.audit_log_repository import (
    count_audit_logs,
    list_audit_logs
)

from schemas.audit_log import (
    AuditLogListResponseSchema
)


router = APIRouter()

require_audit_admin = require_roles(
    [
        "admin"
    ]
)


def _serialize_audit_log(

    audit_log
) -> dict:

    return {

        "id": audit_log.id,

        "actor_user_id": audit_log.actor_user_id,

        "actor_email": audit_log.actor_email,

        "action": audit_log.action,

        "entity_type": audit_log.entity_type,

        "entity_id": audit_log.entity_id,

        "details": audit_log.details,

        "created_at": audit_log.created_at
    }


# =====================================================
# LIST AUDIT LOGS
# =====================================================

@router.get(
    "/logs",

    response_model=AuditLogListResponseSchema
)
async def list_audit_logs_route(

    limit: int = Query(

        default=50,

        ge=1,

        le=100
    ),

    offset: int = Query(

        default=0,

        ge=0
    ),

    current_user = Depends(require_audit_admin)
):

    audit_logs = list_audit_logs(

        limit=limit,

        offset=offset
    )

    return {

        "success": True,

        "total": count_audit_logs(),

        "limit": limit,

        "offset": offset,

        "audit_logs": [

            _serialize_audit_log(
                audit_log
            )

            for audit_log in audit_logs
        ]
    }
