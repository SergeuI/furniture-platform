from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from api.dependencies import auth as auth_dependencies
from api.routes import auth as auth_route
from database.base import Base
from database.models.user import UserModel
from database.models.user_change_request import UserChangeRequestModel
from database.repositories import user_change_request_repository


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@dataclass
class UserStub:
    id: str
    email: str
    role: str
    is_active: bool = True


class AuthChangeRequestTests(unittest.TestCase):
    def test_change_requests_route_returns_pending_records_with_limit_offset_and_desc_sorting(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "change_requests.db") as (client, session_factory):
                self._seed_change_requests(session_factory)

                response = client.get(
                    "/auth/change-requests?status=pending&limit=2&offset=1",
                    headers=self._auth_headers("admin-token"),
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["success"])
            self.assertEqual(payload["limit"], 2)
            self.assertEqual(payload["offset"], 1)
            self.assertEqual(len(payload["requests"]), 2)
            self.assertTrue(all(item["status"] == "pending" for item in payload["requests"]))
            self.assertEqual(
                [item["id"] for item in payload["requests"]],
                ["pending-new", "pending-mid"],
            )

    def test_change_requests_route_returns_200_for_empty_result(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "change_requests.db") as (client, session_factory):
                self._seed_change_requests(session_factory)

                response = client.get(
                    "/auth/change-requests?status=archived",
                    headers=self._auth_headers("admin-token"),
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["success"])
            self.assertEqual(payload["requests"], [])

    def test_change_requests_route_remains_admin_only(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "change_requests.db") as (client, session_factory):
                self._seed_change_requests(session_factory)

                response = client.get(
                    "/auth/change-requests?status=pending",
                    headers=self._auth_headers("free-token"),
                )

            self.assertEqual(response.status_code, 403)

    def test_change_requests_route_does_not_mutate_database_on_get(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "change_requests.db") as (client, session_factory):
                self._seed_change_requests(session_factory)

                with session_factory() as session:
                    before = [
                        (row.id, row.status, row.created_at)
                        for row in session.query(UserChangeRequestModel)
                        .order_by(UserChangeRequestModel.created_at.desc())
                        .all()
                    ]

                response = client.get(
                    "/auth/change-requests?status=pending&limit=50&offset=0",
                    headers=self._auth_headers("admin-token"),
                )

                with session_factory() as session:
                    after = [
                        (row.id, row.status, row.created_at)
                        for row in session.query(UserChangeRequestModel)
                        .order_by(UserChangeRequestModel.created_at.desc())
                        .all()
                    ]

            self.assertEqual(response.status_code, 200)
            self.assertEqual(before, after)

    def test_repository_without_limit_and_offset_returns_all_matching_records(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._client_context(Path(tmpdir) / "change_requests.db") as (_client, session_factory):
                self._seed_change_requests(session_factory)

                results = user_change_request_repository.list_user_change_requests(status="pending")

            self.assertEqual(
                [row.id for row in results],
                ["pending-newest", "pending-new", "pending-mid", "pending-old"],
            )

    def _seed_change_requests(self, session_factory) -> None:
        now = datetime.utcnow()
        with session_factory() as session:
            session.add_all(
                [
                    UserModel(
                        id="admin-user",
                        email="admin@example.com",
                        username="admin",
                        password_hash="hash",
                        role="admin",
                    ),
                    UserModel(
                        id="request-user",
                        email="request@example.com",
                        username="requester",
                        password_hash="hash",
                        role="free",
                    ),
                    UserChangeRequestModel(
                        id="pending-old",
                        user_id="request-user",
                        change_type="email",
                        old_value="old@example.com",
                        new_value="old-new@example.com",
                        status="pending",
                        created_at=now - timedelta(minutes=40),
                    ),
                    UserChangeRequestModel(
                        id="pending-mid",
                        user_id="request-user",
                        change_type="phone",
                        old_value="+100000000",
                        new_value="+200000000",
                        status="pending",
                        created_at=now - timedelta(minutes=30),
                    ),
                    UserChangeRequestModel(
                        id="approved-old",
                        user_id="request-user",
                        change_type="username",
                        old_value="old-name",
                        new_value="approved-name",
                        status="approved",
                        created_at=now - timedelta(minutes=20),
                    ),
                    UserChangeRequestModel(
                        id="pending-new",
                        user_id="request-user",
                        change_type="city",
                        old_value="kyiv",
                        new_value="lviv",
                        status="pending",
                        created_at=now - timedelta(minutes=10),
                    ),
                    UserChangeRequestModel(
                        id="pending-newest",
                        user_id="request-user",
                        change_type="telegram",
                        old_value="@old",
                        new_value="@new",
                        status="pending",
                        created_at=now - timedelta(minutes=5),
                    ),
                ]
            )
            session.commit()

    @contextmanager
    def _client_context(self, database_path: Path):
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", _enable_foreign_keys)
        Base.metadata.create_all(
            engine,
            tables=[
                UserModel.__table__,
                UserChangeRequestModel.__table__,
            ],
        )
        session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

        app = FastAPI()
        app.include_router(auth_route.router, prefix="/auth")

        admin_user = UserStub(
            id="admin-user",
            email="admin@example.com",
            role="admin",
        )
        free_user = UserStub(
            id="free-user",
            email="free@example.com",
            role="free",
        )

        def _resolve_user(token: str):
            return {
                "admin-token": admin_user,
                "free-token": free_user,
            }.get(token, admin_user)

        with (
            patch.object(auth_dependencies, "get_user_from_token", side_effect=_resolve_user),
            patch.object(user_change_request_repository, "SessionLocal", side_effect=session_factory),
        ):
            with TestClient(app) as client:
                yield client, session_factory

    @staticmethod
    def _auth_headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
        }


if __name__ == "__main__":
    unittest.main()
