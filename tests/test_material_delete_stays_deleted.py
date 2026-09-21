import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import audit_log  # noqa: F401
from database.models import hole_library  # noqa: F401
from database.models.material import MaterialModel  # noqa: F401
from database.repositories import audit_log_repository, inventory_repository


class MaterialDeleteStaysDeletedTests(unittest.TestCase):
    def test_default_upsert_does_not_resurrect_deleted_material_but_explicit_restore_does(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "phase1.db"
            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            Base.metadata.create_all(bind=engine)
            session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

            with mock.patch.object(inventory_repository, "SessionLocal", session_factory), mock.patch.object(
                audit_log_repository, "SessionLocal", session_factory
            ):
                created = inventory_repository.upsert_material(
                    article="phase1-delete-me",
                    name="Phase 1 material",
                    category="dsp",
                )
                self.assertIsNotNone(created)
                self.assertIsNotNone(inventory_repository.delete_material("phase1-delete-me"))
                audit_log_repository.create_audit_log(
                    actor_user_id="admin",
                    actor_email="admin@example.com",
                    action="catalog.material_deleted",
                    entity_type="material",
                    entity_id="phase1-delete-me",
                    details={"article": "phase1-delete-me"},
                )

                automatic_attempt = inventory_repository.upsert_material(
                    article="phase1-delete-me",
                    name="Should stay deleted",
                    category="dsp",
                )
                explicit_restore = inventory_repository.upsert_material(
                    article="phase1-delete-me",
                    name="Explicitly restored",
                    category="dsp",
                    allow_deleted_restore=True,
                )

            with session_factory() as session:
                rows = session.execute(
                    text("SELECT article, name FROM materials WHERE article = :article"),
                    {"article": "phase1-delete-me"},
                ).fetchall()

            self.assertIsNone(automatic_attempt)
            self.assertIsNotNone(explicit_restore)
            self.assertEqual([tuple(row) for row in rows], [("phase1-delete-me", "Explicitly restored")])


if __name__ == "__main__":
    unittest.main()
