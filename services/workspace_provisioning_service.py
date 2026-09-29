from sqlalchemy.orm import Session

from database.models.user import UserModel
from database.models.workspace import WorkspaceModel
from database.models.workspace_membership import WorkspaceMembershipModel


INITIAL_WORKSPACE_NAME = "Мій робочий простір"


def provision_initial_workspace(db: Session, user: UserModel):
    """Provision in the caller's transaction, after the new User has been flushed.

    The full immutable user ID identifies the initial workspace. The display
    name is a renameable placeholder, not a person's or company's legal name.
    Conflicting or inactive existing ownership is rejected, never repaired.
    """
    if not user.id:
        raise ValueError("User must be flushed before workspace provisioning")

    slug = f"account-{user.id}"
    workspace = db.query(WorkspaceModel).filter(WorkspaceModel.slug == slug).first()
    if workspace is not None:
        membership = (
            db.query(WorkspaceMembershipModel)
            .filter(
                WorkspaceMembershipModel.workspace_id == workspace.id,
                WorkspaceMembershipModel.user_id == user.id,
            )
            .first()
        )
        if (
            not workspace.is_active
            or membership is None
            or membership.role != "owner"
            or membership.status != "active"
        ):
            raise ValueError("Initial workspace ownership conflict")
        return workspace, membership

    workspace = WorkspaceModel(name=INITIAL_WORKSPACE_NAME, slug=slug, is_active=True)
    db.add(workspace)
    db.flush()
    membership = WorkspaceMembershipModel(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
        status="active",
    )
    db.add(membership)
    db.flush()
    return workspace, membership
