from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api.dependencies import auth as auth_dependencies
from api.routes import project as project_route
from database.base import Base
from database.models.audit_log import AuditLogModel
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel
from database.models.project import ProjectModel
from database.models.project_version import ProjectVersionModel
from services import entitlement_service
from services.entitlement_registry_sync_service import EntitlementRegistrySyncService
import database.repositories.project_repository as project_repository


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@dataclass
class UserStub:
    id: str
    email: str
    role: str


class ProjectEntitlementsApiTests(unittest.TestCase):
    def test_authenticated_free_user_is_blocked_when_project_entitlements_are_disabled(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "projects.db") as (client, _session_factory):
                list_response = client.get(
                    "/projects",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(list_response.status_code, 403)
                self.assertEqual(list_response.json()["detail"]["error"], "Insufficient permissions")

                generate_response = client.post(
                    "/projects/generate",
                    json=self._project_payload(),
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(generate_response.status_code, 403)
                self.assertEqual(generate_response.json()["detail"]["error"], "Insufficient permissions")

    def test_project_quota_counts_only_owned_projects(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(
                Path(tmpdir) / "projects.db",
                project_entitlements={
                    "projects.view": True,
                    "projects.create": True,
                    "projects.edit": True,
                    "projects.delete": True,
                    "projects.max_owned": 3,
                },
                seed_projects=True,
            ) as (client, session_factory):
                with session_factory() as session:
                    session.add_all(
                        [
                            ProjectModel(
                                id="free-owned-1",
                                width=100,
                                height=100,
                                depth=100,
                                sections=1,
                                drawers=[],
                                created_by_user_id="free-user",
                            ),
                            ProjectModel(
                                id="free-owned-2",
                                width=100,
                                height=100,
                                depth=100,
                                sections=1,
                                drawers=[],
                                created_by_user_id="free-user",
                            ),
                            ProjectModel(
                                id="null-owned",
                                width=100,
                                height=100,
                                depth=100,
                                sections=1,
                                drawers=[],
                                created_by_user_id=None,
                            ),
                            ProjectModel(
                                id="other-owned",
                                width=100,
                                height=100,
                                depth=100,
                                sections=1,
                                drawers=[],
                                created_by_user_id="other-user",
                            ),
                        ]
                    )
                    session.commit()

                response = client.get(
                    "/projects/quota",
                    headers=self._auth_headers("free-token"),
                )

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["success"])
                quota = response.json()["project_quota"]
                self.assertEqual(quota["usage"], 2)
                self.assertEqual(quota["limit"], 3)
                self.assertFalse(quota["is_unlimited"])
                self.assertTrue(quota["can_create"])

    def test_project_view_edit_and_delete_routes_respect_entitlements_and_hide_foreign_projects(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(
                Path(tmpdir) / "projects.db",
                project_entitlements={
                    "projects.view": True,
                    "projects.create": True,
                    "projects.edit": True,
                    "projects.delete": True,
                    "projects.max_owned": 3,
                },
            ) as (client, session_factory):
                with session_factory() as session:
                    session.add_all(
                        [
                            ProjectModel(
                                id="own-project",
                                width=100,
                                height=100,
                                depth=100,
                                sections=1,
                                drawers=[],
                                created_by_user_id="free-user",
                            ),
                            ProjectModel(
                                id="foreign-project",
                                width=100,
                                height=100,
                                depth=100,
                                sections=1,
                                drawers=[],
                                created_by_user_id="other-user",
                            ),
                            ProjectModel(
                                id="null-project",
                                width=100,
                                height=100,
                                depth=100,
                                sections=1,
                                drawers=[],
                                created_by_user_id=None,
                            ),
                        ]
                    )
                    session.commit()

                list_response = client.get(
                    "/projects",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(list_response.status_code, 200)
                self.assertTrue(list_response.json()["success"])
                self.assertEqual(list_response.json()["total"], 2)
                returned_ids = {project["id"] for project in list_response.json()["projects"]}
                self.assertEqual(returned_ids, {"own-project", "null-project"})

                own_detail = client.get(
                    "/projects/own-project",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(own_detail.status_code, 200)
                self.assertTrue(own_detail.json()["success"])

                foreign_detail = client.get(
                    "/projects/foreign-project",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(foreign_detail.status_code, 200)
                self.assertFalse(foreign_detail.json()["success"])
                self.assertEqual(foreign_detail.json()["error"], "Project not found")

                update_response = client.put(
                    "/projects/own-project",
                    json=self._project_payload(name="Updated"),
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(update_response.status_code, 200)
                self.assertTrue(update_response.json()["success"])
                self.assertEqual(update_response.json()["project"]["id"], "own-project")

                foreign_update = client.put(
                    "/projects/foreign-project",
                    json=self._project_payload(name="Updated"),
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(foreign_update.status_code, 200)
                self.assertFalse(foreign_update.json()["success"])
                self.assertEqual(foreign_update.json()["error"], "Project not found")

                foreign_delete = client.delete(
                    "/projects/foreign-project",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(foreign_delete.status_code, 200)
                self.assertFalse(foreign_delete.json()["success"])
                self.assertEqual(foreign_delete.json()["error"], "Project not found")

                delete_response = client.delete(
                    "/projects/own-project",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(delete_response.status_code, 200)
                self.assertTrue(delete_response.json()["success"])
                self.assertEqual(delete_response.json()["deleted_project_id"], "own-project")

    def test_project_list_supports_admin_ownership_scope_and_paginates_after_scope_filter(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(
                Path(tmpdir) / "projects.db",
                project_entitlements={
                    "projects.view": True,
                    "projects.create": True,
                    "projects.edit": True,
                    "projects.delete": True,
                    "projects.max_owned": 3,
                },
            ) as (client, session_factory):
                with session_factory() as session:
                    self._seed_projects(
                        session,
                        [
                            ("admin-owned-1", "admin-user"),
                            ("admin-owned-2", "admin-user"),
                            ("other-owned-1", "other-user"),
                            ("other-owned-2", "other-user"),
                            ("other-owned-3", "other-user"),
                            ("unowned-1", None),
                            ("unowned-2", None),
                        ],
                    )

                default_response = client.get(
                    "/projects",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(default_response.status_code, 200)
                self.assertTrue(default_response.json()["success"])
                self.assertEqual(default_response.json()["total"], 7)

                all_response = client.get(
                    "/projects?ownership_scope=all",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(all_response.status_code, 200)
                self.assertTrue(all_response.json()["success"])
                self.assertEqual(all_response.json()["total"], 7)
                self.assertEqual(
                    {project["id"] for project in all_response.json()["projects"]},
                    {project["id"] for project in default_response.json()["projects"]},
                )

                mine_response = client.get(
                    "/projects?ownership_scope=mine",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(mine_response.status_code, 200)
                self.assertTrue(mine_response.json()["success"])
                self.assertEqual(mine_response.json()["total"], 2)
                self.assertEqual(
                    {project["id"] for project in mine_response.json()["projects"]},
                    {"admin-owned-1", "admin-owned-2"},
                )
                self.assertTrue(
                    all(project["created_by_user_id"] == "admin-user" for project in mine_response.json()["projects"])
                )

                unowned_response = client.get(
                    "/projects?ownership_scope=unowned",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(unowned_response.status_code, 200)
                self.assertTrue(unowned_response.json()["success"])
                self.assertEqual(unowned_response.json()["total"], 2)
                self.assertEqual(
                    {project["id"] for project in unowned_response.json()["projects"]},
                    {"unowned-1", "unowned-2"},
                )
                self.assertTrue(
                    all(project["created_by_user_id"] is None for project in unowned_response.json()["projects"])
                )

                users_response = client.get(
                    "/projects?ownership_scope=users",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(users_response.status_code, 200)
                self.assertTrue(users_response.json()["success"])
                self.assertEqual(users_response.json()["total"], 3)
                self.assertEqual(
                    {project["id"] for project in users_response.json()["projects"]},
                    {"other-owned-1", "other-owned-2", "other-owned-3"},
                )
                self.assertTrue(
                    all(
                        project["created_by_user_id"] not in (None, "admin-user")
                        for project in users_response.json()["projects"]
                    )
                )

                paginated_users_response = client.get(
                    "/projects?ownership_scope=users&limit=1&offset=1",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(paginated_users_response.status_code, 200)
                self.assertTrue(paginated_users_response.json()["success"])
                self.assertEqual(paginated_users_response.json()["total"], 3)
                self.assertEqual(len(paginated_users_response.json()["projects"]), 1)
                self.assertIn(
                    paginated_users_response.json()["projects"][0]["id"],
                    {"other-owned-1", "other-owned-2", "other-owned-3"},
                )

    def test_project_list_rejects_invalid_and_conflicting_ownership_scope_values(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(
                Path(tmpdir) / "projects.db",
                project_entitlements={
                    "projects.view": True,
                    "projects.create": True,
                    "projects.edit": True,
                    "projects.delete": True,
                    "projects.max_owned": 3,
                },
            ) as (client, session_factory):
                with session_factory() as session:
                    self._seed_projects(
                        session,
                        [
                            ("free-owned-1", "free-user"),
                            ("null-owned-1", None),
                            ("other-owned-1", "other-user"),
                        ],
                    )

                free_default = client.get(
                    "/projects",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(free_default.status_code, 200)
                self.assertTrue(free_default.json()["success"])
                self.assertEqual(free_default.json()["total"], 2)

                free_only_mine = client.get(
                    "/projects?only_mine=true",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(free_only_mine.status_code, 200)
                self.assertTrue(free_only_mine.json()["success"])
                self.assertEqual(free_only_mine.json()["total"], 1)
                self.assertEqual(
                    {project["id"] for project in free_only_mine.json()["projects"]},
                    {"free-owned-1"},
                )

                invalid_scope = client.get(
                    "/projects?ownership_scope=invalid",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(invalid_scope.status_code, 400)
                self.assertEqual(invalid_scope.json()["detail"]["error"], "Invalid ownership scope")

                conflict_scope = client.get(
                    "/projects?only_mine=true&ownership_scope=all",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(conflict_scope.status_code, 400)
                self.assertEqual(
                    conflict_scope.json()["detail"]["error"],
                    "Conflicting project ownership filters",
                )

                admin_only_mine = client.get(
                    "/projects?only_mine=true&ownership_scope=mine",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(admin_only_mine.status_code, 200)
                self.assertTrue(admin_only_mine.json()["success"])
                self.assertEqual(admin_only_mine.json()["total"], 0)

                non_admin_scope = client.get(
                    "/projects?ownership_scope=users",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(non_admin_scope.status_code, 403)
                self.assertEqual(
                    non_admin_scope.json()["detail"]["error"],
                    "Ownership scope is admin-only",
                )

    def test_generate_uses_authenticated_user_and_blocks_at_quota(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(
                Path(tmpdir) / "projects.db",
                project_entitlements={
                    "projects.view": True,
                    "projects.create": True,
                    "projects.edit": True,
                    "projects.delete": True,
                    "projects.max_owned": 1,
                },
            ) as (client, session_factory):
                create_mock = AsyncMock(
                    return_value=SimpleNamespace(
                        success=True,
                        errors=[],
                        result={"project_id": "generated-project"},
                    )
                )

                with patch.object(project_route, "generate_project", create_mock):
                    response = client.post(
                        "/projects/generate",
                        json=self._project_payload(),
                        headers=self._auth_headers("free-token"),
                    )

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["success"])
                self.assertEqual(response.json()["result"]["project_id"], "generated-project")
                self.assertEqual(create_mock.await_count, 1)
                _, kwargs = create_mock.await_args
                self.assertEqual(kwargs["created_by_user_id"], "free-user")

                with session_factory() as session:
                    session.add(
                        ProjectModel(
                            id="owned-project",
                            width=100,
                            height=100,
                            depth=100,
                            sections=1,
                            drawers=[],
                            created_by_user_id="free-user",
                        )
                    )
                    session.commit()

                blocked_mock = AsyncMock(
                    return_value=SimpleNamespace(
                        success=True,
                        errors=[],
                        result={"project_id": "should-not-be-used"},
                    )
                )

                with patch.object(project_route, "generate_project", blocked_mock):
                    blocked_response = client.post(
                        "/projects/generate",
                        json=self._project_payload(),
                        headers=self._auth_headers("free-token"),
                    )

                self.assertEqual(blocked_response.status_code, 403)
                self.assertEqual(blocked_response.json()["detail"]["error"], "Project ownership limit reached")
                self.assertEqual(blocked_mock.await_count, 0)

    @contextmanager
    def _client_context(
        self,
        database_path: Path,
        *,
        project_entitlements: dict[str, object] | None = None,
        seed_projects: bool = False,
    ):
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", _enable_foreign_keys)
        Base.metadata.create_all(
            engine,
            tables=[
                EntitlementFeatureModel.__table__,
                PlanEntitlementModel.__table__,
                AuditLogModel.__table__,
                ProjectModel.__table__,
                ProjectVersionModel.__table__,
            ],
        )
        session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        with session_factory() as session:
            service = EntitlementRegistrySyncService(session=session)
            service.apply_sync(actor_user_id="admin", actor_email="admin@example.com")
            feature_ids = {
                row.feature_key: row.id
                for row in session.query(EntitlementFeatureModel).all()
            }
            self._configure_project_entitlements(
                session,
                feature_ids,
                project_entitlements=project_entitlements
                or {
                    "projects.view": False,
                    "projects.create": False,
                    "projects.edit": False,
                    "projects.delete": False,
                    "projects.max_owned": 0,
                },
            )
            session.commit()

            if seed_projects:
                session.commit()

        app = FastAPI()
        app.include_router(project_route.router, prefix="/projects")

        free_user = UserStub(
            id="free-user",
            email="free@example.com",
            role="free",
        )
        admin_user = UserStub(
            id="admin-user",
            email="admin@example.com",
            role="admin",
        )
        other_user = UserStub(
            id="other-user",
            email="other@example.com",
            role="free",
        )
        token_map = {
            "free-token": free_user,
            "admin-token": admin_user,
            "other-token": other_user,
        }

        def _resolve_user(token: str):
            return token_map.get(token, free_user)

        with (
            patch.object(auth_dependencies, "get_user_from_token", side_effect=_resolve_user),
            patch.object(entitlement_service, "SessionLocal", side_effect=session_factory),
            patch.object(project_repository, "SessionLocal", side_effect=session_factory),
        ):
            with TestClient(app) as client:
                yield client, session_factory

    @staticmethod
    def _configure_project_entitlements(
        session,
        feature_ids: dict[str, str],
        *,
        project_entitlements: dict[str, object],
    ) -> None:
        for feature_key in ("projects.view", "projects.create", "projects.edit", "projects.delete"):
            entitlement = session.query(PlanEntitlementModel).filter(
                PlanEntitlementModel.feature_id == feature_ids[feature_key],
                PlanEntitlementModel.plan_code == "free",
            ).one()
            entitlement.bool_value = bool(project_entitlements.get(feature_key, False))

        quota_entitlement = session.query(PlanEntitlementModel).filter(
            PlanEntitlementModel.feature_id == feature_ids["projects.max_owned"],
            PlanEntitlementModel.plan_code == "free",
        ).one()
        limit_value = project_entitlements.get("projects.max_owned")
        if limit_value in (None, 0):
            quota_entitlement.integer_value = None
            quota_entitlement.is_unlimited = False
        else:
            quota_entitlement.integer_value = int(limit_value)
            quota_entitlement.is_unlimited = False

    @staticmethod
    def _project_payload(*, name: str = "Test Project") -> dict:
        return {
            "metadata": {
                "name": name,
                "notes": "Test notes",
            },
            "dimensions": {
                "width": 1000,
                "height": 2000,
                "depth": 600,
            },
            "sections": {
                "count": 1,
                "config": [1000],
            },
            "drawers": {
                "config": [],
            },
            "materials": {
                "facade": None,
                "inside": None,
                "facade_edge_banding": None,
                "inside_edge_banding": None,
                "facade_thickness": None,
                "inside_thickness": None,
                "edge_banding": None,
                "thickness": None,
            },
            "fittings": {
                "slide_type": None,
                "bottom_type": None,
                "handle_type": None,
                "handle_position": None,
            },
        }

    @staticmethod
    def _seed_projects(
        session,
        rows: list[tuple[str, str | None]],
    ) -> None:
        base_timestamp = datetime(2026, 1, 1, 12, 0, 0)

        for index, (project_id, owner_id) in enumerate(rows):
            timestamp = base_timestamp + timedelta(minutes=index)
            session.add(
                ProjectModel(
                    id=project_id,
                    width=100,
                    height=100,
                    depth=100,
                    sections=1,
                    drawers=[],
                    project_name=project_id,
                    created_by_user_id=owner_id,
                    updated_by_user_id=owner_id,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )

        session.commit()

    @staticmethod
    def _auth_headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
        }


if __name__ == "__main__":
    unittest.main()
