from fastapi import HTTPException, status

from database.models.workspace import WorkspaceModel
from database.models.workspace_membership import WorkspaceMembershipModel
from database.session import SessionLocal


def get_user_workspaces(user_id: str):
    from database.repositories.workspace_repository import get_user_workspaces as repository_get_user_workspaces
    return repository_get_user_workspaces(user_id)


def get_workspace_membership(user_id: str, workspace_id: str):
    from database.repositories.workspace_repository import get_workspace_membership as repository_get_workspace_membership
    return repository_get_workspace_membership(user_id, workspace_id)


def require_workspace_membership(user_id: str, workspace_id: str):
    db = SessionLocal()
    try:
        row = (
            db.query(WorkspaceMembershipModel, WorkspaceModel)
            .join(WorkspaceModel, WorkspaceModel.id == WorkspaceMembershipModel.workspace_id)
            .filter(
                WorkspaceMembershipModel.user_id == user_id,
                WorkspaceMembershipModel.workspace_id == workspace_id,
            )
            .first()
        )
        if not row or not row[0].status == "active" or not row[1].is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active workspace membership required")
        return {"workspace": row[1], "membership": row[0]}
    finally:
        db.close()
