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
from database.repositories import inventory_repository
from services import upload_service


class _AllowedEntitlementService:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def has_feature(self, current_user, feature_key: str) -> bool:
        return feature_key in {"fittings.create", "fittings.edit"}


class SupplierLogoUploadApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.upload_root = Path(self._tmpdir.name) / "uploads" / "supplier-logos"
        self.database_path = Path(self._tmpdir.name) / "suppliers.db"
        self._create_schema(self.database_path)

        self.engine = create_engine(
            f"sqlite:///{self.database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        self._original_session_local = inventory_repository.SessionLocal
        inventory_repository.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def tearDown(self) -> None:
        inventory_repository.SessionLocal = self._original_session_local
        self.engine.dispose()
        self._tmpdir.cleanup()

    def test_png_and_jpg_uploads_return_logo_urls_and_persist_in_supplier(self) -> None:
        app = self._build_app()

        png_bytes = self._make_image_bytes("PNG")
        jpg_bytes = self._make_image_bytes("JPEG")

        with patch.object(upload_service, "SUPPLIER_LOGO_UPLOAD_ROOT", self.upload_root):
            with patch.object(catalog_route, "EntitlementService", _AllowedEntitlementService):
                with TestClient(app) as client:
                    png_response = client.post(
                        "/catalog/suppliers/logo",
                        headers={"Authorization": "Bearer token"},
                        files={"file": ("supplier-logo.png", png_bytes, "image/png")},
                    )
                    jpg_response = client.post(
                        "/catalog/suppliers/logo",
                        headers={"Authorization": "Bearer token"},
                        files={"file": ("supplier-logo.jpg", jpg_bytes, "image/jpeg")},
                    )

        self.assertEqual(png_response.status_code, 200)
        self.assertTrue(png_response.json()["success"])
        self.assertTrue(png_response.json()["logo_url"].startswith("/uploads/supplier-logos/"))

        self.assertEqual(jpg_response.status_code, 200)
        self.assertTrue(jpg_response.json()["success"])
        self.assertTrue(jpg_response.json()["logo_url"].startswith("/uploads/supplier-logos/"))

        saved_logo_url = png_response.json()["logo_url"]
        supplier = inventory_repository.create_supplier(
            code="logo-supplier",
            name="Logo Supplier",
            owner_user_id="user-1",
            is_system=False,
            logo_url=saved_logo_url,
        )
        self.assertIsNotNone(supplier)
        assert supplier is not None
        self.assertEqual(supplier["logo_url"], saved_logo_url)

        saved_file = self.upload_root / Path(saved_logo_url).name
        self.assertTrue(saved_file.exists())

    def test_invalid_file_type_is_rejected(self) -> None:
        app = self._build_app()

        with patch.object(upload_service, "SUPPLIER_LOGO_UPLOAD_ROOT", self.upload_root):
            with patch.object(catalog_route, "EntitlementService", _AllowedEntitlementService):
                with TestClient(app) as client:
                    response = client.post(
                        "/catalog/suppliers/logo",
                        headers={"Authorization": "Bearer token"},
                        files={"file": ("supplier-logo.txt", b"plain text", "text/plain")},
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
                CREATE TABLE users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    logo_url TEXT,
                    owner_user_id TEXT,
                    is_system INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "INSERT INTO users (id, email) VALUES (?, ?)",
                ("user-1", "user@example.com"),
            )
            connection.commit()


if __name__ == "__main__":
    unittest.main()
