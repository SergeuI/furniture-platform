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
            .order_by(WorkspaceModel.name.asc())
            .all()
        )
    finally:
        db.close()


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
