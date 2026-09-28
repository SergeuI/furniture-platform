from dataclasses import dataclass

from fastapi import Depends, Query

from api.dependencies.auth import require_current_user
from services.workspace_membership_service import require_workspace_membership


@dataclass(frozen=True)
class WorkspaceContext:
    user_id: str
    user_role: str
    workspace_id: str
    workspace_name: str
    workspace_role: str


def require_workspace_context(workspace_id: str = Query(..., min_length=1), current_user=Depends(require_current_user)) -> WorkspaceContext:
    validated = require_workspace_membership(current_user.id, workspace_id)
    return WorkspaceContext(
        user_id=str(current_user.id),
        user_role=str(current_user.role),
        workspace_id=str(validated["workspace"].id),
        workspace_name=str(validated["workspace"].name),
        workspace_role=str(validated["membership"].role),
    )
