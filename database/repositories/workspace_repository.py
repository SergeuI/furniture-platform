from database.models.workspace import WorkspaceModel
from database.models.workspace_membership import WorkspaceMembershipModel
from database.session import SessionLocal


def get_user_workspaces(user_id: str):
    db = SessionLocal()
    try:
        return (
            db.query(WorkspaceModel, WorkspaceMembershipModel)
            .join(WorkspaceMembershipModel, WorkspaceMembershipModel.workspace_id == WorkspaceModel.id)
            .filter(WorkspaceMembershipModel.user_id == user_id)
            .filter(WorkspaceMembershipModel.status == "active")
            .filter(WorkspaceModel.is_active.is_(True))
            .order_by(WorkspaceModel.name.asc())
            .all()
        )
    finally:
        db.close()


def get_single_active_workspace(user_id: str):
    workspaces = get_user_workspaces(user_id)
    return workspaces[0] if len(workspaces) == 1 else None


def get_workspace_membership(user_id: str, workspace_id: str):
    db = SessionLocal()
    try:
        return (
            db.query(WorkspaceMembershipModel)
            .join(WorkspaceModel, WorkspaceModel.id == WorkspaceMembershipModel.workspace_id)
            .filter(
                WorkspaceMembershipModel.user_id == user_id,
                WorkspaceMembershipModel.workspace_id == workspace_id,
            )
            .first()
        )
    finally:
        db.close()
