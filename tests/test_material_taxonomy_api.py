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
from database.base import Base
from database.models import audit_log  # noqa: F401
from database.models import catalog_item  # noqa: F401
from database.models import entitlement_feature  # noqa: F401
from database.models import fitting  # noqa: F401
from database.models import fitting_hole_service_rule  # noqa: F401
from database.models import fitting_image  # noqa: F401
from database.models import material  # noqa: F401
from database.models import material_edge  # noqa: F401
from database.models import material_edge_price  # noqa: F401
from database.models import material_import_job  # noqa: F401
from database.models import material_price  # noqa: F401
from database.models.material import MaterialModel
from database.models import material_taxonomy  # noqa: F401
from database.models import material_user_link  # noqa: F401
from database.models import plan_entitlement  # noqa: F401
from database.models import project  # noqa: F401
from database.models import project_scan_session  # noqa: F401
from database.models import project_version  # noqa: F401
from database.models import registration_identity  # noqa: F401
from database.models import service_catalog_item  # noqa: F401
from database.models import service_drilling_rule  # noqa: F401
from database.models import user  # noqa: F401
from database.models.user import UserModel
from database.models import user_change_request  # noqa: F401
from database.models import user_service_catalog_price  # noqa: F401
from database.repositories import inventory_repository
from database.repositories import material_taxonomy_repository
from services import upload_service


class _AllowedMaterialTaxonomyEntitlementService:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def has_feature(self, current_user, feature_key: str) -> bool:
        return feature_key in {"materials.view", "materials.edit", "materials.create", "materials.delete"}

    def get_limit(self, current_user, feature_key: str):
        return SimpleNamespace(
            limit_value=None,
            status="unlimited",
        )


class _ViewOnlyMaterialTaxonomyEntitlementService:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def has_feature(self, current_user, feature_key: str) -> bool:
        return feature_key == "materials.view"

    def get_limit(self, current_user, feature_key: str):
        return SimpleNamespace(
            limit_value=None,
            status="unlimited",
        )


class MaterialTaxonomyApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database_path = f"{self._tmpdir.name}/materials.db"
        self.engine = create_engine(
            f"sqlite:///{self.database_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self._original_session_local = material_taxonomy_repository.SessionLocal
        self._original_inventory_session_local = inventory_repository.SessionLocal
        material_taxonomy_repository.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        inventory_repository.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def tearDown(self) -> None:
        material_taxonomy_repository.SessionLocal = self._original_session_local
        inventory_repository.SessionLocal = self._original_inventory_session_local
        self.engine.dispose()
        self._tmpdir.cleanup()

    def test_admin_can_manage_material_taxonomy_and_seed_alias_rows(self) -> None:
        app = self._build_app(role="admin")

        with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
            with TestClient(app) as client:
                category_response = client.post(
                    "/catalog/material-categories",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "code": "sheet_materials",
                        "name": "Листові матеріали",
                        "description": "Тестовий опис",
                        "image_url": "https://example.com/category.jpg",
                        "sort_order": 10,
                        "is_active": True,
                        "is_system": True,
                    },
                )
                self.assertEqual(category_response.status_code, 200)
                self.assertTrue(category_response.json()["success"])
                category_id = category_response.json()["item"]["id"]
                self.assertEqual(category_response.json()["item"]["description"], "Тестовий опис")
                self.assertEqual(category_response.json()["item"]["image_url"], "https://example.com/category.jpg")

                list_response = client.get(
                    "/catalog/material-categories",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(list_response.status_code, 200)
                self.assertTrue(list_response.json()["success"])
                self.assertTrue(any(item["code"] == "sheet_materials" for item in list_response.json()["items"]))

                update_category_response = client.patch(
                    f"/catalog/material-categories/{category_id}",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "code": "sheet_materials",
                        "name": "Листові матеріали",
                        "description": "Оновлений опис",
                        "image_url": "https://example.com/category-2.jpg",
                        "sort_order": 20,
                        "is_active": False,
                    },
                )
                self.assertEqual(update_category_response.status_code, 200)
                self.assertFalse(update_category_response.json()["item"]["is_active"])
                self.assertEqual(update_category_response.json()["item"]["description"], "Оновлений опис")
                self.assertEqual(update_category_response.json()["item"]["image_url"], "https://example.com/category-2.jpg")

                active_only_response = client.get(
                    "/catalog/material-categories",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertTrue(all(item["is_active"] for item in active_only_response.json()["items"]))

                all_categories_response = client.get(
                    "/catalog/material-categories?active_only=false",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertTrue(any(item["code"] == "sheet_materials" for item in all_categories_response.json()["items"]))

                manufacturer_response = client.post(
                    "/catalog/material-manufacturers",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "name": "Kronospan",
                        "website_url": "https://kronospan.com",
                        "is_active": True,
                        "is_system": True,
                    },
                )
                self.assertEqual(manufacturer_response.status_code, 200)
                manufacturer_payload = manufacturer_response.json()
                self.assertTrue(manufacturer_payload["success"])
                self.assertEqual(manufacturer_payload["item"]["code"], "kronospan")
                self.assertIsNone(manufacturer_payload["item"]["owner_user_id"])
                manufacturer_id = manufacturer_payload["item"]["id"]

                private_manufacturer_response = client.post(
                    "/catalog/material-manufacturers",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "name": "Kronospan Private",
                        "website_url": "https://kronospan-private.example",
                        "is_active": True,
                        "is_system": False,
                    },
                )
                self.assertEqual(private_manufacturer_response.status_code, 200)
                private_manufacturer_payload = private_manufacturer_response.json()
                self.assertTrue(private_manufacturer_payload["success"])
                self.assertEqual(private_manufacturer_payload["item"]["owner_user_id"], "user-1")
                self.assertFalse(private_manufacturer_payload["item"]["is_system"])
                private_manufacturer_id = private_manufacturer_payload["item"]["id"]

                with sqlite3.connect(self.database_path) as connection:
                    alias_count = connection.execute(
                        "SELECT COUNT(*) FROM material_manufacturer_aliases WHERE manufacturer_id = ?",
                        (manufacturer_id,),
                    ).fetchone()[0]
                self.assertEqual(alias_count, 1)

                png_buffer = BytesIO()
                Image.new("RGBA", (1, 1), (255, 0, 0, 255)).save(png_buffer, format="PNG")
                png_bytes = png_buffer.getvalue()

                with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as uploads_dir:
                    with patch.object(upload_service, "MATERIAL_MANUFACTURER_LOGO_UPLOAD_ROOT", Path(uploads_dir)):
                        upload_response = client.post(
                            "/catalog/material-manufacturers/logo",
                            headers={"Authorization": "Bearer token"},
                            files={"file": ("manufacturer.png", png_bytes, "image/png")},
                        )

                self.assertEqual(upload_response.status_code, 200)
                upload_payload = upload_response.json()
                self.assertTrue(upload_payload["success"])
                self.assertTrue(upload_payload["logo_url"].startswith("/uploads/material-manufacturer-logos/"))

                list_manufacturers_response = client.get(
                    "/catalog/material-manufacturers?active_only=false",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(list_manufacturers_response.status_code, 200)
                list_manufacturers_payload = list_manufacturers_response.json()
                self.assertTrue(any(item["name"] == "Kronospan" for item in list_manufacturers_payload["items"]))
                self.assertTrue(any(item["name"] == "Kronospan Private" for item in list_manufacturers_payload["items"]))

                update_manufacturer_response = client.patch(
                    f"/catalog/material-manufacturers/{manufacturer_id}",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "name": "Kronospan Updated",
                        "website_url": "https://kronospan.example",
                        "is_active": False,
                    },
                )
                self.assertEqual(update_manufacturer_response.status_code, 200)
                self.assertFalse(update_manufacturer_response.json()["item"]["is_active"])
                self.assertEqual(update_manufacturer_response.json()["item"]["name"], "Kronospan Updated")

                active_manufacturers_response = client.get(
                    "/catalog/material-manufacturers",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertTrue(
                    all(item["is_active"] for item in active_manufacturers_response.json()["items"]),
                )

                inactive_visible_response = client.get(
                    "/catalog/material-manufacturers?active_only=false",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertTrue(any(item["name"] == "Kronospan Updated" for item in inactive_visible_response.json()["items"]))
                self.assertTrue(any(item["name"] == "Kronospan Private" for item in inactive_visible_response.json()["items"]))

    def test_non_admin_sees_system_and_own_categories_only(self) -> None:
        app = self._build_app(role="free")

        system_category = material_taxonomy_repository.create_material_category(
            code="system_category",
            name="Системна категорія",
            sort_order=1,
            is_active=True,
            is_system=True,
        )
        self.assertIsNotNone(system_category)

        foreign_category = material_taxonomy_repository.create_material_category(
            code="foreign_category",
            name="Чужа категорія",
            owner_user_id="user-2",
            sort_order=2,
            is_active=True,
            is_system=False,
        )
        self.assertIsNotNone(foreign_category)

        with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
            with TestClient(app) as client:
                own_first_response = client.post(
                    "/catalog/material-categories",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "name": "Моя категорія",
                        "description": "Власна",
                        "image_url": "https://example.com/own.png",
                        "is_active": True,
                    },
                )
                self.assertEqual(own_first_response.status_code, 200)
                own_first_payload = own_first_response.json()
                self.assertTrue(own_first_payload["success"])
                self.assertEqual(own_first_payload["item"]["owner_user_id"], "user-1")
                self.assertFalse(own_first_payload["item"]["is_system"])
                self.assertTrue(own_first_payload["item"]["code"])

                own_second_response = client.post(
                    "/catalog/material-categories",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "name": "Моя категорія",
                        "description": "Власна 2",
                        "is_active": True,
                    },
                )
                self.assertEqual(own_second_response.status_code, 200)
                own_second_payload = own_second_response.json()
                self.assertTrue(own_second_payload["success"])
                self.assertNotEqual(own_first_payload["item"]["code"], own_second_payload["item"]["code"])

                list_response = client.get(
                    "/catalog/material-categories?active_only=false",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(list_response.status_code, 200)
                codes = [item["code"] for item in list_response.json()["items"]]
                self.assertIn(system_category["code"], codes)
                self.assertIn(own_first_payload["item"]["code"], codes)
                self.assertIn(own_second_payload["item"]["code"], codes)
                self.assertNotIn(foreign_category["code"], codes)

                foreign_lookup = client.get(
                    f"/catalog/material-categories/{foreign_category['id']}",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(foreign_lookup.status_code, 404)

                materials_response = client.get(
                    "/catalog/materials",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(materials_response.status_code, 200)
                materials_payload = materials_response.json()
                category_codes = [item["code"] for item in materials_payload["categories"]]
                self.assertIn(system_category["code"], category_codes)
                self.assertIn(own_first_payload["item"]["code"], category_codes)
                self.assertNotIn(foreign_category["code"], category_codes)

    def test_non_admin_sees_system_and_own_material_manufacturers_only(self) -> None:
        app = self._build_app(role="free")

        owner_session = material_taxonomy_repository.SessionLocal()
        try:
            owner_session.add(
                UserModel(
                    id="user-2",
                    email="foreign@example.com",
                    username="foreign.owner",
                    password_hash="hash",
                    role="free",
                ),
            )
            owner_session.commit()
        finally:
            owner_session.close()

        system_manufacturer = material_taxonomy_repository.create_material_manufacturer(
            name="System Manufacturer",
            website_url="https://system.example",
            is_active=True,
            is_system=True,
        )
        self.assertIsNotNone(system_manufacturer)

        foreign_manufacturer = material_taxonomy_repository.create_material_manufacturer(
            name="Foreign Manufacturer",
            website_url="https://foreign.example",
            owner_user_id="user-2",
            is_active=True,
            is_system=False,
        )
        self.assertIsNotNone(foreign_manufacturer)

        with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
            with TestClient(app) as client:
                own_manufacturer_response = client.post(
                    "/catalog/material-manufacturers",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "name": "Own Manufacturer",
                        "website_url": "https://own.example",
                        "is_active": True,
                        "is_system": False,
                    },
                )
                self.assertEqual(own_manufacturer_response.status_code, 200)
                own_manufacturer_payload = own_manufacturer_response.json()
                self.assertTrue(own_manufacturer_payload["success"])
                self.assertEqual(own_manufacturer_payload["item"]["owner_user_id"], "user-1")
                self.assertFalse(own_manufacturer_payload["item"]["is_system"])

                list_response = client.get(
                    "/catalog/material-manufacturers?active_only=false",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(list_response.status_code, 200)
                payload = list_response.json()
                codes = [item["name"] for item in payload["items"]]
                self.assertIn(system_manufacturer["name"], codes)
                self.assertIn(own_manufacturer_payload["item"]["name"], codes)
                self.assertNotIn(foreign_manufacturer["name"], codes)

                foreign_lookup = client.get(
                    f"/catalog/material-manufacturers/{foreign_manufacturer['id']}",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(foreign_lookup.status_code, 404)

                system_update = client.patch(
                    f"/catalog/material-manufacturers/{system_manufacturer['id']}",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "name": system_manufacturer["name"],
                        "website_url": "https://system.example",
                        "is_active": False,
                    },
                )
                self.assertEqual(system_update.status_code, 403)

    def test_material_api_reads_and_preserves_manufacturer_id(self) -> None:
        app = self._build_app(role="free")

        manufacturer = material_taxonomy_repository.create_material_manufacturer(
            name="Kronospan",
            website_url="https://kronospan.com",
            is_active=True,
            is_system=True,
        )
        self.assertIsNotNone(manufacturer)
        manufacturer_id = manufacturer["id"]

        with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
            with TestClient(app) as client:
                create_response = client.post(
                    "/catalog/materials",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "article": "M-9001",
                        "name": "ДСП Kronospan K 086 PW",
                        "category": "dsp",
                        "city": "kyiv",
                        "price": 123.45,
                        "manufacturer_id": manufacturer_id,
                    },
                )
                self.assertEqual(create_response.status_code, 200)
                create_payload = create_response.json()
                self.assertTrue(create_payload["success"])
                self.assertEqual(create_payload["item"]["manufacturer_id"], manufacturer_id)
                self.assertEqual(create_payload["item"]["manufacturer_name"], "Kronospan")

                update_response = client.patch(
                    "/catalog/materials/M-9001",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "name": "ДСП Kronospan K 086 PW update",
                    },
                )
                self.assertEqual(update_response.status_code, 200)
                update_payload = update_response.json()
                self.assertTrue(update_payload["success"])
                self.assertEqual(update_payload["item"]["manufacturer_id"], manufacturer_id)
                self.assertEqual(update_payload["item"]["manufacturer_name"], "Kronospan")

                detail_response = client.get(
                    "/catalog/materials/M-9001",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(detail_response.status_code, 200)
                detail_payload = detail_response.json()
                self.assertTrue(detail_payload["success"])
                self.assertEqual(detail_payload["item"]["manufacturer_id"], manufacturer_id)
                self.assertEqual(detail_payload["item"]["manufacturer_name"], "Kronospan")

    def test_material_manufacturer_delete_requires_inactive_and_unused(self) -> None:
        app = self._build_app(role="admin")

        active_manufacturer = material_taxonomy_repository.create_material_manufacturer(
            name="Active Manufacturer",
            website_url="https://active.example",
            is_active=True,
            is_system=True,
        )
        self.assertIsNotNone(active_manufacturer)

        unused_inactive_manufacturer = material_taxonomy_repository.create_material_manufacturer(
            name="Inactive Unused Manufacturer",
            website_url="https://inactive-unused.example",
            is_active=False,
            is_system=True,
        )
        self.assertIsNotNone(unused_inactive_manufacturer)

        referenced_manufacturer = material_taxonomy_repository.create_material_manufacturer(
            name="Inactive Referenced Manufacturer",
            website_url="https://inactive-referenced.example",
            is_active=False,
            is_system=True,
        )
        self.assertIsNotNone(referenced_manufacturer)

        session_factory = material_taxonomy_repository.SessionLocal
        with session_factory() as session:
            session.add(
                MaterialModel(
                    article="M-DELETE-REF-1",
                    name="Referenced material",
                    category="dsp",
                    manufacturer_id=referenced_manufacturer["id"],
                    is_default=False,
                ),
            )
            session.commit()

        with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
            with TestClient(app) as client:
                active_delete_response = client.delete(
                    f"/catalog/material-manufacturers/{active_manufacturer['id']}",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(active_delete_response.status_code, 200)
                self.assertFalse(active_delete_response.json()["success"])
                self.assertIn("деактив", active_delete_response.json()["error"].lower())

                unused_delete_response = client.delete(
                    f"/catalog/material-manufacturers/{unused_inactive_manufacturer['id']}",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(unused_delete_response.status_code, 200)
                self.assertTrue(unused_delete_response.json()["success"])
                self.assertEqual(int(unused_delete_response.json()["item"]["id"]), unused_inactive_manufacturer["id"])

                referenced_delete_response = client.delete(
                    f"/catalog/material-manufacturers/{referenced_manufacturer['id']}",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(referenced_delete_response.status_code, 200)
                self.assertFalse(referenced_delete_response.json()["success"])
                self.assertIn("використовується", referenced_delete_response.json()["error"].lower())

        with session_factory() as session:
            self.assertIsNone(session.get(material_taxonomy_repository.MaterialManufacturerModel, unused_inactive_manufacturer["id"]))
            self.assertIsNotNone(session.get(material_taxonomy_repository.MaterialManufacturerModel, active_manufacturer["id"]))
            referenced_material = session.query(MaterialModel).filter(MaterialModel.article == "M-DELETE-REF-1").one_or_none()
            self.assertIsNotNone(referenced_material)
            self.assertEqual(int(referenced_material.manufacturer_id), referenced_manufacturer["id"])

    def test_admin_default_category_scope_excludes_private_categories(self) -> None:
        app = self._build_app(role="admin")

        system_category = material_taxonomy_repository.create_material_category(
            code="system_only_category",
            name="Системна категорія",
            sort_order=1,
            is_active=True,
            is_system=True,
        )
        self.assertIsNotNone(system_category)

        owner_session = material_taxonomy_repository.SessionLocal()
        try:
            owner_session.add(
                UserModel(
                    id="user-1",
                    email="owner@example.com",
                    username="owner.one",
                    password_hash="hash",
                    role="free",
                ),
            )
            owner_session.commit()
        finally:
            owner_session.close()

        private_category = material_taxonomy_repository.create_material_category(
            code="private_category",
            name="Приватна категорія",
            owner_user_id="user-1",
            sort_order=2,
            is_active=True,
            is_system=False,
        )
        self.assertIsNotNone(private_category)

        fallback_owner_session = material_taxonomy_repository.SessionLocal()
        try:
            fallback_owner_session.add(
                UserModel(
                    id="user-2",
                    email="fallback@example.com",
                    username=None,
                    password_hash="hash",
                    role="free",
                ),
            )
            fallback_owner_session.commit()
        finally:
            fallback_owner_session.close()

        fallback_category = material_taxonomy_repository.create_material_category(
            code="fallback_category",
            name="Категорія без логіна",
            owner_user_id="user-2",
            sort_order=3,
            is_active=True,
            is_system=False,
        )
        self.assertIsNotNone(fallback_category)

        with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
            with TestClient(app) as client:
                response = client.get(
                    "/catalog/material-categories",
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        codes = [item["code"] for item in payload["items"]]
        self.assertIn(system_category["code"], codes)
        self.assertNotIn(private_category["code"], codes)

        with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
            with TestClient(app) as client:
                private_scope_response = client.get(
                    "/catalog/material-categories?active_only=false&include_private_categories=true",
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(private_scope_response.status_code, 200)
        private_scope_payload = private_scope_response.json()
        private_scope_codes = [item["code"] for item in private_scope_payload["items"]]
        self.assertIn(system_category["code"], private_scope_codes)
        self.assertIn(private_category["code"], private_scope_codes)
        self.assertIn(fallback_category["code"], private_scope_codes)
        private_row = next(item for item in private_scope_payload["items"] if item["code"] == private_category["code"])
        self.assertEqual(private_row["owner_user_id"], "user-1")
        self.assertEqual(private_row["owner_display_name"], "owner.one")
        self.assertEqual(private_row["owner_login"], "owner.one")
        self.assertEqual(private_row["owner_email"], "owner@example.com")
        fallback_row = next(item for item in private_scope_payload["items"] if item["code"] == fallback_category["code"])
        self.assertEqual(fallback_row["owner_user_id"], "user-2")
        self.assertEqual(fallback_row["owner_display_name"], "fallback@example.com")
        self.assertIsNone(fallback_row["owner_login"])
        self.assertEqual(fallback_row["owner_email"], "fallback@example.com")

    def test_material_category_image_upload_uses_materials_permission_gate(self) -> None:
        app = self._build_app(role="free")
        png_buffer = BytesIO()
        Image.new("RGBA", (1, 1), (0, 255, 0, 255)).save(png_buffer, format="PNG")
        png_bytes = png_buffer.getvalue()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as uploads_dir:
            with patch.object(upload_service, "MATERIAL_CATEGORY_IMAGE_UPLOAD_ROOT", Path(uploads_dir)):
                with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
                    with TestClient(app) as client:
                        response = client.post(
                            "/catalog/material-categories/image",
                            headers={"Authorization": "Bearer token"},
                            files={"file": ("category.png", png_bytes, "image/png")},
                        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertTrue(payload["image_url"].startswith("/uploads/material-category-images/"))

    def test_material_category_image_upload_rejects_view_only_users(self) -> None:
        app = self._build_app(role="free")
        png_buffer = BytesIO()
        Image.new("RGBA", (1, 1), (0, 255, 0, 255)).save(png_buffer, format="PNG")
        png_bytes = png_buffer.getvalue()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as uploads_dir:
            with patch.object(upload_service, "MATERIAL_CATEGORY_IMAGE_UPLOAD_ROOT", Path(uploads_dir)):
                with patch.object(catalog_route, "EntitlementService", _ViewOnlyMaterialTaxonomyEntitlementService):
                    with TestClient(app) as client:
                        response = client.post(
                            "/catalog/material-categories/image",
                            headers={"Authorization": "Bearer token"},
                            files={"file": ("category.png", png_bytes, "image/png")},
                        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["detail"]["success"])
        self.assertEqual(response.json()["detail"]["error"], "Insufficient permissions")

    def test_non_admin_category_write_rules_follow_ownership_and_usage(self) -> None:
        app = self._build_app(role="free")

        own_category = material_taxonomy_repository.create_material_category(
            name="Редагована категорія",
            sort_order=3,
            is_active=True,
            is_system=False,
            owner_user_id="user-1",
        )
        self.assertIsNotNone(own_category)

        system_category = material_taxonomy_repository.create_material_category(
            code="system_editable",
            name="Системна для редагування",
            sort_order=4,
            is_active=True,
            is_system=True,
        )
        self.assertIsNotNone(system_category)

        used_category = material_taxonomy_repository.create_material_category(
            name="Категорія для використання",
            sort_order=5,
            is_active=True,
            is_system=False,
            owner_user_id="user-1",
        )
        self.assertIsNotNone(used_category)

        db_session = material_taxonomy_repository.SessionLocal()
        try:
            db_session.add(
                MaterialModel(
                    article="used-category-material",
                    category=used_category["code"],
                    is_default=False,
                ),
            )
            db_session.commit()
        finally:
            db_session.close()

        with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
            with TestClient(app) as client:
                create_system_response = client.post(
                    "/catalog/material-categories",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "name": "Спроба системної",
                        "is_system": True,
                    },
                )
                self.assertEqual(create_system_response.status_code, 403)

                update_own_response = client.patch(
                    f"/catalog/material-categories/{own_category['id']}",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "name": "Редагована категорія 2",
                        "is_active": False,
                    },
                )
                self.assertEqual(update_own_response.status_code, 200)
                self.assertEqual(update_own_response.json()["item"]["name"], "Редагована категорія 2")
                self.assertFalse(update_own_response.json()["item"]["is_active"])

                update_system_response = client.patch(
                    f"/catalog/material-categories/{system_category['id']}",
                    headers={"Authorization": "Bearer token"},
                    json={
                        "name": "Спроба змінити системну",
                    },
                )
                self.assertEqual(update_system_response.status_code, 403)

                delete_own_response = client.delete(
                    f"/catalog/material-categories/{own_category['id']}",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(delete_own_response.status_code, 200)
                self.assertTrue(delete_own_response.json()["success"])

                delete_used_response = client.delete(
                    f"/catalog/material-categories/{used_category['id']}",
                    headers={"Authorization": "Bearer token"},
                )
                self.assertEqual(delete_used_response.status_code, 400)
                self.assertIn("матеріали", delete_used_response.json()["detail"]["error"])

    def test_admin_can_upload_material_category_image_and_validation_applies(self) -> None:
        app = self._build_app(role="admin")
        png_buffer = BytesIO()
        Image.new("RGBA", (1, 1), (255, 0, 0, 255)).save(png_buffer, format="PNG")
        png_bytes = png_buffer.getvalue()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as uploads_dir:
            with patch.object(upload_service, "MATERIAL_CATEGORY_IMAGE_UPLOAD_ROOT", Path(uploads_dir)):
                with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
                    with TestClient(app) as client:
                        response = client.post(
                            "/catalog/material-categories/image",
                            headers={"Authorization": "Bearer token"},
                            files={"file": ("category.png", png_bytes, "image/png")},
                        )

                        self.assertEqual(response.status_code, 200)
                        payload = response.json()
                        self.assertTrue(payload["success"])
                        self.assertTrue(payload["image_url"].startswith("/uploads/material-category-images/"))
                        self.assertTrue(any(Path(uploads_dir).iterdir()))

                        invalid_response = client.post(
                            "/catalog/material-categories/image",
                            headers={"Authorization": "Bearer token"},
                            files={"file": ("category.txt", b"not an image", "text/plain")},
                        )

                        self.assertEqual(invalid_response.status_code, 400)
                        self.assertFalse(invalid_response.json()["detail"]["success"])
                        self.assertIn("Unsupported file type", invalid_response.json()["detail"]["error"])

    def test_material_catalog_route_uses_material_taxonomy_categories(self) -> None:
        app = self._build_app(role="admin")

        for code, name, sort_order in [
            ("dsp", "ДСП", 0),
            ("mdf", "МДФ", 1),
            ("hdf", "ДВП / HDF", 2),
            ("plywood", "Фанера", 3),
            ("countertop", "Стільниці", 4),
            ("compact_board", "Компакт-плита", 5),
            ("facade_material", "Фасадні матеріали", 6),
        ]:
            created = material_taxonomy_repository.create_material_category(
                code=code,
                name=name,
                description=f"Опис {code}",
                sort_order=sort_order,
                is_active=True,
                is_system=True,
            )
            self.assertIsNotNone(created)

        with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
            with TestClient(app) as client:
                response = client.get(
                    "/catalog/materials",
                    headers={"Authorization": "Bearer token"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(
            [item["code"] for item in payload["categories"]],
            [
                "dsp",
                "mdf",
                "hdf",
                "plywood",
                "countertop",
                "compact_board",
                "facade_material",
            ],
        )
        self.assertNotIn("edge_04", [item["code"] for item in payload["categories"]])
        self.assertNotIn("edge_08", [item["code"] for item in payload["categories"]])
        self.assertNotIn("handles", [item["code"] for item in payload["categories"]])
        self.assertNotIn("slides_basic", [item["code"] for item in payload["categories"]])
        self.assertNotIn("slides_softclose", [item["code"] for item in payload["categories"]])
        self.assertTrue(all("description" in item for item in payload["categories"]))
        self.assertTrue(all("image_url" in item for item in payload["categories"]))

    def test_material_taxonomy_write_routes_require_admin(self) -> None:
        app = self._build_app(role="free")

        with patch.object(catalog_route, "EntitlementService", _AllowedMaterialTaxonomyEntitlementService):
            with TestClient(app) as client:
                response = client.post(
                    "/catalog/material-manufacturers",
                    headers={"Authorization": "Bearer token"},
                    json={"name": "Blocked manufacturer"},
                )

        self.assertEqual(response.status_code, 403)

    def _build_app(self, *, role: str) -> FastAPI:
        app = FastAPI()
        app.include_router(catalog_route.router, prefix="/catalog")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(
            id="user-1",
            role=role,
            email="user@example.com",
            city="kyiv",
        )
        return app


if __name__ == "__main__":
    unittest.main()
