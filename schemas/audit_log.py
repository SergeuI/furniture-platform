from datetime import datetime
from typing import List
from typing import Optional

from pydantic import (
    BaseModel
)


# =====================================================
# AUDIT LOG RESPONSES
# =====================================================

class AuditLogResponseSchema(BaseModel):

    id: str

    actor_user_id: str

    actor_email: str

    action: str

    entity_type: str

    entity_id: str

    details: Optional[dict] = None

    created_at: datetime


class AuditLogListResponseSchema(BaseModel):

    success: bool

    total: int

    limit: int

    offset: int

    audit_logs: List[AuditLogResponseSchema]
