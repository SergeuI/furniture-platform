from fastapi import APIRouter, Depends

from api.dependencies.workspace_context import WorkspaceContext, require_workspace_context


router = APIRouter()


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
