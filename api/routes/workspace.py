from fastapi import APIRouter, Depends

from api.dependencies.workspace_context import WorkspaceContext, require_workspace_context
from api.dependencies.auth import require_current_user
from services.workspace_membership_service import get_user_workspaces


router = APIRouter()


@router.get("/mine")
def get_my_workspaces(current_user=Depends(require_current_user)):
    return [
        {
            "workspace_id": str(workspace.id),
            "workspace_name": str(workspace.name),
            "workspace_role": str(membership.role),
        }
        for workspace, membership in get_user_workspaces(current_user.id)
    ]


@router.get("/context")
def get_workspace_context(
    context: WorkspaceContext = Depends(require_workspace_context),
):
    return {
        "user_id": context.user_id,
        "user_role": context.user_role,
        "workspace_id": context.workspace_id,
        "workspace_name": context.workspace_name,
        "workspace_role": context.workspace_role,
    }
