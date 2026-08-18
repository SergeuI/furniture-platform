from __future__ import annotations

import sqlite3
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.dependencies import auth as auth_dependencies
from api.routes import catalog as catalog_route
from database.repositories import fitting_taxonomy_repository
from services import upload_service


class _AllowedEntitlementService:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def has_feature(self, current_user, feature_key: str) -> bool:
        return feature_key in {"fittings.create", "fittings.edit", "fittings.view"}


class FittingManufacturerLogoUploadApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.upload_root = Path(self._tmpdir.name) / "uploads" / "fitting-manufacturer-logos"
        self.database_path = Path(self._tmpdir.name) / "manufacturers.db"
        self._create_schema(self.database_path)

        self.engine = create_engine(
            f"sqlite:///{self.database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        self._original_session_local = fitting_taxonomy_repository.SessionLocal
        fitting_taxonomy_repository.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def tearDown(self) -> None:
        fitting_taxonomy_repository.SessionLocal = self._original_session_local
        self.engine.dispose()
        self._tmpdir.cleanup()

    def test_png_upload_returns_logo_url_and_can_be_persisted_on_manufacturer(self) -> None:
        app = self._build_app()
        png_bytes = self._make_image_bytes("PNG")

        with patch.object(upload_service, "MANUFACTURER_LOGO_UPLOAD_ROOT", self.upload_root):
            with patch.object(catalog_route, "EntitlementService", _AllowedEntitlementService):
                with TestClient(app) as client:
                    response = client.post(
                        "/catalog/fitting-manufacturers/logo",
                        headers={"Authorization": "Bearer token"},
                        files={"file": ("manufacturer-logo.png", png_bytes, "image/png")},
                    )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertTrue(response.json()["logo_url"].startswith("/uploads/fitting-manufacturer-logos/"))

        saved_logo_url = response.json()["logo_url"]
        manufacturer = fitting_taxonomy_repository.create_fitting_manufacturer(
            code="blum",
            name="Blum",
            logo_url=saved_logo_url,
            is_active=True,
            sort_order=1,
        )
        self.assertIsNotNone(manufacturer)
        assert manufacturer is not None
        self.assertEqual(manufacturer["logo_url"], saved_logo_url)

        saved_file = self.upload_root / Path(saved_logo_url).name
        self.assertTrue(saved_file.exists())

        with patch.object(upload_service, "MANUFACTURER_LOGO_UPLOAD_ROOT", self.upload_root):
            with patch.object(catalog_route, "EntitlementService", _AllowedEntitlementService):
                with TestClient(app) as client:
                    list_response = client.get(
                        "/catalog/fitting-manufacturers?active_only=false",
                        headers={"Authorization": "Bearer token"},
                    )

        self.assertEqual(list_response.status_code, 200)
        items = list_response.json()["items"]
        saved_item = next(item for item in items if item["code"] == "blum")
        self.assertEqual(saved_item["logo_url"], saved_logo_url)

    def test_invalid_file_type_is_rejected(self) -> None:
        app = self._build_app()

        with patch.object(upload_service, "MANUFACTURER_LOGO_UPLOAD_ROOT", self.upload_root):
            with patch.object(catalog_route, "EntitlementService", _AllowedEntitlementService):
                with TestClient(app) as client:
                    response = client.post(
                        "/catalog/fitting-manufacturers/logo",
                        headers={"Authorization": "Bearer token"},
                        files={"file": ("manufacturer-logo.txt", b"plain text", "text/plain")},
                    )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["detail"]["success"])
        self.assertIn("Unsupported file type", response.json()["detail"]["error"])

    def _build_app(self) -> FastAPI:
        app = FastAPI()
        app.include_router(catalog_route.router, prefix="/catalog")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")
        return app

    @staticmethod
    def _make_image_bytes(format_name: str) -> bytes:
        image = Image.new("RGB", (1, 1), color=(255, 0, 0))
        buffer = BytesIO()
        image.save(buffer, format=format_name)
        return buffer.getvalue()

    @staticmethod
    def _create_schema(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE fitting_manufacturers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    description TEXT,
                    website_url TEXT,
                    logo_url TEXT,
                    country_code TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
