import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api.dependencies import workspace_context
from api.routes import workspace as workspace_route
from database.base import Base
from database.models.hole_library import HoleLibraryTypeModel  # noqa: F401
from database.models.registration_identity import RegistrationChallengeModel
from database.models.user import UserModel
from database.models.workspace import WorkspaceModel
from database.models.workspace_membership import WorkspaceMembershipModel
from database.repositories import workspace_repository
from services import workspace_membership_service


class WorkspaceFoundationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = create_engine(f"sqlite:///{(Path(self.tmp.name) / 'workspace.db').as_posix()}")
        self.addCleanup(self.engine.dispose)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        models = (UserModel, WorkspaceModel, WorkspaceMembershipModel, RegistrationChallengeModel)
        Base.metadata.create_all(self.engine, tables=[model.__table__ for model in models])
        self.sessions = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.patches = [
            mock.patch.object(workspace_membership_service, "SessionLocal", self.sessions),
            mock.patch.object(workspace_repository, "SessionLocal", self.sessions),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def add_user(self, db, label, role="free"):
        user = UserModel(email=f"{label}@example.test", username=label,
                         password_hash="test-hash", role=role)
        db.add(user)
        db.flush()
        return user

    def add_workspace(self, db, user, name, *, active=True, membership_status="active", role="owner"):
        workspace = WorkspaceModel(name=name, slug=f"{name}-{user.id}", is_active=active)
        db.add(workspace)
        db.flush()
        db.add(WorkspaceMembershipModel(workspace_id=workspace.id, user_id=user.id,
                                         role=role, status=membership_status))
        db.flush()
        return workspace

    def test_mine_lists_only_authenticated_users_active_workspaces(self):
        with self.sessions() as db:
            user_a = self.add_user(db, "a")
            user_b = self.add_user(db, "b")
            workspace_a = self.add_workspace(db, user_a, "A")
            self.add_workspace(db, user_b, "B")
            db.commit()
        with mock.patch.object(workspace_route, "get_user_workspaces", workspace_membership_service.get_user_workspaces):
            result = workspace_route.get_my_workspaces(SimpleNamespace(id=user_a.id))
        self.assertEqual(result, [{"workspace_id": workspace_a.id, "workspace_name": "A", "workspace_role": "owner"}])

    def test_inactive_membership_and_workspace_are_excluded(self):
        with self.sessions() as db:
            user = self.add_user(db, "user")
            self.add_workspace(db, user, "active")
            self.add_workspace(db, user, "inactive-membership", membership_status="inactive")
            self.add_workspace(db, user, "inactive-workspace", active=False)
            db.commit()
        self.assertEqual([row[0].name for row in workspace_membership_service.get_user_workspaces(user.id)], ["active"])

    def test_zero_and_one_and_multiple_resolution(self):
        with self.sessions() as db:
            zero = self.add_user(db, "zero")
            one = self.add_user(db, "one")
            two = self.add_user(db, "two")
            one_workspace = self.add_workspace(db, one, "one")
            self.add_workspace(db, two, "two-a")
            self.add_workspace(db, two, "two-b")
            db.commit()
        self.assertIsNone(workspace_membership_service.get_single_active_workspace(zero.id))
        self.assertEqual(workspace_membership_service.get_single_active_workspace(one.id)[0].id, one_workspace.id)
        self.assertIsNone(workspace_membership_service.get_single_active_workspace(two.id))

    def test_context_accepts_active_membership_and_rejects_foreign_or_inactive(self):
        with self.sessions() as db:
            user_a = self.add_user(db, "a")
            user_b = self.add_user(db, "b")
            active = self.add_workspace(db, user_a, "active", role="designer")
            foreign = self.add_workspace(db, user_b, "foreign")
            inactive_membership = self.add_workspace(db, user_a, "inactive-membership", membership_status="inactive")
            inactive_workspace = self.add_workspace(db, user_a, "inactive-workspace", active=False)
            db.commit()
        context = workspace_context.require_workspace_context(active.id, SimpleNamespace(id=user_a.id, role="pro"))
        self.assertEqual((context.workspace_id, context.workspace_role, context.user_role), (active.id, "designer", "pro"))
        for workspace_id in (foreign.id, inactive_membership.id, inactive_workspace.id, "missing"):
            with self.subTest(workspace_id=workspace_id), self.assertRaises(HTTPException) as error:
                workspace_context.require_workspace_context(workspace_id, SimpleNamespace(id=user_a.id, role="free"))
            self.assertEqual(error.exception.status_code, 403)

    def test_mine_has_no_write_side_effect_and_registration_workspace_is_visible(self):
        with self.sessions() as db:
            user = self.add_user(db, "registered")
            workspace = self.add_workspace(db, user, "registered")
            db.commit()
        before = self.counts()
        with mock.patch.object(workspace_route, "get_user_workspaces", workspace_membership_service.get_user_workspaces):
            result = workspace_route.get_my_workspaces(SimpleNamespace(id=user.id))
        self.assertEqual(result[0]["workspace_id"], workspace.id)
        self.assertEqual(self.counts(), before)

    def counts(self):
        with self.sessions() as db:
            return tuple(db.query(model).count() for model in (UserModel, WorkspaceModel, WorkspaceMembershipModel, RegistrationChallengeModel))


if __name__ == "__main__":
    unittest.main()
