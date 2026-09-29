import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.registration_identity import RegistrationChallengeModel
from database.models.hole_library import HoleLibraryTypeModel  # noqa: F401 - register mapper
from database.models.user import UserModel
from database.models.workspace import WorkspaceModel
from database.models.workspace_membership import WorkspaceMembershipModel
from database.repositories import user_repository
from services import auth_service, production_auth_engine, telegram_identity_service
from services import registration_onboarding_service as onboarding
from services.workspace_provisioning_service import (
    INITIAL_WORKSPACE_NAME,
    provision_initial_workspace,
)


class WorkspaceProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "registration.db"
        self.engine = create_engine(f"sqlite:///{self.path.as_posix()}")
        self.addCleanup(self.engine.dispose)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        self.models = (UserModel, WorkspaceModel, WorkspaceMembershipModel, RegistrationChallengeModel)
        Base.metadata.create_all(self.engine, tables=[model.__table__ for model in self.models])
        self.sessions = sessionmaker(bind=self.engine, autoflush=False)
        self.patch = mock.patch.object(onboarding, "SessionLocal", self.sessions)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def start_registration(self):
        return onboarding.start_pending_phone_registration(
            name="Person Name", email="new@example.test", password="Password123",
            phone="+380501234567", local_test_mode=True,
        )

    def counts(self):
        with self.sessions() as db:
            return tuple(db.query(model).count() for model in self.models)

    @staticmethod
    def add_user(db, label="existing"):
        user = UserModel(email=f"{label}@example.test", username=label,
                         password_hash="test-hash", role="free")
        db.add(user)
        db.flush()
        return user

    def test_registration_creates_complete_set_and_keeps_free_role(self):
        self.assertTrue(self.start_registration()["success"])
        self.assertEqual(self.counts(), (1, 1, 1, 1))
        with self.sessions() as db:
            user = db.query(UserModel).one()
            workspace = db.query(WorkspaceModel).one()
            membership = db.query(WorkspaceMembershipModel).one()
            challenge = db.query(RegistrationChallengeModel).one()
            self.assertEqual(user.role, "free")
            self.assertEqual(user.registration_status, "pending_phone")
            self.assertIsNone(user.trial_started_at)
            self.assertEqual(workspace.slug, f"account-{user.id}")
            self.assertEqual(workspace.name, INITIAL_WORKSPACE_NAME)
            self.assertTrue(workspace.is_active)
            self.assertEqual((membership.user_id, membership.workspace_id), (user.id, workspace.id))
            self.assertEqual((membership.role, membership.status), ("owner", "active"))
            self.assertEqual(challenge.user_id, user.id)

    def test_recall_before_and_after_commit_preserves_identity_and_display_name(self):
        with self.sessions() as db:
            user = self.add_user(db)
            user_id = user.id
            workspace, membership = provision_initial_workspace(db, user)
            expected_ids = workspace.id, membership.id
            second = provision_initial_workspace(db, user)
            self.assertEqual(tuple(row.id for row in second), expected_ids)
            workspace.name = "Renamed company"
            user.username = "renamed-person"
            user.email = "changed@example.test"
            db.commit()
        with self.sessions() as db:
            result = provision_initial_workspace(db, db.get(UserModel, user_id))
            self.assertEqual(tuple(row.id for row in result), expected_ids)
            self.assertEqual(result[0].name, "Renamed company")
            db.commit()
        self.assertEqual(self.counts(), (1, 1, 1, 0))

    def test_helper_does_not_commit_or_rollback_callers_transaction(self):
        with self.sessions() as db:
            user = self.add_user(db)
            with mock.patch.object(db, "commit", side_effect=AssertionError("helper committed")), \
                 mock.patch.object(db, "rollback", side_effect=AssertionError("helper rolled back")):
                provision_initial_workspace(db, user)
                provision_initial_workspace(db, user)
            db.rollback()
        self.assertEqual(self.counts(), (0, 0, 0, 0))

    def assert_insert_failure_rolls_back(self, model):
        def fail_insert(*_):
            raise IntegrityError("forced insert failure", {}, RuntimeError("forced"))

        event.listen(model, "before_insert", fail_insert)
        try:
            with self.assertRaises(IntegrityError):
                self.start_registration()
        finally:
            event.remove(model, "before_insert", fail_insert)
        self.assertEqual(self.counts(), (0, 0, 0, 0))

    def test_workspace_insert_failure_rolls_back_entire_registration(self):
        self.assert_insert_failure_rolls_back(WorkspaceModel)

    def test_membership_insert_failure_rolls_back_entire_registration(self):
        self.assert_insert_failure_rolls_back(WorkspaceMembershipModel)

    def test_challenge_insert_failure_rolls_back_entire_registration(self):
        self.assert_insert_failure_rolls_back(RegistrationChallengeModel)

    def test_unexpected_helper_failure_rolls_back(self):
        with mock.patch.object(onboarding, "provision_initial_workspace", side_effect=RuntimeError("forced")):
            with self.assertRaises(RuntimeError):
                self.start_registration()
        self.assertEqual(self.counts(), (0, 0, 0, 0))

    def test_slug_collision_does_not_attach_to_another_owner(self):
        with self.sessions() as db:
            owner = self.add_user(db, "owner")
            other = self.add_user(db, "other")
            workspace = WorkspaceModel(slug=f"account-{other.id}", name="Other owner's workspace")
            db.add(workspace)
            db.flush()
            db.add(WorkspaceMembershipModel(workspace_id=workspace.id, user_id=owner.id,
                                            role="owner", status="active"))
            other_id = other.id
            db.commit()
        with self.sessions() as db:
            with self.assertRaisesRegex(ValueError, "ownership conflict"):
                provision_initial_workspace(db, db.get(UserModel, other_id))
            db.rollback()
            self.assertIsNone(db.query(WorkspaceMembershipModel).filter_by(user_id=other_id).first())
        self.assertEqual(self.counts(), (2, 1, 1, 0))

    def test_existing_workspace_requires_active_owner_and_active_workspace(self):
        for invalid in ("missing", "member", "inactive_membership", "inactive_workspace"):
            with self.subTest(invalid=invalid), self.sessions() as db:
                user = self.add_user(db, invalid)
                workspace = WorkspaceModel(slug=f"account-{user.id}", name="Existing",
                                           is_active=invalid != "inactive_workspace")
                db.add(workspace)
                db.flush()
                if invalid != "missing":
                    db.add(WorkspaceMembershipModel(
                        workspace_id=workspace.id, user_id=user.id,
                        role="member" if invalid == "member" else "owner",
                        status="inactive" if invalid == "inactive_membership" else "active",
                    ))
                    db.flush()
                with self.assertRaisesRegex(ValueError, "ownership conflict"):
                    provision_initial_workspace(db, user)
                db.rollback()

    def test_existing_users_untouched_and_duplicate_registration_creates_nothing(self):
        with self.sessions() as db:
            legacy = self.add_user(db)
            legacy_id = legacy.id
            db.commit()
            before = {col.name: getattr(legacy, col.name) for col in UserModel.__table__.columns}
        self.assertTrue(self.start_registration()["success"])
        self.assertFalse(self.start_registration()["success"])
        self.assertEqual(self.counts(), (2, 1, 1, 1))
        with self.sessions() as db:
            legacy = db.get(UserModel, legacy_id)
            self.assertEqual({col.name: getattr(legacy, col.name) for col in UserModel.__table__.columns}, before)
            self.assertIsNone(db.query(WorkspaceMembershipModel).filter_by(user_id=legacy_id).first())

    def test_other_creation_paths_do_not_provision(self):
        with mock.patch.object(user_repository, "SessionLocal", self.sessions):
            auth_service.register_user("local@example.test", "Password123", role="free")
            auth_service.create_managed_user("admin@example.test", "Password123", role="admin")
            # Demo seed uses this same managed-user operation.
            auth_service.create_managed_user("demo@example.test", "Password123", role="free")
            telegram_identity_service.ensure_telegram_identity(101, "telegram@example.test")
            production_auth_engine.init_auth_tables(db_path=str(self.path))
            production_auth_engine.register_user(102, "operator", "cut_operator", db_path=str(self.path))
        self.assertEqual(self.counts(), (5, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
