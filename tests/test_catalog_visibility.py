from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from hashlib import sha256
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from api.dependencies import auth as auth_dependencies
from api.routes import catalog
from api.routes import fitting_holes as fitting_holes_route
from database.base import Base
from database.models import audit_log  # noqa: F401
from database.models import catalog_item  # noqa: F401
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models import entitlement_feature  # noqa: F401
from database.models.fitting import (
    FittingCategoryModel,
    FittingHolePointModel,
    FittingHoleTemplateModel,
    FittingManufacturerModel,
    FittingModel,
    FittingProductModel,
    FittingSupplierOfferModel,
    SupplierModel,
)
from database.models import fitting_hole_service_rule  # noqa: F401
from database.models import fitting_image  # noqa: F401
from database.models.fitting_image import FittingImageModel
from database.models.material import MaterialModel
from database.models import material_edge  # noqa: F401
from database.models import material_edge_price  # noqa: F401
from database.models import material_import_job  # noqa: F401
from database.models import material_price  # noqa: F401
from database.models import material_user_link  # noqa: F401
from database.models.material_user_link import MaterialUserLinkModel
from database.models import plan_entitlement  # noqa: F401
from database.models.plan_entitlement import PlanEntitlementModel
from database.models import project  # noqa: F401
from database.models import project_scan_session  # noqa: F401
from database.models import project_version  # noqa: F401
from database.models import registration_identity  # noqa: F401
from database.models import service_catalog_item  # noqa: F401
from database.models import service_drilling_rule  # noqa: F401
from database.models import user  # noqa: F401
from database.models import user_change_request  # noqa: F401
from database.models import user_service_catalog_price  # noqa: F401
from database.repositories import inventory_repository
from database.repositories import material_import_job_repository
from database.repositories import fitting_hole_service_rule_repository
import services.entitlement_service as entitlement_service
import services.fitting_holes_service as fitting_holes_service
from services import fitting_source_parser
from services.mounting_node_service import MountingNodeService
from services.fitting_image_gallery_service import PreparedFittingGalleryImage


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@dataclass
class UserStub:
    id: str
    email: str
    role: str
    city: str = "kyiv"
    trial_started_at: datetime | None = None
    trial_ends_at: datetime | None = None


class CatalogVisibilityTests(unittest.TestCase):
    @staticmethod
    def _set_material_bool_entitlement(
        session,
        feature_key: str,
        plan_code: str,
        enabled: bool,
    ) -> None:
        feature = (
            session.query(EntitlementFeatureModel)
            .filter(EntitlementFeatureModel.feature_key == feature_key)
            .one()
        )
        entitlement = (
            session.query(PlanEntitlementModel)
            .filter(
                PlanEntitlementModel.feature_id == feature.id,
                PlanEntitlementModel.plan_code == plan_code,
            )
            .one()
        )
        entitlement.bool_value = enabled
        entitlement.is_unlimited = False
        entitlement.integer_value = None
        entitlement.decimal_value = None
        entitlement.text_value = None
        entitlement.is_not_applicable = False

    @staticmethod
    def _set_fitting_bool_entitlement(
        session,
        feature_key: str,
        plan_code: str,
        enabled: bool,
    ) -> None:
        feature = (
            session.query(EntitlementFeatureModel)
            .filter(EntitlementFeatureModel.feature_key == feature_key)
            .one()
        )
        entitlement = (
            session.query(PlanEntitlementModel)
            .filter(
                PlanEntitlementModel.feature_id == feature.id,
                PlanEntitlementModel.plan_code == plan_code,
            )
            .one()
        )
        entitlement.bool_value = enabled
        entitlement.is_unlimited = False
        entitlement.integer_value = None
        entitlement.decimal_value = None
        entitlement.text_value = None
        entitlement.is_not_applicable = False

    @staticmethod
    def _fake_gallery_image():
        return PreparedFittingGalleryImage(
            sort_order=0,
            is_primary=True,
            source_url="https://cdn.example.com/fittings/p1.jpg",
            image_bytes=b"fake-image-bytes",
            content_type="image/png",
            sha256=sha256(b"fake-image-bytes").hexdigest(),
        )

    @staticmethod
    def _make_png_bytes(color: tuple[int, int, int]) -> bytes:
        buffer = BytesIO()
        Image.new("RGB", (120, 120), color).save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def _remove_material_entitlement(
        session,
        feature_key: str,
        plan_code: str,
    ) -> None:
        feature = (
            session.query(EntitlementFeatureModel)
            .filter(EntitlementFeatureModel.feature_key == feature_key)
            .one()
        )
        entitlement = (
            session.query(PlanEntitlementModel)
            .filter(
                PlanEntitlementModel.feature_id == feature.id,
                PlanEntitlementModel.plan_code == plan_code,
            )
            .one()
        )
        session.delete(entitlement)

    @staticmethod
    def _create_material_import_job(
        session,
        *,
        job_id: int,
        article: str,
        city: str,
        owner_user_id: str | None,
        status: str = "success",
    ) -> None:
        session.add(
            material_import_job.MaterialImportJobModel(
                id=job_id,
                article=article,
                category="dsp",
                city=city,
                owner_user_id=owner_user_id,
                status=status,
                attempt_count=1,
                max_attempts=5,
                next_retry_at=None,
                last_error=None,
                last_strategy=None,
                last_source_url=None,
                preferred_url=None,
                debug_trace=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                completed_at=datetime.utcnow() if status == "success" else None,
            )
        )

    def test_system_materials_and_fittings_are_visible_to_trial_and_free_users(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, _client):
                with session_factory() as session:
                    session.add_all(
                        [
                            MaterialModel(
                                article="SYS-MAT",
                                name="System Material",
                                category="dsp",
                                owner_user_id=None,
                                is_default=True,
                            ),
                            MaterialModel(
                                article="PRIVATE-MAT",
                                name="Private Material",
                                category="dsp",
                                owner_user_id="owner-1",
                                is_default=False,
                            ),
                            FittingModel(
                                name="System Fitting",
                                fitting_type="drawer_slides",
                                fitting_group="fittings",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                            ),
                            FittingModel(
                                name="Private Fitting",
                                fitting_type="drawer_slides",
                                fitting_group="fittings",
                                owner_user_id="owner-1",
                                is_system=False,
                                is_active=True,
                            ),
                        ]
                    )
                    session.commit()

                for role in ("trial", "free", "pro", "premium", "business"):
                    materials = inventory_repository.list_materials(
                        viewer_user_id=f"{role}-user",
                        viewer_role=role,
                    )
                    fittings = inventory_repository.list_fittings(
                        viewer_user_id=f"{role}-user",
                        viewer_role=role,
                    )

                    self.assertIn("SYS-MAT", {item["article"] for item in materials})
                    self.assertNotIn("PRIVATE-MAT", {item["article"] for item in materials})
                    self.assertIn("System Fitting", {item["name"] for item in fittings})
                    self.assertNotIn("Private Fitting", {item["name"] for item in fittings})
                    self.assertIn("technical_product_id", fittings[0])

    def test_admin_can_filter_materials_by_ownership_scope_without_mixing_types(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add_all(
                        [
                            MaterialModel(
                                article="ADMIN-SYS",
                                name="Admin System",
                                category="dsp",
                                owner_user_id=None,
                                is_default=True,
                            ),
                            MaterialModel(
                                article="ADMIN-MINE",
                                name="Admin Private",
                                category="dsp",
                                owner_user_id="admin-user",
                                is_default=False,
                            ),
                            MaterialModel(
                                article="USER-PRIVATE",
                                name="User Private",
                                category="dsp",
                                owner_user_id="other-user",
                                is_default=False,
                            ),
                            MaterialModel(
                                article="ORPHAN",
                                name="Orphan Material",
                                category="dsp",
                                owner_user_id=None,
                                is_default=False,
                            ),
                        ]
                    )
                    session.commit()

                system_response = client.get(
                    "/catalog/materials?ownership_scope=system",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(system_response.status_code, 200)
                system_articles = {item["article"] for item in system_response.json()["items"]}
                self.assertEqual(system_articles, {"ADMIN-SYS"})
                self.assertNotIn("ORPHAN", system_articles)

                mine_response = client.get(
                    "/catalog/materials?ownership_scope=mine",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(mine_response.status_code, 200)
                mine_articles = {item["article"] for item in mine_response.json()["items"]}
                self.assertEqual(mine_articles, {"ADMIN-MINE"})

                users_response = client.get(
                    "/catalog/materials?ownership_scope=users",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(users_response.status_code, 200)
                users_articles = {item["article"] for item in users_response.json()["items"]}
                self.assertEqual(users_articles, {"USER-PRIVATE"})

                all_response = client.get(
                    "/catalog/materials?ownership_scope=all",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(all_response.status_code, 200)
                all_articles = {item["article"] for item in all_response.json()["items"]}
                self.assertEqual(all_articles, {"ADMIN-SYS", "ADMIN-MINE", "USER-PRIVATE", "ORPHAN"})

    def test_admin_can_filter_fittings_by_ownership_scope_and_see_owner_metadata(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add_all(
                        [
                            UserModel(
                                id="admin-user",
                                email="admin@example.com",
                                username="admin.operator",
                                password_hash="hash",
                                role="admin",
                            ),
                            UserModel(
                                id="owner-1",
                                email="owner.one@example.com",
                                username="owner.one",
                                password_hash="hash",
                                role="trial",
                            ),
                            UserModel(
                                id="other-user",
                                email="other@example.com",
                                username="other.user",
                                password_hash="hash",
                                role="trial",
                            ),
                        ]
                    )
                    session.add_all(
                        [
                            FittingModel(
                                name="System Fitting",
                                fitting_type="drawer_slides",
                                fitting_group="fittings",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                            ),
                            FittingModel(
                                name="Admin Private Fitting",
                                fitting_type="drawer_slides",
                                fitting_group="fittings",
                                owner_user_id="admin-user",
                                is_system=False,
                                is_active=True,
                            ),
                            FittingModel(
                                name="Foreign Private Fitting",
                                fitting_type="drawer_slides",
                                fitting_group="fittings",
                                owner_user_id="owner-1",
                                is_system=False,
                                is_active=True,
                            ),
                            FittingModel(
                                name="Orphan Fitting",
                                fitting_type="drawer_slides",
                                fitting_group="fittings",
                                owner_user_id=None,
                                is_system=False,
                                is_active=True,
                            ),
                        ]
                    )
                    session.commit()

                system_response = client.get(
                    "/catalog/fittings?ownership_scope=system",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(system_response.status_code, 200)
                system_names = {item["name"] for item in system_response.json()["items"]}
                self.assertEqual(system_names, {"System Fitting"})

                mine_response = client.get(
                    "/catalog/fittings?ownership_scope=mine",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(mine_response.status_code, 200)
                mine_names = {item["name"] for item in mine_response.json()["items"]}
                self.assertEqual(mine_names, {"Admin Private Fitting"})

                users_response = client.get(
                    "/catalog/fittings?ownership_scope=users",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(users_response.status_code, 200)
                users_names = {item["name"] for item in users_response.json()["items"]}
                self.assertEqual(users_names, {"Foreign Private Fitting"})

                all_response = client.get(
                    "/catalog/fittings?ownership_scope=all",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(all_response.status_code, 200)
                all_items = all_response.json()["items"]
                all_names = {item["name"] for item in all_items}
                self.assertEqual(
                    all_names,
                    {"System Fitting", "Admin Private Fitting", "Foreign Private Fitting", "Orphan Fitting"},
                )
                private_item = next(item for item in all_items if item["name"] == "Foreign Private Fitting")
                self.assertEqual(private_item["owner_user_id"], "owner-1")
                self.assertEqual(private_item["owner_display_name"], "owner.one")
                self.assertEqual(private_item["owner_login"], "owner.one")
                self.assertEqual(private_item["owner_email"], "owner.one@example.com")

                detail_response = client.get(
                    f"/catalog/fittings/{private_item['id']}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(detail_response.status_code, 200)
                detail_item = detail_response.json()["item"]
                self.assertEqual(detail_item["owner_user_id"], "owner-1")
                self.assertEqual(detail_item["owner_display_name"], "owner.one")
                self.assertEqual(detail_item["owner_login"], "owner.one")
                self.assertEqual(detail_item["owner_email"], "owner.one@example.com")

    def test_admin_material_owners_endpoint_deduplicates_and_hides_private_data_from_non_admins(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add_all(
                        [
                            UserModel(
                                id="owner-1",
                                email="owner.one@example.com",
                                username="owner.one",
                                password_hash="hash",
                                role="trial",
                            ),
                            UserModel(
                                id="collaborator-1",
                                email="collab@example.com",
                                username=None,
                                password_hash="hash",
                                role="free",
                            ),
                            MaterialModel(
                                article="OWNED-MAT",
                                name="Owned Material",
                                category="dsp",
                                owner_user_id="owner-1",
                                is_default=False,
                            ),
                            MaterialUserLinkModel(
                                material_article="OWNED-MAT",
                                user_id="owner-1",
                            ),
                            MaterialUserLinkModel(
                                material_article="OWNED-MAT",
                                user_id="collaborator-1",
                            ),
                        ]
                    )
                    session.commit()

                admin_response = client.get(
                    "/catalog/materials/OWNED-MAT/owners",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(admin_response.status_code, 200)
                self.assertTrue(admin_response.json()["success"])
                self.assertEqual(admin_response.json()["owners_count"], 2)
                self.assertEqual(
                    [owner["id"] for owner in admin_response.json()["owners"]],
                    ["owner-1", "collaborator-1"],
                )
                self.assertEqual(admin_response.json()["owners"][0]["display_name"], "owner.one")
                self.assertEqual(admin_response.json()["owners"][0]["email"], "owner.one@example.com")
                self.assertEqual(admin_response.json()["owners"][1]["login"], "collab")

                trial_response = client.get(
                    "/catalog/materials/OWNED-MAT/owners",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(trial_response.status_code, 403)

    def test_admin_material_owners_endpoint_returns_empty_list_for_material_without_owners(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="ORPHAN-OWNERS",
                            name="Orphan Owners Material",
                            category="dsp",
                            owner_user_id=None,
                            is_default=False,
                        )
                    )
                    session.commit()

                response = client.get(
                    "/catalog/materials/ORPHAN-OWNERS/owners",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["owners_count"], 0)
                self.assertEqual(payload["owners"], [])

    def test_trial_user_can_open_system_material_and_fitting_details(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    system_material = MaterialModel(
                        article="SYS-MAT",
                        name="System Material",
                        category="dsp",
                        owner_user_id=None,
                        is_default=True,
                    )
                    system_fitting = FittingModel(
                        name="System Fitting",
                        fitting_type="drawer_slides",
                        fitting_group="fittings",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                        image_cached_bytes=b"fitting-bytes",
                        image_cached_content_type="image/png",
                    )
                    session.add_all([system_material, system_fitting])
                    session.commit()
                    fitting_id = str(system_fitting.id)

                response = client.get(
                    "/catalog/materials/SYS-MAT",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["success"])
                self.assertEqual(response.json()["item"]["article"], "SYS-MAT")

                response = client.get(
                    f"/catalog/fittings/{fitting_id}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["success"])
                self.assertEqual(response.json()["item"]["name"], "System Fitting")

    def test_private_fitting_detail_and_image_are_hidden_by_id(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    private_fitting = FittingModel(
                        name="Private Fitting",
                        fitting_type="drawer_slides",
                        fitting_group="fittings",
                        owner_user_id="owner-1",
                        is_system=False,
                        is_active=True,
                        image_cached_bytes=b"private-bytes",
                        image_cached_content_type="image/png",
                    )
                    session.add(private_fitting)
                    session.commit()
                    fitting_id = str(private_fitting.id)

                detail_response = client.get(
                    f"/catalog/fittings/{fitting_id}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(detail_response.status_code, 404)

                image_response = client.get(
                    f"/catalog/fittings/{fitting_id}/image",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(image_response.status_code, 404)

    def test_trial_user_can_create_update_and_delete_own_material(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                rejected = client.post(
                    "/catalog/materials",
                    json={
                        "article": "TRIAL-MAT-SYSTEM",
                        "name": "Rejected System Material",
                        "category": "dsp",
                        "city": "kyiv",
                        "price": 12.5,
                        "is_default": True,
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(rejected.status_code, 200)
                self.assertFalse(rejected.json()["success"])

                created = client.post(
                    "/catalog/materials",
                    json={
                        "article": "TRIAL-MAT",
                        "name": "Trial Material",
                        "category": "dsp",
                        "city": "kyiv",
                        "price": 12.5,
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(created.status_code, 200)
                self.assertTrue(created.json()["success"])
                article = created.json()["item"]["article"]

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == article).one()
                    self.assertEqual(material.owner_user_id, "trial-user")
                    self.assertFalse(material.is_default)

                detail = client.get(
                    f"/catalog/materials/{article}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(detail.status_code, 200)
                self.assertTrue(detail.json()["success"])
                self.assertEqual(detail.json()["item"]["article"], article)

                updated = client.post(
                    "/catalog/materials",
                    json={
                        "article": article,
                        "name": "Trial Material Updated",
                        "category": "dsp",
                        "city": "kyiv",
                        "price": 13.5,
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(updated.status_code, 200)
                self.assertTrue(updated.json()["success"])

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == article).one()
                    self.assertEqual(material.name, "Trial Material Updated")
                    self.assertFalse(material.is_default)

                deleted = client.delete(
                    f"/catalog/materials/{article}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(deleted.status_code, 200)
                self.assertTrue(deleted.json()["success"])

                with session_factory() as session:
                    self.assertIsNone(session.query(MaterialModel).filter(MaterialModel.article == article).one_or_none())

    def test_material_view_entitlement_blocks_list_and_detail_access(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._set_material_bool_entitlement(session, "materials.view", "trial", False)
                    session.add(
                        MaterialModel(
                            article="VISIBLE-MAT",
                            name="Visible Material",
                            category="dsp",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    session.commit()

                list_response = client.get(
                    "/catalog/materials",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(list_response.status_code, 403)

                detail_response = client.get(
                    "/catalog/materials/VISIBLE-MAT",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(detail_response.status_code, 403)

    def test_material_create_entitlement_blocks_new_material_creation(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._set_material_bool_entitlement(session, "materials.create", "trial", False)
                    session.commit()

                response = client.post(
                    "/catalog/materials",
                    json={
                        "article": "NO-CREATE-MAT",
                        "name": "No Create Material",
                        "category": "dsp",
                        "city": "kyiv",
                        "price": 12.5,
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 403)

    def test_material_edit_entitlement_blocks_owned_material_update(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._set_material_bool_entitlement(session, "materials.edit", "trial", False)
                    session.add(
                        MaterialModel(
                            article="OWNED-EDIT-MAT",
                            name="Owned Edit Material",
                            category="dsp",
                            owner_user_id="trial-user",
                            is_default=False,
                        )
                    )
                    session.commit()

                response = client.post(
                    "/catalog/materials",
                    json={
                        "article": "OWNED-EDIT-MAT",
                        "name": "Owned Edit Material Updated",
                        "category": "dsp",
                        "city": "kyiv",
                        "price": 13.5,
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 403)

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "OWNED-EDIT-MAT").one()
                    self.assertEqual(material.name, "Owned Edit Material")

    def test_material_update_endpoint_updates_own_private_material_without_changing_quota_or_row_count(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="OWNED-UPD-MAT",
                            name="Owned Update Material",
                            description="Original description",
                            color="Oak",
                            dimensions="2800 x 2070",
                            thickness="18",
                            category="dsp",
                            owner_user_id="trial-user",
                            is_default=False,
                        )
                    )
                    session.add(
                        material_price.MaterialPriceModel(
                            article="OWNED-UPD-MAT",
                            city="kyiv",
                            price=12.5,
                        )
                    )
                    session.add(
                        MaterialUserLinkModel(
                            material_article="OWNED-UPD-MAT",
                            user_id="trial-user",
                            source="manual",
                            product_type="dsp",
                        )
                    )
                    session.commit()

                with session_factory() as session:
                    material_before = session.query(MaterialModel).filter(MaterialModel.article == "OWNED-UPD-MAT").one()
                    material_count_before = session.query(MaterialModel).count()
                    link_count_before = session.query(MaterialUserLinkModel).filter(
                        MaterialUserLinkModel.material_article == "OWNED-UPD-MAT",
                        MaterialUserLinkModel.user_id == "trial-user",
                    ).count()
                    owned_count_before = inventory_repository.count_owned_private_materials("trial-user")
                    price_before = (
                        session.query(material_price.MaterialPriceModel)
                        .filter(
                            material_price.MaterialPriceModel.article == "OWNED-UPD-MAT",
                            material_price.MaterialPriceModel.city == "kyiv",
                        )
                        .one()
                    )

                response = client.patch(
                    "/catalog/materials/OWNED-UPD-MAT",
                    json={
                        "name": "Owned Update Material Renamed",
                        "price": 15.75,
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["item"]["article"], "OWNED-UPD-MAT")
                self.assertEqual(payload["item"]["name"], "Owned Update Material Renamed")

                with session_factory() as session:
                    material_after = session.query(MaterialModel).filter(MaterialModel.article == "OWNED-UPD-MAT").one()
                    material_count_after = session.query(MaterialModel).count()
                    link_count_after = session.query(MaterialUserLinkModel).filter(
                        MaterialUserLinkModel.material_article == "OWNED-UPD-MAT",
                        MaterialUserLinkModel.user_id == "trial-user",
                    ).count()
                    owned_count_after = inventory_repository.count_owned_private_materials("trial-user")
                    price_after = (
                        session.query(material_price.MaterialPriceModel)
                        .filter(
                            material_price.MaterialPriceModel.article == "OWNED-UPD-MAT",
                            material_price.MaterialPriceModel.city == "kyiv",
                        )
                        .one()
                    )

                self.assertEqual(material_before.id, material_after.id)
                self.assertEqual(material_count_before, material_count_after)
                self.assertEqual(link_count_before, link_count_after)
                self.assertEqual(owned_count_before, owned_count_after)
                self.assertEqual(material_after.description, "Original description")
                self.assertEqual(material_after.color, "Oak")
                self.assertEqual(material_after.dimensions, "2800 x 2070")
                self.assertEqual(material_after.thickness, "18")
                self.assertEqual(price_before.price, 12.5)
                self.assertEqual(price_after.price, 15.75)

    def test_material_update_endpoint_requires_materials_edit_entitlement(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._set_material_bool_entitlement(session, "materials.edit", "trial", False)
                    session.add(
                        MaterialModel(
                            article="EDIT-BLOCKED-MAT",
                            name="Edit Blocked Material",
                            category="dsp",
                            owner_user_id="trial-user",
                            is_default=False,
                        )
                    )
                    session.commit()

                response = client.patch(
                    "/catalog/materials/EDIT-BLOCKED-MAT",
                    json={"name": "Should Not Update"},
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["detail"]["error"], "Insufficient permissions")

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "EDIT-BLOCKED-MAT").one()
                    self.assertEqual(material.name, "Edit Blocked Material")

    def test_material_update_endpoint_handles_missing_materials_edit_entitlement(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._remove_material_entitlement(session, "materials.edit", "trial")
                    session.add(
                        MaterialModel(
                            article="EDIT-MISSING-MAT",
                            name="Missing Edit Material",
                            category="dsp",
                            owner_user_id="trial-user",
                            is_default=False,
                        )
                    )
                    session.commit()

                response = client.patch(
                    "/catalog/materials/EDIT-MISSING-MAT",
                    json={"name": "Should Not Update"},
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["detail"]["error"], "Insufficient permissions")

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "EDIT-MISSING-MAT").one()
                    self.assertEqual(material.name, "Missing Edit Material")

    def test_material_update_endpoint_blocks_foreign_private_material(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="FOREIGN-EDIT-MAT",
                            name="Foreign Edit Material",
                            description="Foreign description",
                            category="dsp",
                            owner_user_id="stranger-user",
                            is_default=False,
                        )
                    )
                    session.commit()

                response = client.patch(
                    "/catalog/materials/FOREIGN-EDIT-MAT",
                    json={"name": "Should Not Update"},
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["detail"]["error"], "Material not found")

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "FOREIGN-EDIT-MAT").one()
                    self.assertEqual(material.name, "Foreign Edit Material")
                    self.assertEqual(material.description, "Foreign description")

    def test_material_update_endpoint_blocks_system_material_for_non_admin_users(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="SYSTEM-EDIT-MAT",
                            name="System Edit Material",
                            category="dsp",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    session.commit()

                response = client.patch(
                    "/catalog/materials/SYSTEM-EDIT-MAT",
                    json={"name": "Should Not Update"},
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["detail"]["error"], "You do not have permission to edit this material")

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "SYSTEM-EDIT-MAT").one()
                    self.assertEqual(material.name, "System Edit Material")

    def test_material_update_endpoint_allows_admin_bypass(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="ADMIN-EDIT-MAT",
                            name="Admin Edit Material",
                            description="Admin description",
                            category="dsp",
                            owner_user_id="stranger-user",
                            is_default=False,
                        )
                    )
                    session.commit()

                response = client.patch(
                    "/catalog/materials/ADMIN-EDIT-MAT",
                    json={
                        "name": "Admin Edit Material Updated",
                        "description": "Admin updated description",
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["success"])
                self.assertEqual(response.json()["item"]["article"], "ADMIN-EDIT-MAT")
                self.assertEqual(response.json()["item"]["name"], "Admin Edit Material Updated")

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "ADMIN-EDIT-MAT").one()
                    self.assertEqual(material.name, "Admin Edit Material Updated")
                    self.assertEqual(material.description, "Admin updated description")

    def test_material_update_endpoint_rejects_invalid_and_forbidden_fields(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="VALIDATION-MAT",
                            name="Validation Material",
                            description="Validation description",
                            color="White",
                            dimensions="2800 x 2070",
                            thickness="18",
                            category="dsp",
                            owner_user_id="trial-user",
                            is_default=False,
                        )
                    )
                    session.commit()

                forbidden_payloads = [
                    {"article": "NEW-ARTICLE"},
                    {"owner_user_id": "other-user"},
                    {"is_default": True},
                    {"source_url": "https://example.com/new"},
                    {"city": "lviv"},
                    {"unknown_field": "value"},
                ]

                for payload in forbidden_payloads:
                    response = client.patch(
                        "/catalog/materials/VALIDATION-MAT",
                        json=payload,
                        headers=self._auth_headers("trial-token"),
                    )
                    self.assertEqual(response.status_code, 422)

                invalid_name = client.patch(
                    "/catalog/materials/VALIDATION-MAT",
                    json={"name": ""},
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(invalid_name.status_code, 422)

                invalid_price = client.patch(
                    "/catalog/materials/VALIDATION-MAT",
                    json={"price": -1},
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(invalid_price.status_code, 422)

                partial_update = client.patch(
                    "/catalog/materials/VALIDATION-MAT",
                    json={"name": "Validation Material Updated"},
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(partial_update.status_code, 200)
                self.assertTrue(partial_update.json()["success"])

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "VALIDATION-MAT").one()
                    self.assertEqual(material.name, "Validation Material Updated")
                    self.assertEqual(material.description, "Validation description")
                    self.assertEqual(material.color, "White")
                    self.assertEqual(material.dimensions, "2800 x 2070")
                    self.assertEqual(material.thickness, "18")

    def test_material_delete_entitlement_blocks_owned_material_deletion(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._set_material_bool_entitlement(session, "materials.delete", "trial", False)
                    session.add(
                        MaterialModel(
                            article="OWNED-DELETE-MAT",
                            name="Owned Delete Material",
                            category="dsp",
                            owner_user_id="trial-user",
                            is_default=False,
                        )
                    )
                    session.commit()

                response = client.delete(
                    "/catalog/materials/OWNED-DELETE-MAT",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 403)

    def test_material_import_job_result_is_visible_for_own_material(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="OWN-JOB-MAT",
                            name="Own Job Material",
                            category="dsp",
                            owner_user_id="owner-1",
                            is_default=False,
                        )
                    )
                    self._create_material_import_job(
                        session,
                        job_id=101,
                        article="OWN-JOB-MAT",
                        city="kyiv",
                        owner_user_id="owner-1",
                    )
                    session.commit()

                response = client.get(
                    "/catalog/materials/import-jobs/101",
                    headers=self._auth_headers("owner-token"),
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertIsNotNone(payload["item"])
                self.assertEqual(payload["item"]["article"], "OWN-JOB-MAT")

    def test_material_import_job_result_hides_foreign_private_material(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="FOREIGN-JOB-MAT",
                            name="Foreign Job Material",
                            category="dsp",
                            owner_user_id="stranger-user",
                            is_default=False,
                        )
                    )
                    self._create_material_import_job(
                        session,
                        job_id=102,
                        article="FOREIGN-JOB-MAT",
                        city="kyiv",
                        owner_user_id="stranger-user",
                    )
                    session.commit()

                response = client.get(
                    "/catalog/materials/import-jobs/102",
                    headers=self._auth_headers("owner-token"),
                )
                self.assertEqual(response.status_code, 404)
                payload = response.json()
                self.assertEqual(payload["detail"]["error"], "Material import job not found")

    def test_material_import_job_result_allows_admin_bypass(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="ADMIN-JOB-MAT",
                            name="Admin Job Material",
                            category="dsp",
                            owner_user_id="stranger-user",
                            is_default=False,
                        )
                    )
                    self._create_material_import_job(
                        session,
                        job_id=103,
                        article="ADMIN-JOB-MAT",
                        city="kyiv",
                        owner_user_id="stranger-user",
                    )
                    session.commit()

                response = client.get(
                    "/catalog/materials/import-jobs/103",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertIsNotNone(payload["item"])
                self.assertEqual(payload["item"]["article"], "ADMIN-JOB-MAT")

    def test_material_import_job_result_requires_view_permission_and_keeps_db_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._set_material_bool_entitlement(session, "materials.view", "trial", False)
                    session.add(
                        MaterialModel(
                            article="BLOCKED-JOB-MAT",
                            name="Blocked Job Material",
                            category="dsp",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    self._create_material_import_job(
                        session,
                        job_id=104,
                        article="BLOCKED-JOB-MAT",
                        city="kyiv",
                        owner_user_id=None,
                    )
                    session.commit()

                with session_factory() as session:
                    materials_before = session.query(MaterialModel).count()
                    jobs_before = session.query(material_import_job.MaterialImportJobModel).count()

                response = client.get(
                    "/catalog/materials/import-jobs/104",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 403)

                with session_factory() as session:
                    materials_after = session.query(MaterialModel).count()
                    jobs_after = session.query(material_import_job.MaterialImportJobModel).count()

                self.assertEqual(materials_before, materials_after)
                self.assertEqual(jobs_before, jobs_after)

    def test_material_import_job_result_keeps_system_material_visible(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="SYSTEM-JOB-MAT",
                            name="System Job Material",
                            category="dsp",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    self._create_material_import_job(
                        session,
                        job_id=105,
                        article="SYSTEM-JOB-MAT",
                        city="kyiv",
                        owner_user_id=None,
                    )
                    session.commit()

                response = client.get(
                    "/catalog/materials/import-jobs/105",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertIsNotNone(payload["item"])
                self.assertEqual(payload["item"]["article"], "SYSTEM-JOB-MAT")

    def test_free_user_can_create_three_materials_but_not_a_fourth(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add_all(
                        [
                            MaterialModel(
                                article="ADMIN-SYSTEM-MAT",
                                name="Admin System Material",
                                category="dsp",
                                owner_user_id=None,
                                is_default=True,
                            ),
                            MaterialModel(
                                article="OTHER-PRIVATE-MAT",
                                name="Other Private Material",
                                category="dsp",
                                owner_user_id="someone-else",
                                is_default=False,
                            ),
                        ]
                    )
                    session.commit()

                quota_response = client.get(
                    "/catalog/materials",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(quota_response.status_code, 200)
                self.assertTrue(quota_response.json()["success"])
                quota = quota_response.json()["material_quota"]
                self.assertEqual(quota["owned_count"], 0)
                self.assertEqual(quota["limit"], 3)
                self.assertFalse(quota["is_unlimited"])
                self.assertTrue(quota["can_create"])

                system_visible = client.get(
                    "/catalog/materials/ADMIN-SYSTEM-MAT",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(system_visible.status_code, 200)
                self.assertTrue(system_visible.json()["success"])

                foreign_hidden = client.get(
                    "/catalog/materials/OTHER-PRIVATE-MAT",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(foreign_hidden.status_code, 200)
                self.assertFalse(foreign_hidden.json()["success"])

                created_articles = []
                for index in range(1, 4):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": f"FREE-MAT-{index}",
                            "name": f"Free Material {index}",
                            "category": "dsp",
                            "city": "kyiv",
                            "price": 12.5 + index,
                        },
                        headers=self._auth_headers("free-token"),
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.json()["success"])
                    created_articles.append(response.json()["item"]["article"])

                quota_response = client.get(
                    "/catalog/materials",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(quota_response.status_code, 200)
                quota = quota_response.json()["material_quota"]
                self.assertEqual(quota["owned_count"], 3)
                self.assertEqual(quota["limit"], 3)
                self.assertFalse(quota["can_create"])

                own_detail = client.get(
                    f"/catalog/materials/{created_articles[0]}",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(own_detail.status_code, 200)
                self.assertTrue(own_detail.json()["success"])
                self.assertEqual(own_detail.json()["item"]["article"], created_articles[0])

                blocked = client.post(
                    "/catalog/materials",
                    json={
                        "article": "FREE-MAT-4",
                        "name": "Free Material 4",
                        "category": "dsp",
                        "city": "kyiv",
                        "price": 16.5,
                    },
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(blocked.status_code, 403)
                self.assertEqual(blocked.json()["detail"]["error"], "Material ownership limit reached")

                deleted = client.delete(
                    f"/catalog/materials/{created_articles[0]}",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(deleted.status_code, 200)
                self.assertTrue(deleted.json()["success"])

                quota_response = client.get(
                    "/catalog/materials",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(quota_response.status_code, 200)
                quota = quota_response.json()["material_quota"]
                self.assertEqual(quota["owned_count"], 2)
                self.assertEqual(quota["limit"], 3)
                self.assertTrue(quota["can_create"])

                created_after_delete = client.post(
                    "/catalog/materials",
                    json={
                        "article": "FREE-MAT-4",
                        "name": "Free Material 4",
                        "category": "dsp",
                        "city": "kyiv",
                        "price": 16.5,
                    },
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(created_after_delete.status_code, 200)
                self.assertTrue(created_after_delete.json()["success"])

    def test_admin_created_material_is_system_and_visible_to_trial(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                created = client.post(
                    "/catalog/materials",
                    json={
                        "article": "ADMIN-MAT",
                        "name": "Admin Material",
                        "category": "dsp",
                        "city": "kyiv",
                        "source_url": "https://example.com/system-material",
                        "price": 42.0,
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(created.status_code, 200)
                self.assertTrue(created.json()["success"])
                article = created.json()["item"]["article"]

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == article).one()
                    self.assertIsNone(material.owner_user_id)
                    self.assertTrue(material.is_default)

                detail = client.get(
                    f"/catalog/materials/{article}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(detail.status_code, 200)
                self.assertTrue(detail.json()["success"])
                self.assertEqual(detail.json()["item"]["article"], article)

                edge_denied = client.post(
                    f"/catalog/materials/{article}/edges",
                    json={
                        "edge_key": "abs",
                        "source_url": "https://example.com/edge.png",
                        "city": "kyiv",
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(edge_denied.status_code, 200)
                self.assertFalse(edge_denied.json()["success"])

                denied_delete = client.delete(
                    f"/catalog/materials/{article}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(denied_delete.status_code, 200)
                self.assertFalse(denied_delete.json()["success"])

                with session_factory() as session:
                    before_system = session.query(MaterialModel).filter(MaterialModel.article == article).one()
                    before_system_name = before_system.name

                free_update = client.post(
                    "/catalog/materials",
                    json={
                        "article": article,
                        "name": "Blocked Update",
                        "category": "dsp",
                        "city": "kyiv",
                        "price": 42.0,
                    },
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(free_update.status_code, 200)
                self.assertTrue(free_update.json()["success"])
                self.assertEqual(free_update.json()["item"]["article"], article)

                with session_factory() as session:
                    after_system = session.query(MaterialModel).filter(MaterialModel.article == article).one()
                    self.assertEqual(after_system.name, before_system_name)

                free_delete = client.delete(
                    f"/catalog/materials/{article}",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(free_delete.status_code, 200)
                self.assertFalse(free_delete.json()["success"])

    def test_trial_user_cannot_see_private_material_by_id_or_image(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    private_material = MaterialModel(
                        article="PRIVATE-MAT",
                        name="Private Material",
                        category="dsp",
                        owner_user_id="owner-1",
                        is_default=False,
                        image_cached_bytes=b"private-material-bytes",
                        image_cached_content_type="image/png",
                    )
                    session.add(private_material)
                    session.commit()

                detail = client.get(
                    "/catalog/materials/PRIVATE-MAT",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(detail.status_code, 200)
                self.assertFalse(detail.json()["success"])

                image = client.get(
                    "/catalog/materials/PRIVATE-MAT/image",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(image.status_code, 404)

    def test_trial_user_can_create_update_and_delete_own_fitting(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                rejected = client.post(
                    "/catalog/fittings",
                    json={
                        "name": "Rejected System Fitting",
                        "fitting_type": "drawer_slides",
                        "fitting_group": "fittings",
                        "is_system": True,
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(rejected.status_code, 200)
                self.assertFalse(rejected.json()["success"])

                created = client.post(
                    "/catalog/fittings",
                    json={
                        "name": "Trial Fitting",
                        "fitting_type": "drawer_slides",
                        "fitting_group": "fittings",
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(created.status_code, 200)
                self.assertTrue(created.json()["success"])
                fitting_id = str(created.json()["item"]["id"])

                with session_factory() as session:
                    fitting = session.get(FittingModel, int(fitting_id))
                    self.assertIsNotNone(fitting)
                    self.assertEqual(fitting.owner_user_id, "trial-user")
                    self.assertFalse(fitting.is_system)

                updated = client.put(
                    f"/catalog/fittings/{fitting_id}",
                    json={
                        "name": "Trial Fitting Updated",
                        "fitting_type": "drawer_slides",
                        "fitting_group": "fittings",
                        "is_system": True,
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(updated.status_code, 200)
                self.assertTrue(updated.json()["success"])
                self.assertFalse(updated.json()["item"]["is_system"])

                with session_factory() as session:
                    fitting = session.get(FittingModel, int(fitting_id))
                    self.assertIsNotNone(fitting)
                    self.assertEqual(fitting.name, "Trial Fitting Updated")
                    self.assertFalse(fitting.is_system)

                deleted = client.delete(
                    f"/catalog/fittings/{fitting_id}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(deleted.status_code, 200)
                self.assertTrue(deleted.json()["success"])

                with session_factory() as session:
                    self.assertIsNone(session.get(FittingModel, int(fitting_id)))

    def test_fitting_list_route_handles_rows_without_timestamp_attrs(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        FittingManufacturerModel(
                            id=2,
                            code="hettich",
                            name="Hettich",
                            is_active=True,
                            sort_order=1,
                        )
                    )
                    session.add(
                        FittingCategoryModel(
                            id=3,
                            code="connectors_fasteners",
                            name="З'єднувальна та кріпильна фурнітура",
                            is_active=True,
                            sort_order=1,
                        )
                    )
                    session.add(
                        FittingProductModel(
                            id=31,
                            article="61136",
                            name="Дюбель під стяжку VB DU 321 (9021847) Hettich",
                            brand="Hettich",
                            manufacturer_id=2,
                            category_id=3,
                            is_active=True,
                        )
                    )
                    session.add(
                        SupplierModel(
                            code="viyar",
                            name="VIYAR",
                            logo_url="https://example.test/viyar-logo.png",
                            owner_user_id=None,
                            is_system=True,
                            is_active=True,
                        )
                    )
                    session.add(
                        FittingModel(
                            name="Timestampless Fitting",
                            article="61136",
                            technical_product_id=31,
                            fitting_type="drawer_slides",
                            fitting_group="fittings",
                            owner_user_id=None,
                            is_system=True,
                            is_active=True,
                            source="viyar",
                            source_url="https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                            brand="Hettich",
                            price=5.22,
                            stock="В наявності",
                        )
                    )
                    session.commit()

                    fitting = session.query(FittingModel).filter(FittingModel.article == "61136").one()
                    supplier = session.query(SupplierModel).filter(SupplierModel.code == "viyar").one()
                    session.add(
                        FittingSupplierOfferModel(
                            fitting_id=fitting.id,
                            supplier_id=supplier.id,
                            article="61136",
                            source_url="https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                            price=5.22,
                            currency="UAH",
                            unit="шт",
                            stock="in stock",
                            is_active=True,
                            priority=100,
                        )
                    )
                    session.commit()
                    fitting_id = str(fitting.id)

                response = client.get(
                    "/catalog/fittings?city=Kyiv&ownership_scope=all",
                    headers=self._auth_headers("admin-token"),
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(len(payload["items"]), 1)
                self.assertEqual(payload["items"][0]["article"], "61136")
                self.assertEqual(payload["items"][0]["technical_product_id"], 31)
                self.assertEqual(payload["items"][0]["manufacturer_id"], 2)
                self.assertEqual(payload["items"][0]["supplier_offers"][0]["supplier_name"], "VIYAR")
                self.assertEqual(
                    payload["items"][0]["supplier_offers"][0]["supplier_logo_url"],
                    "https://example.test/viyar-logo.png",
                )
                detail_response = client.get(
                    f"/catalog/fittings/{fitting_id}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(detail_response.status_code, 200)
                self.assertEqual(detail_response.json()["item"]["manufacturer_id"], 2)
                self.assertNotIn("created_at", payload["items"][0])
                self.assertNotIn("updated_at", payload["items"][0])

    def test_manual_fitting_keeps_supplier_offer_without_import_source(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    supplier = SupplierModel(
                        code="viyar",
                        name="VIYAR",
                        logo_url="https://example.test/viyar-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    session.add(supplier)
                    session.add(
                        FittingModel(
                            name="Manual fitting",
                            article="0006",
                            fitting_type="drawer_slides",
                            fitting_group="fittings",
                            owner_user_id=None,
                            is_system=True,
                            is_active=True,
                            source=None,
                            source_url=None,
                            brand="Hettich",
                            price=80.0,
                            stock="in stock",
                        )
                    )
                    session.commit()

                    fitting = session.query(FittingModel).filter(FittingModel.article == "0006").one()
                    session.add(
                        FittingSupplierOfferModel(
                            fitting_id=fitting.id,
                            supplier_id=supplier.id,
                            article="006",
                            source_url=None,
                            price=70.0,
                            currency="UAH",
                            unit="шт.",
                            stock="in stock",
                            is_active=True,
                            priority=100,
                        )
                    )
                    session.commit()

                list_response = client.get(
                    "/catalog/fittings?city=Kyiv&ownership_scope=all&search=0006",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(list_response.status_code, 200)
                list_payload = list_response.json()
                self.assertEqual(len(list_payload["items"]), 1)
                self.assertEqual(list_payload["items"][0]["article"], "0006")
                self.assertEqual(list_payload["items"][0]["source_site"], "manual")
                self.assertEqual(list_payload["items"][0]["supplier_offers"][0]["supplier_name"], "VIYAR")
                self.assertEqual(
                    list_payload["items"][0]["supplier_offers"][0]["supplier_logo_url"],
                    "https://example.test/viyar-logo.png",
                )

                detail_response = client.get(
                    f"/catalog/fittings/{list_payload['items'][0]['id']}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(detail_response.status_code, 200)
                detail_payload = detail_response.json()["item"]
                self.assertIsNone(detail_payload["source_site"])
                self.assertEqual(detail_payload["supplier_offers"][0]["supplier_name"], "VIYAR")
                self.assertEqual(detail_payload["supplier_offers"][0]["supplier_logo_url"], "https://example.test/viyar-logo.png")

    def test_delete_fitting_blocks_when_it_is_used_by_mounting_node(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    fitting = FittingModel(
                        name="Node-locked Fitting",
                        article="NODE-LOCKED-0001",
                        city="Kyiv",
                        owner_user_id="trial-user",
                        is_system=False,
                        is_active=True,
                    )
                    session.add(fitting)
                    session.commit()
                    fitting_id = int(fitting.id)

                with session_factory() as session:
                    service = MountingNodeService(session=session)
                    node = service.create_mounting_node(
                        {
                            "name": "Confirmat node",
                            "ownership_type": "system",
                            "items": [{"fitting_id": fitting_id, "quantity": 1}],
                        },
                        viewer_user_id=None,
                        viewer_role="admin",
                    )
                    self.assertEqual(node["items"][0]["fitting_id"], fitting_id)

                blocked = client.delete(
                    f"/catalog/fittings/{fitting_id}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(blocked.status_code, 409)
                blocked_payload = blocked.json()
                self.assertFalse(blocked_payload["detail"]["success"])
                self.assertIn("Confirmat node", blocked_payload["detail"]["error"])
                self.assertIn("повторіть видалення", blocked_payload["detail"]["error"])
                self.assertTrue(blocked_payload["detail"]["dependent_nodes"])

                with session_factory() as session:
                    self.assertIsNotNone(session.get(FittingModel, fitting_id))

    def test_delete_fitting_removes_supplier_offer_images_and_hole_templates(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    supplier = SupplierModel(
                        code="custom-viyar",
                        name="Custom VIYAR",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    session.add(supplier)
                    session.flush()

                    fitting = FittingModel(
                        name="Delete candidate",
                        article="0003",
                        city="Kyiv",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    session.add(fitting)
                    session.flush()

                    session.add_all(
                        [
                            FittingSupplierOfferModel(
                                fitting_id=fitting.id,
                                supplier_id=supplier.id,
                                article="0003",
                                source_url=None,
                                price=15.0,
                                currency="UAH",
                                unit="шт",
                                stock="in stock",
                                is_active=True,
                                priority=100,
                            ),
                            FittingImageModel(
                                fitting_id=fitting.id,
                                sort_order=0,
                                is_primary=True,
                                source_url="https://example.com/fitting.jpg",
                                image_cached_bytes=b"delete-candidate-image",
                                image_cached_content_type="image/jpeg",
                                image_sha256=sha256(b"delete-candidate-image").hexdigest(),
                            ),
                        ]
                    )
                    template = FittingHoleTemplateModel(
                        fitting_id=fitting.id,
                        name="Template",
                        bundle_key="bundle-a",
                        bundle_name="Bundle A",
                        template_type="surface_mount",
                        side="left",
                        coordinate_system="cartesian",
                        mounting_variant_key="surface_mount",
                        is_default=True,
                        is_active=True,
                    )
                    session.add(template)
                    session.flush()
                    session.add(
                        FittingHolePointModel(
                            template_id=template.id,
                            label="P1",
                            x_mm=10.0,
                            y_mm=20.0,
                            z_mm=0.0,
                            order_index=0,
                            quantity=1,
                            mirrored=False,
                        )
                    )
                    session.commit()
                    fitting_id = int(fitting.id)
                    supplier_id = int(supplier.id)

                response = client.delete(
                    f"/catalog/fittings/{fitting_id}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])

                with session_factory() as session:
                    self.assertIsNone(session.get(FittingModel, fitting_id))
                    self.assertIsNotNone(session.get(SupplierModel, supplier_id))
                    self.assertEqual(
                        session.query(FittingSupplierOfferModel).filter(FittingSupplierOfferModel.fitting_id == fitting_id).count(),
                        0,
                    )
                    self.assertEqual(
                        session.query(FittingImageModel).filter(FittingImageModel.fitting_id == fitting_id).count(),
                        0,
                    )
                    self.assertEqual(
                        session.query(FittingHolePointModel).join(FittingHoleTemplateModel).filter(
                            FittingHoleTemplateModel.fitting_id == fitting_id,
                        ).count(),
                        0,
                    )
                    self.assertEqual(
                        session.query(FittingHoleTemplateModel).filter(FittingHoleTemplateModel.fitting_id == fitting_id).count(),
                        0,
                    )

    def test_delete_fitting_repository_handles_supplier_offer_image_rows_without_stale_data_error(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    supplier = SupplierModel(
                        code="delete-test-supplier",
                        name="Delete Test Supplier",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    fitting = FittingModel(
                        name="Delete repository candidate",
                        article="0010",
                        city="Kyiv",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    session.add_all([supplier, fitting])
                    session.flush()

                    session.add_all(
                        [
                            FittingSupplierOfferModel(
                                fitting_id=fitting.id,
                                supplier_id=supplier.id,
                                article="0010",
                                source_url=None,
                                price=80.0,
                                currency="UAH",
                                unit="шт",
                                stock="in stock",
                                is_active=True,
                                priority=100,
                            ),
                            FittingImageModel(
                                fitting_id=fitting.id,
                                sort_order=0,
                                is_primary=True,
                                source_url="https://example.com/delete-test.jpg",
                                image_cached_bytes=b"delete-test-image",
                                image_cached_content_type="image/jpeg",
                                image_sha256=sha256(b"delete-test-image").hexdigest(),
                            ),
                        ]
                    )
                    session.commit()
                    fitting_id = int(fitting.id)
                    supplier_id = int(supplier.id)

                deleted = inventory_repository.delete_fitting(fitting_id)

                self.assertIsNotNone(deleted)
                self.assertTrue(deleted["success"])
                self.assertEqual(int(deleted["selected_item_id"]), fitting_id)

                with session_factory() as session:
                    self.assertIsNone(session.get(FittingModel, fitting_id))
                    self.assertIsNotNone(session.get(SupplierModel, supplier_id))
                    self.assertEqual(
                        session.query(FittingSupplierOfferModel).filter(FittingSupplierOfferModel.fitting_id == fitting_id).count(),
                        0,
                    )
                    self.assertEqual(
                        session.query(FittingImageModel).filter(FittingImageModel.fitting_id == fitting_id).count(),
                        0,
                    )

    def test_source_import_success_creates_fitting(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with patch.object(
                    catalog,
                    "parse_fitting_source_metadata",
                    return_value={
                        "success": True,
                        "source_site": "viyar",
                        "final_url": "https://viyar.ua/ua/catalog/test-fitting",
                        "name": "Parsed Fitting",
                        "article": "PARSED-001",
                        "price": 4.02,
                        "availability": "in stock",
                        "image_url": "https://cdn.example.com/fittings/main.jpg",
                        "image_urls": [
                            "https://cdn.example.com/fittings/main.jpg",
                        ],
                        "description": "Parsed description",
                        "brand": "Hettich",
                    },
                    create=True,
                ), patch.object(
                    catalog,
                    "prepare_fitting_gallery_images",
                    return_value=(self._fake_gallery_image(),),
                ) as prepare_gallery_mock:
                    response = client.post(
                        "/catalog/fittings",
                        json={
                            "name": "https://viyar.ua/ua/catalog/test-fitting",
                            "source_url": "https://viyar.ua/ua/catalog/test-fitting",
                            "fitting_type": "drawer_slides",
                            "fitting_group": "fittings",
                        },
                        headers=self._auth_headers("trial-token"),
                    )

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["success"])
                item = response.json()["item"]
                self.assertEqual(item["name"], "Parsed Fitting")
                self.assertEqual(item["article"], "PARSED-001")
                self.assertEqual(item["price"], 4.02)
                self.assertEqual(item["description"], "Parsed description")
                prepare_gallery_mock.assert_called_once()

                with session_factory() as session:
                    fitting = session.query(FittingModel).filter(FittingModel.article == "PARSED-001").one()
                    self.assertEqual(fitting.name, "Parsed Fitting")
                    self.assertEqual(fitting.source_url, "https://viyar.ua/ua/catalog/test-fitting")
                    self.assertEqual(fitting.image_url, "https://cdn.example.com/fittings/p1.jpg")

    def test_source_import_success_filters_kronas_media_gallery_entries_and_creates_fitting(self) -> None:
        kronas_url = (
            "https://kronas.com.ua/furnitura-270/petli-i-komplektuyushhie-334/"
            "petli-dlya-dsp-454/petli-plavnogo-zakryvaniya-351/"
            "petlja-nakladnaja-c-dovodchikom-clip-on-3d-giff-prime-d35-h0-chernyj-nikel"
        )
        kronas_html = """
            <html>
              <head>
                <title>Петля накладная c доводчиком Clip-on 3D GIFF PRIME d=35 H=0 черный никель</title>
                <meta itemprop="price" content="71.77">
                <meta itemprop="priceCurrency" content="UAH">
              </head>
              <body>
                <h1>Петля накладная c доводчиком Clip-on 3D GIFF PRIME d=35 H=0 черный никель</h1>
                <span id="artikul" itemprop="sku">134376</span>
                <div class="productLabel">Є в наявності</div>
                <div class="productAttr">
                  <div class="productAttr__key">Виробник:</div>
                  <div class="productAttr__value">GIFF PRIME</div>
                  <div class="productAttr__key">Одиниця виміру:</div>
                  <div class="productAttr__value">шт</div>
                </div>
                <div class="productImageBlock__slider">
                  <div class="js-productImage" data-src="https://cdn.example.com/kronas/image-a.png"></div>
                  <div class="js-productImage" data-src="https://www.youtube.com/embed/abc123"></div>
                  <div class="js-productImage" data-src="https://cdn.example.com/kronas/image-b.png"></div>
                  <div class="js-productImage" data-src="https://cdn.example.com/kronas/image-c.png"></div>
                </div>
              </body>
            </html>
        """

        image_bytes_map = {
            "https://cdn.example.com/kronas/image-a.png": self._make_png_bytes((220, 40, 40)),
            "https://cdn.example.com/kronas/image-b.png": self._make_png_bytes((40, 220, 40)),
            "https://cdn.example.com/kronas/image-c.png": self._make_png_bytes((40, 40, 220)),
        }

        def fake_fetch_remote_image_payload(url: str, city: str | None = None):
            payload = image_bytes_map.get(url)
            if payload is None:
                return None
            return {
                "bytes": payload,
                "content_type": "image/png",
            }

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        SupplierModel(
                            code="kronas",
                            name="Кронас",
                            owner_user_id=None,
                            is_system=True,
                            is_active=True,
                        ),
                    )
                    session.commit()
                    supplier_id = session.query(SupplierModel.id).filter(SupplierModel.code == "kronas").one()[0]

                with patch.object(
                    fitting_source_parser,
                    "_fetch_html",
                    new=AsyncMock(return_value=(200, kronas_url, kronas_html)),
                ), patch.object(
                    catalog,
                    "fetch_remote_image_payload",
                    side_effect=fake_fetch_remote_image_payload,
                ), patch.object(
                    catalog,
                    "_resolve_fitting_manufacturer_id_from_brand",
                    return_value=None,
                ), patch.object(
                    catalog,
                    "_resolve_fitting_category_id_from_type",
                    return_value=None,
                ):
                    response = client.post(
                        "/catalog/fittings",
                        json={
                            "name": kronas_url,
                            "source_url": kronas_url,
                            "fitting_type": "fittings",
                            "fitting_group": "fittings",
                            "is_active": True,
                            "image_urls": [
                                "https://cdn.example.com/kronas/image-a.png",
                                "https://cdn.example.com/kronas/image-b.png",
                                "https://cdn.example.com/kronas/image-c.png",
                            ],
                            "supplier_offer": {
                                "supplier_id": supplier_id,
                                "article": "134376",
                                "price": 71.77,
                                "currency": "UAH",
                                "unit": "шт",
                                "stock": "in stock",
                                "is_active": True,
                                "priority": 100,
                            },
                        },
                        headers=self._auth_headers("trial-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["item"]["article"], "134376")
                self.assertEqual(payload["item"]["brand"], "GIFF PRIME")
                self.assertEqual(payload["item"]["price"], 71.77)
                self.assertEqual(payload["item"]["source_url"], kronas_url)
                self.assertEqual(payload["item"]["image_url"], "https://cdn.example.com/kronas/image-a.png")

                with session_factory() as session:
                    fitting = session.query(FittingModel).filter(FittingModel.article == "134376").one()
                    image_rows = (
                        session.query(FittingImageModel)
                        .filter(FittingImageModel.fitting_id == fitting.id)
                        .order_by(FittingImageModel.sort_order.asc())
                        .all()
                    )
                    offer = (
                        session.query(FittingSupplierOfferModel)
                        .filter(FittingSupplierOfferModel.fitting_id == fitting.id)
                        .one()
                    )

                self.assertEqual(fitting.image_url, "https://cdn.example.com/kronas/image-a.png")
                self.assertEqual(
                    [row.source_url for row in image_rows],
                    [
                        "https://cdn.example.com/kronas/image-a.png",
                        "https://cdn.example.com/kronas/image-b.png",
                        "https://cdn.example.com/kronas/image-c.png",
                    ],
                )
                self.assertEqual(offer.supplier_id, supplier_id)
                self.assertEqual(offer.article, "134376")
                self.assertEqual(offer.price, 71.77)
                self.assertNotIn("youtube", " ".join(row.source_url for row in image_rows).lower())

    def test_source_preview_route_rejects_invalid_preview_without_writes(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with patch.object(
                    catalog,
                    "parse_fitting_source_metadata",
                    return_value={
                        "success": False,
                        "error": "Not Found",
                    },
                    create=True,
                ):
                    response = client.post(
                        "/catalog/fittings/source-preview",
                        json={
                            "source_url": "https://viyar.ua/ua/catalog/error-404",
                            "city": "Київ",
                        },
                        headers=self._auth_headers("trial-token"),
                    )

                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()["success"])
                self.assertIn("Not Found", response.json()["error"])

                with session_factory() as session:
                    self.assertEqual(session.query(FittingModel).count(), 0)

    def test_source_import_failure_rejects_when_name_empty(self) -> None:
        self._assert_source_import_rejected_without_create(
            payload_name="",
            expected_article=None,
        )

    def test_source_import_failure_rejects_when_name_contains_url(self) -> None:
        self._assert_source_import_rejected_without_create(
            payload_name="https://viyar.ua/ua/catalog/broken-fitting",
            expected_article=None,
        )

    def test_source_import_failure_rejects_when_name_is_arbitrary_text(self) -> None:
        self._assert_source_import_rejected_without_create(
            payload_name="Broken fitting",
            expected_article=None,
        )

    def test_manual_create_without_source_url_stays_working(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with patch.object(catalog, "parse_fitting_source_metadata") as parse_mock:
                    response = client.post(
                        "/catalog/fittings",
                        json={
                            "name": "Manual Fitting",
                            "article": "MF-001",
                            "fitting_type": "manual_test_type",
                            "fitting_group": "fittings",
                            "is_active": True,
                        },
                        headers=self._auth_headers("trial-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                parse_mock.assert_not_called()

                with session_factory() as session:
                    fitting = session.query(FittingModel).filter(FittingModel.name == "Manual Fitting").one()
                    product = session.query(FittingProductModel).one()
                    self.assertEqual(session.query(FittingImageModel).count(), 0)
                    self.assertEqual(session.query(FittingSupplierOfferModel).count(), 0)
                    self.assertEqual(session.query(FittingProductModel).count(), 1)
                    self.assertEqual(session.query(FittingModel).count(), 1)
                    self.assertEqual(product.name, "Manual Fitting")
                    self.assertEqual(product.article, "MF-001")
                    self.assertIsNone(product.brand)
                    self.assertIsNone(product.manufacturer_id)
                    self.assertIsNone(product.category_id)
                    self.assertTrue(product.is_active)
                    self.assertIsNone(fitting.source_url)
                    self.assertEqual(fitting.article, "MF-001")
                    self.assertEqual(fitting.technical_product_id, product.id)
                    self.assertEqual(payload["item"]["technical_product_id"], product.id)

    def test_manual_create_with_supplier_id_persists_supplier_offer(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    supplier = SupplierModel(
                        code="viyar",
                        name="VIYAR",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    session.add(supplier)
                    session.commit()
                    supplier_id = supplier.id

                response = client.post(
                    "/catalog/fittings",
                    json={
                        "name": "Manual Fitting With Supplier",
                        "article": "MF-SUP-001",
                        "fitting_type": "manual_test_type",
                        "fitting_group": "fittings",
                        "is_active": True,
                        "supplier_offer": {
                            "supplier_id": supplier_id,
                            "article": "SUP-001",
                            "price": 19.5,
                            "currency": "UAH",
                            "unit": "шт",
                            "stock": "in stock",
                            "priority": 0,
                            "is_active": True,
                        },
                    },
                    headers=self._auth_headers("trial-token"),
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])

                with session_factory() as session:
                    fitting = session.query(FittingModel).filter(FittingModel.article == "MF-SUP-001").one()
                    product = session.query(FittingProductModel).one()
                    offer = session.query(FittingSupplierOfferModel).one()

                    self.assertEqual(session.query(FittingSupplierOfferModel).count(), 1)
                    self.assertEqual(session.query(FittingProductModel).count(), 1)
                    self.assertEqual(session.query(FittingModel).count(), 1)
                    self.assertEqual(fitting.technical_product_id, product.id)
                    self.assertEqual(offer.fitting_id, fitting.id)
                    self.assertEqual(offer.supplier_id, supplier_id)
                    self.assertEqual(offer.article, "SUP-001")
                    self.assertEqual(offer.price, 19.5)
                    self.assertEqual(offer.currency, "UAH")
                    self.assertEqual(offer.unit, "шт")
                    self.assertEqual(offer.stock, "in stock")
                    self.assertEqual(offer.priority, 0)
                    self.assertTrue(offer.is_active)
                    self.assertEqual(payload["item"]["technical_product_id"], product.id)

    def test_manual_create_without_source_url_persists_gallery_images(self) -> None:
        manual_image_one_data_url = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="
        )
        manual_image_two_data_url = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgaPj/HwAEggJ/59habAAAAABJRU5ErkJggg=="
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                response = client.post(
                    "/catalog/fittings",
                    json={
                        "name": "Manual Fitting With Image",
                        "article": "MF-IMG-001",
                        "fitting_type": "manual_test_type",
                        "fitting_group": "fittings",
                        "image_url": manual_image_one_data_url,
                        "image_urls": [manual_image_one_data_url, manual_image_two_data_url],
                        "is_active": True,
                    },
                    headers=self._auth_headers("trial-token"),
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])

                with session_factory() as session:
                    fitting = session.query(FittingModel).filter(FittingModel.name == "Manual Fitting With Image").one()
                    product = session.query(FittingProductModel).one()
                    images = session.query(FittingImageModel).order_by(FittingImageModel.sort_order.asc()).all()

                    self.assertEqual(session.query(FittingProductModel).count(), 1)
                    self.assertEqual(session.query(FittingModel).count(), 1)
                    self.assertEqual(session.query(FittingImageModel).count(), 2)
                    self.assertEqual(fitting.technical_product_id, product.id)
                    self.assertEqual([image.fitting_id for image in images], [fitting.id, fitting.id])
                    self.assertEqual([image.sort_order for image in images], [0, 1])
                    self.assertEqual([image.is_primary for image in images], [True, False])
                    self.assertTrue(images[0].image_cached_bytes)
                    self.assertTrue(images[1].image_cached_bytes)
                    self.assertEqual(images[0].image_cached_content_type, "image/png")
                    self.assertEqual(images[1].image_cached_content_type, "image/png")
                    self.assertEqual(payload["item"]["technical_product_id"], product.id)
                    self.assertEqual(payload["item"]["image_url"], manual_image_one_data_url)

    def test_source_import_rejects_when_gallery_images_missing_uses_generic_message(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with patch.object(
                    catalog,
                    "parse_fitting_source_metadata",
                    return_value={
                        "success": True,
                        "source_site": "viyar",
                        "final_url": "https://viyar.ua/ua/catalog/no-images",
                        "name": "No Images Fitting",
                        "article": "NO-IMG-001",
                        "price": 4.02,
                        "availability": "in stock",
                        "image_url": "https://cdn.example.com/fittings/main.jpg",
                        "image_urls": [],
                        "description": "Parsed description",
                    },
                    create=True,
                ), patch.object(catalog, "prepare_fitting_gallery_images") as prepare_gallery_mock, patch.object(
                    catalog,
                    "create_fitting",
                ) as create_mock:
                    response = client.post(
                        "/catalog/fittings",
                        json={
                            "name": "https://viyar.ua/ua/catalog/no-images",
                            "source_url": "https://viyar.ua/ua/catalog/no-images",
                            "fitting_type": "drawer_slides",
                            "fitting_group": "fittings",
                        },
                        headers=self._auth_headers("trial-token"),
                    )

                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()["success"])
                self.assertEqual(
                    response.json()["error"],
                    "Не вдалося отримати дані за посиланням. Перевірте посилання або спробуйте пізніше.",
                )
                prepare_gallery_mock.assert_not_called()
                create_mock.assert_not_called()

    def _assert_source_import_rejected_without_create(
        self,
        *,
        payload_name: str,
        expected_article: str | None,
    ) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with patch.object(
                    catalog,
                    "parse_fitting_source_metadata",
                    return_value={
                        "success": False,
                        "source_site": "viyar",
                        "error": "Page.goto: net::ERR_NETWORK_ACCESS_DENIED",
                    },
                ) as parse_mock, patch.object(catalog, "create_fitting") as create_mock:
                    with session_factory() as session:
                        before_count = session.query(FittingModel).count()

                    response = client.post(
                        "/catalog/fittings",
                        json={
                            "name": payload_name,
                            "source_url": "https://viyar.ua/ua/catalog/broken-fitting",
                            "article": expected_article,
                            "fitting_type": "drawer_slides",
                            "fitting_group": "fittings",
                        },
                        headers=self._auth_headers("trial-token"),
                    )

                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()["success"])
                self.assertEqual(
                    response.json()["error"],
                    "Не вдалося отримати дані за посиланням. Перевірте посилання або спробуйте пізніше.",
                )
                self.assertNotIn("Page.goto", response.json()["error"])
                parse_mock.assert_called_once()
                create_mock.assert_not_called()

                with session_factory() as session:
                    after_count = session.query(FittingModel).count()

                self.assertEqual(before_count, after_count)

    def test_free_user_cannot_create_fitting(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (_session_factory, client):
                with _session_factory() as session:
                    before_count = session.query(FittingModel).count()

                response = client.post(
                    "/catalog/fittings",
                    json={
                        "name": "Free Fitting",
                        "fitting_type": "drawer_slides",
                        "fitting_group": "fittings",
                    },
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(response.status_code, 403)

                with _session_factory() as session:
                    after_count = session.query(FittingModel).count()

                self.assertEqual(before_count, after_count)

    def test_free_user_cannot_update_or_delete_fitting_without_entitlements(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    fitting = FittingModel(
                        name="Free Owned Fitting",
                        fitting_type="drawer_slides",
                        fitting_group="fittings",
                        owner_user_id="free-user",
                        is_system=False,
                        is_active=True,
                    )
                    session.add(fitting)
                    session.commit()
                    fitting_id = str(fitting.id)

                update_response = client.put(
                    f"/catalog/fittings/{fitting_id}",
                    json={
                        "name": "Free Owned Fitting Updated",
                        "fitting_type": "drawer_slides",
                        "fitting_group": "fittings",
                    },
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(update_response.status_code, 403)
                self.assertEqual(update_response.json()["detail"]["error"], "Insufficient permissions")

                delete_response = client.delete(
                    f"/catalog/fittings/{fitting_id}",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(delete_response.status_code, 403)
                self.assertEqual(delete_response.json()["detail"]["error"], "Insufficient permissions")

                with session_factory() as session:
                    fitting = session.get(FittingModel, int(fitting_id))
                    self.assertIsNotNone(fitting)
                    self.assertEqual(fitting.name, "Free Owned Fitting")

    def test_admin_created_fitting_is_system_and_visible_to_trial(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                created = client.post(
                    "/catalog/fittings",
                    json={
                        "name": "Admin Fitting",
                        "fitting_type": "drawer_slides",
                        "fitting_group": "fittings",
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(created.status_code, 200)
                self.assertTrue(created.json()["success"])
                fitting_id = str(created.json()["item"]["id"])

                with session_factory() as session:
                    fitting = session.get(FittingModel, int(fitting_id))
                    self.assertIsNotNone(fitting)
                    self.assertIsNone(fitting.owner_user_id)
                    self.assertTrue(fitting.is_system)

                detail = client.get(
                    f"/catalog/fittings/{fitting_id}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(detail.status_code, 200)
                self.assertTrue(detail.json()["success"])
                self.assertEqual(detail.json()["item"]["id"], int(fitting_id))

                denied_update = client.put(
                    f"/catalog/fittings/{fitting_id}",
                    json={
                        "name": "Blocked Update",
                        "fitting_type": "drawer_slides",
                        "fitting_group": "fittings",
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(denied_update.status_code, 200)
                self.assertFalse(denied_update.json()["success"])

                denied_delete = client.delete(
                    f"/catalog/fittings/{fitting_id}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(denied_delete.status_code, 200)
                self.assertFalse(denied_delete.json()["success"])

    def test_trial_user_cannot_see_private_fitting_by_id_or_image(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    private_fitting = FittingModel(
                        name="Private Fitting",
                        fitting_type="drawer_slides",
                        fitting_group="fittings",
                        owner_user_id="owner-1",
                        is_system=False,
                        is_active=True,
                        image_cached_bytes=b"private-bytes",
                        image_cached_content_type="image/png",
                    )
                    session.add(private_fitting)
                    session.commit()
                    fitting_id = str(private_fitting.id)

                detail = client.get(
                    f"/catalog/fittings/{fitting_id}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(detail.status_code, 404)

                image = client.get(
                    f"/catalog/fittings/{fitting_id}/image",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(image.status_code, 404)

    def test_free_user_with_view_entitlement_sees_only_system_fittings(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add_all(
                        [
                            FittingModel(
                                name="System Fitting",
                                fitting_type="drawer_slides",
                                fitting_group="fittings",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                            ),
                            FittingModel(
                                name="Private Fitting",
                                fitting_type="drawer_slides",
                                fitting_group="fittings",
                                owner_user_id="owner-1",
                                is_system=False,
                                is_active=True,
                            ),
                        ]
                    )
                    session.commit()

                response = client.get(
                    "/catalog/fittings",
                    headers=self._auth_headers("free-token"),
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                names = {item["name"] for item in payload["items"]}
                self.assertIn("System Fitting", names)
                self.assertNotIn("Private Fitting", names)

    def test_fitting_view_entitlement_false_blocks_list_detail_and_images(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._set_fitting_bool_entitlement(session, "fittings.view", "trial", False)
                    system_fitting = FittingModel(
                        name="System Fitting",
                        fitting_type="drawer_slides",
                        fitting_group="fittings",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                        image_cached_bytes=b"system-bytes",
                        image_cached_content_type="image/png",
                    )
                    private_fitting = FittingModel(
                        name="Private Fitting",
                        fitting_type="drawer_slides",
                        fitting_group="fittings",
                        owner_user_id="owner-1",
                        is_system=False,
                        is_active=True,
                    )
                    session.add_all([system_fitting, private_fitting])
                    session.flush()
                    private_fitting_id = str(private_fitting.id)
                    system_fitting_id = str(system_fitting.id)
                    session.commit()

                with session_factory() as session:
                    before_count = session.query(FittingModel).count()

                list_response = client.get(
                    "/catalog/fittings",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(list_response.status_code, 403)

                detail_response = client.get(
                    f"/catalog/fittings/{system_fitting_id}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(detail_response.status_code, 403)

                image_response = client.get(
                    f"/catalog/fittings/{system_fitting_id}/image",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(image_response.status_code, 403)

                gallery_response = client.get(
                    f"/catalog/fittings/{private_fitting_id}/images/1",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(gallery_response.status_code, 403)

                admin_list = client.get(
                    "/catalog/fittings",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(admin_list.status_code, 200)
                self.assertTrue(admin_list.json()["success"])

                admin_detail = client.get(
                    f"/catalog/fittings/{private_fitting_id}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(admin_detail.status_code, 200)
                self.assertTrue(admin_detail.json()["success"])

                with session_factory() as session:
                    after_count = session.query(FittingModel).count()

                self.assertEqual(before_count, after_count)

    def test_supplier_listing_shows_system_and_current_user_suppliers_only(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.execute(
                        text(
                            """
                            INSERT INTO users (id, email, password_hash, role, is_active)
                            VALUES (:id, :email, :password_hash, :role, :is_active)
                            """
                        ),
                        [
                            {
                                "id": "owner-1",
                                "email": "owner@example.com",
                                "password_hash": "hash-owner",
                                "role": "trial",
                                "is_active": True,
                            },
                            {
                                "id": "pro-user",
                                "email": "pro@example.com",
                                "password_hash": "hash-pro",
                                "role": "pro",
                                "is_active": True,
                            },
                            {
                                "id": "stranger-user",
                                "email": "stranger@example.com",
                                "password_hash": "hash-stranger",
                                "role": "trial",
                                "is_active": True,
                            },
                        ],
                    )
                    session.commit()
                    session.add_all(
                        [
                            SupplierModel(
                                code="viyar",
                                name="VIYAR",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                            ),
                            SupplierModel(
                                code="private-a",
                                name="Private A",
                                owner_user_id="owner-1",
                                is_system=False,
                                is_active=True,
                            ),
                            SupplierModel(
                                code="private-b",
                                name="Private B",
                                owner_user_id="stranger-user",
                                is_system=False,
                                is_active=True,
                            ),
                        ]
                    )
                    session.commit()

                owner_response = client.get(
                    "/catalog/suppliers",
                    headers=self._auth_headers("owner-token"),
                )
                self.assertEqual(owner_response.status_code, 200)
                owner_codes = {item["code"] for item in owner_response.json()["items"]}
                self.assertIn("viyar", owner_codes)
                self.assertIn("private-a", owner_codes)
                self.assertNotIn("private-b", owner_codes)

                stranger_response = client.get(
                    "/catalog/suppliers",
                    headers=self._auth_headers("stranger-token"),
                )
                self.assertEqual(stranger_response.status_code, 200)
                stranger_codes = {item["code"] for item in stranger_response.json()["items"]}
                self.assertIn("viyar", stranger_codes)
                self.assertIn("private-b", stranger_codes)
                self.assertNotIn("private-a", stranger_codes)

                admin_response = client.get(
                    "/catalog/suppliers",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(admin_response.status_code, 200)
                admin_codes = {item["code"] for item in admin_response.json()["items"]}
                self.assertEqual(admin_codes, {"viyar"})

    def test_supplier_crud_respects_ownership_and_dependency_blocks(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.execute(
                        text(
                            """
                            INSERT INTO users (id, email, password_hash, role, is_active)
                            VALUES (:id, :email, :password_hash, :role, :is_active)
                            """
                        ),
                        [
                            {
                                "id": "owner-1",
                                "email": "owner@example.com",
                                "password_hash": "hash-owner",
                                "role": "trial",
                                "is_active": True,
                            },
                            {
                                "id": "pro-user",
                                "email": "pro@example.com",
                                "password_hash": "hash-pro",
                                "role": "pro",
                                "is_active": True,
                            },
                            {
                                "id": "stranger-user",
                                "email": "stranger@example.com",
                                "password_hash": "hash-stranger",
                                "role": "trial",
                                "is_active": True,
                            },
                        ],
                    )
                    session.commit()
                    session.add_all(
                        [
                            SupplierModel(
                                code="shared-viyar",
                                name="VIYAR",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                            ),
                            SupplierModel(
                                code="owner-supplier",
                                name="Owner Supplier",
                                owner_user_id="owner-1",
                                is_system=False,
                                is_active=True,
                            ),
                        ]
                    )
                    session.commit()

                owner_list = client.get(
                    "/catalog/suppliers",
                    headers=self._auth_headers("owner-token"),
                )
                self.assertEqual(owner_list.status_code, 200)
                owner_codes = {item["code"] for item in owner_list.json()["items"]}
                self.assertIn("shared-viyar", owner_codes)
                self.assertIn("owner-supplier", owner_codes)

                stranger_list = client.get(
                    "/catalog/suppliers",
                    headers=self._auth_headers("stranger-token"),
                )
                self.assertEqual(stranger_list.status_code, 200)
                stranger_codes = {item["code"] for item in stranger_list.json()["items"]}
                self.assertIn("shared-viyar", stranger_codes)
                self.assertNotIn("owner-supplier", stranger_codes)

                created = client.post(
                    "/catalog/suppliers",
                    json={
                        "name": "Owner Created Supplier",
                        "code": "",
                        "is_active": True,
                        "is_system": False,
                    },
                    headers=self._auth_headers("pro-token"),
                )
                self.assertEqual(created.status_code, 200)
                created_payload = created.json()
                self.assertTrue(created_payload["success"])
                self.assertEqual(created_payload["item"]["owner_user_id"], "pro-user")
                self.assertFalse(created_payload["item"]["is_system"])
                self.assertTrue(created_payload["item"]["code"])
                created_supplier_id = created_payload["item"]["id"]

                updated = client.patch(
                    f"/catalog/suppliers/{created_supplier_id}",
                    json={
                        "name": "Owner Created Supplier Updated",
                        "code": created_payload["item"]["code"],
                        "is_active": False,
                        "is_system": False,
                    },
                    headers=self._auth_headers("pro-token"),
                )
                self.assertEqual(updated.status_code, 200)
                updated_payload = updated.json()
                self.assertTrue(updated_payload["success"])
                self.assertEqual(updated_payload["item"]["name"], "Owner Created Supplier Updated")
                self.assertFalse(updated_payload["item"]["is_active"])

                deleted = client.delete(
                    f"/catalog/suppliers/{created_supplier_id}",
                    headers=self._auth_headers("pro-token"),
                )
                self.assertEqual(deleted.status_code, 200)
                self.assertTrue(deleted.json()["success"])

                with session_factory() as session:
                    self.assertIsNone(session.get(SupplierModel, int(created_supplier_id)))

                with session_factory() as session:
                    fitting = FittingModel(
                        name="Offer-linked fitting",
                        article="SUP-DEPENDENCY",
                        fitting_type="drawer_slides",
                        fitting_group="fittings",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    session.add(fitting)
                    session.flush()
                    supplier = session.query(SupplierModel).filter(SupplierModel.code == "shared-viyar").one()
                    session.add(
                        FittingSupplierOfferModel(
                            fitting_id=fitting.id,
                            supplier_id=supplier.id,
                            article="SUP-DEPENDENCY",
                            source_url=None,
                            price=12.5,
                            currency="UAH",
                            unit="шт",
                            stock="in stock",
                            is_active=True,
                            priority=100,
                        )
                    )
                    session.commit()
                    supplier_id = int(supplier.id)

                blocked_delete = client.delete(
                    f"/catalog/suppliers/{supplier_id}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(blocked_delete.status_code, 200)
                self.assertFalse(blocked_delete.json()["success"])
                self.assertIn("used by fitting offers", blocked_delete.json()["error"])

    def test_pro_and_business_users_can_create_update_and_delete_own_fittings(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                for token, expected_owner_id in (
                    ("pro-token", "pro-user"),
                    ("business-token", "business-user"),
                ):
                    created = client.post(
                        "/catalog/fittings",
                        json={
                            "name": f"{expected_owner_id} Fitting",
                            "fitting_type": "drawer_slides",
                            "fitting_group": "fittings",
                        },
                        headers=self._auth_headers(token),
                    )
                    self.assertEqual(created.status_code, 200)
                    self.assertTrue(created.json()["success"])
                    fitting_id = str(created.json()["item"]["id"])

                    with session_factory() as session:
                        fitting = session.get(FittingModel, int(fitting_id))
                        self.assertIsNotNone(fitting)
                        self.assertEqual(fitting.owner_user_id, expected_owner_id)
                        self.assertFalse(fitting.is_system)

                    updated = client.put(
                        f"/catalog/fittings/{fitting_id}",
                        json={
                            "name": f"{expected_owner_id} Fitting Updated",
                            "fitting_type": "drawer_slides",
                            "fitting_group": "fittings",
                            "is_system": True,
                        },
                        headers=self._auth_headers(token),
                    )
                    self.assertEqual(updated.status_code, 200)
                    self.assertTrue(updated.json()["success"])
                    self.assertFalse(updated.json()["item"]["is_system"])

                    deleted = client.delete(
                        f"/catalog/fittings/{fitting_id}",
                        headers=self._auth_headers(token),
                    )
                    self.assertEqual(deleted.status_code, 200)
                    self.assertTrue(deleted.json()["success"])

                    with session_factory() as session:
                        self.assertIsNone(session.get(FittingModel, int(fitting_id)))

    def test_fitting_detail_returns_characteristics_and_images(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    system_fitting = FittingModel(
                        name="Стяжка VB 35/16, чорна (79642) Hettich",
                        article="57839",
                        fitting_type="connector",
                        fitting_group="fittings",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                        source="viyar",
                        source_url="https://example.com/system-fitting",
                        unit=None,
                        currency=None,
                        description=None,
                        brand=None,
                        stock=None,
                        parsed_at=datetime(2026, 7, 21, 10, 30, 0),
                        price_updated_at=datetime(2026, 7, 21, 11, 15, 0),
                        source_payload_json=json.dumps(
                            {
                                "parsed_item": {
                                    "characteristics": {
                                        "Тип товару": "Стяжки",
                                        "Тип стяжки": "Полицетримач",
                                        "Тип шліца": "PZ2",
                                        "Виробник": "Hettich",
                                        "Вага, кг": "0.0049",
                                        "Глибина сверління, мм": "12,5",
                                        "Країна виробник": "Німеччина",
                                        "Товщина плити max, мм": "16",
                                        "Довжина (L), мм": "16",
                                        "Діаметр, мм": "20",
                                        "Матеріал виготовлення": "Метал, пластик",
                                        "Колір": "Чорний",
                                    },
                                    "description": "Стяжка VB 35/16, чорна (79642) Hettich",
                                    "brand": "Hettich",
                                    "currency": "UAH",
                                    "normalized_unit": "шт",
                                    "availability": "В наявності",
                                }
                            },
                            ensure_ascii=False,
                        ),
                    )
                    private_fitting = FittingModel(
                        name="Private Fitting",
                        article="PRIVATE-57839",
                        fitting_type="connector",
                        fitting_group="fittings",
                        owner_user_id="owner-1",
                        is_system=False,
                        is_active=True,
                    )
                    session.add_all([system_fitting, private_fitting])
                    session.flush()
                    session.add(
                        FittingImageModel(
                            fitting_id=system_fitting.id,
                            sort_order=0,
                            is_primary=True,
                            source_url="https://example.com/system-fitting-image.png",
                            image_cached_bytes=b"fitting-image-bytes",
                            image_cached_content_type="image/png",
                            image_sha256=sha256(b"fitting-image-bytes").hexdigest(),
                        )
                    )
                    session.commit()
                    system_fitting_id = str(system_fitting.id)
                    private_fitting_id = str(private_fitting.id)

                admin_response = client.get(
                    f"/catalog/fittings/{system_fitting_id}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(admin_response.status_code, 200)
                self.assertTrue(admin_response.json()["success"])
                admin_item = admin_response.json()["item"]
                self.assertEqual(admin_item["id"], int(system_fitting_id))
                self.assertEqual(admin_item["source_site"], "viyar")
                self.assertEqual(admin_item["brand"], "Hettich")
                self.assertEqual(admin_item["currency"], "UAH")
                self.assertEqual(admin_item["unit"], "шт")
                self.assertEqual(admin_item["availability"], "В наявності")
                self.assertEqual(admin_item["description"], "Стяжка VB 35/16, чорна (79642) Hettich")
                self.assertTrue(admin_item["characteristics"])
                self.assertEqual(admin_item["characteristics"]["Тип товару"], "Стяжки")
                self.assertEqual(len(admin_item["images"]), 1)
                self.assertEqual(admin_item["images"][0]["content_type"], "image/png")

                trial_response = client.get(
                    f"/catalog/fittings/{system_fitting_id}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(trial_response.status_code, 200)
                self.assertTrue(trial_response.json()["success"])
                trial_item = trial_response.json()["item"]
                self.assertEqual(trial_item["characteristics"]["Виробник"], "Hettich")
                self.assertEqual(len(trial_item["images"]), 1)

                private_response = client.get(
                    f"/catalog/fittings/{private_fitting_id}",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(private_response.status_code, 404)

                admin_private_response = client.get(
                    f"/catalog/fittings/{private_fitting_id}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(admin_private_response.status_code, 200)
                self.assertTrue(admin_private_response.json()["success"])
                self.assertEqual(admin_private_response.json()["item"]["id"], int(private_fitting_id))

    def test_fitting_detail_reopens_mt_source_payload_with_base_fields(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    mt_fitting = FittingModel(
                        name="CLIP top BLUMOTION спеціальна завіса 110°",
                        article="092799",
                        fitting_type="connector",
                        fitting_group="fittings",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                        source="mt",
                        source_url="https://mt.ua/products/petlya-clip-top-blumotion-110-nakladnaya-specialnaya-chernyj-61148",
                        unit="шт",
                        currency="UAH",
                        description=None,
                        brand="BLUM",
                        stock="in stock",
                        price=138.8,
                        parsed_at=datetime(2026, 8, 17, 10, 30, 0),
                        price_updated_at=datetime(2026, 8, 17, 11, 15, 0),
                        source_payload_json=json.dumps(
                            {
                                "parsed_item": {
                                    "article": "092799",
                                    "price": 138.8,
                                    "currency": "UAH",
                                    "unit": "шт",
                                    "availability": "in stock",
                                    "brand": "BLUM",
                                    "characteristics": {
                                        "Система завіс": "CLIP top BLUMOTION",
                                        "Ø чашки завіси, мм": "35",
                                        "Кут відкривання завіси, °": "110",
                                        "Бренд": "BLUM",
                                    },
                                }
                            },
                            ensure_ascii=False,
                        ),
                    )
                    session.add(mt_fitting)
                    session.flush()
                    session.add(
                        FittingImageModel(
                            fitting_id=mt_fitting.id,
                            sort_order=0,
                            is_primary=True,
                            source_url="https://cdn.example.com/mt-image.png",
                            image_cached_bytes=b"mt-image-bytes",
                            image_cached_content_type="image/png",
                            image_sha256=sha256(b"mt-image-bytes").hexdigest(),
                        )
                    )
                    session.commit()
                    mt_fitting_id = str(mt_fitting.id)

                response = client.get(
                    f"/catalog/fittings/{mt_fitting_id}",
                    headers=self._auth_headers("admin-token"),
                )

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["success"])
                item = response.json()["item"]
                self.assertEqual(item["article"], "092799")
                self.assertEqual(item["price"], 138.8)
                self.assertEqual(item["currency"], "UAH")
                self.assertEqual(item["unit"], "шт")
                self.assertEqual(item["availability"], "in stock")
                self.assertEqual(item["brand"], "BLUM")
                self.assertTrue(item["characteristics"])
                self.assertEqual(item["characteristics"]["Система завіс"], "CLIP top BLUMOTION")
                self.assertEqual(len(item["images"]), 1)
                self.assertEqual(item["images"][0]["content_type"], "image/png")

    def test_fitting_holes_use_false_blocks_non_admin_write_endpoints_and_keeps_admin_bypass(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._set_fitting_bool_entitlement(session, "fitting_holes.use", "pro", False)
                    self._set_fitting_bool_entitlement(session, "fitting_holes.use", "business", False)
                    fitting = FittingModel(
                        name="Holes Enabled Fitting",
                        fitting_type="drawer_slides",
                        fitting_group="fittings",
                        owner_user_id="trial-user",
                        is_system=False,
                        is_active=True,
                    )
                    session.add(fitting)
                    session.flush()
                    fitting_id = int(fitting.id)
                    session.commit()

                trial_response = client.post(
                    "/fitting-holes/templates",
                    json={
                        "fitting_id": fitting_id,
                        "name": "Trial Template",
                    },
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(trial_response.status_code, 200)
                self.assertTrue(trial_response.json()["success"])

                pro_response = client.post(
                    "/fitting-holes/templates",
                    json={
                        "fitting_id": fitting_id,
                        "name": "Pro Template",
                    },
                    headers=self._auth_headers("pro-token"),
                )
                self.assertEqual(pro_response.status_code, 403)

                premium_response = client.post(
                    "/fitting-holes/templates",
                    json={
                        "fitting_id": fitting_id,
                        "name": "Premium Template",
                    },
                    headers=self._auth_headers("business-token"),
                )
                self.assertEqual(premium_response.status_code, 403)

                admin_response = client.post(
                    "/fitting-holes/templates",
                    json={
                        "fitting_id": fitting_id,
                        "name": "Admin Template",
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(admin_response.status_code, 200)
                self.assertTrue(admin_response.json()["success"])

    def test_fitting_holes_use_false_blocks_get_before_resource_lookup_for_premium_role(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._set_fitting_bool_entitlement(session, "fitting_holes.use", "business", False)
                    session.commit()

                response = client.get(
                    "/fitting-holes/fittings/999999/templates",
                    headers=self._auth_headers("business-token"),
                )
                self.assertEqual(response.status_code, 403)

    def test_fitting_holes_use_false_blocks_patch_before_resource_lookup(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._set_fitting_bool_entitlement(session, "fitting_holes.use", "pro", False)
                    session.commit()

                response = client.patch(
                    "/fitting-holes/templates/999999",
                    json={
                        "name": "Blocked Patch Template",
                    },
                    headers=self._auth_headers("pro-token"),
                )
                self.assertEqual(response.status_code, 403)

    def test_fitting_holes_use_false_blocks_delete_before_resource_lookup(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    self._set_fitting_bool_entitlement(session, "fitting_holes.use", "pro", False)
                    session.commit()

                response = client.delete(
                    "/fitting-holes/points/999999",
                    headers=self._auth_headers("pro-token"),
                )
                self.assertEqual(response.status_code, 403)

    def test_fitting_holes_service_rules_remain_admin_only_even_for_allowed_non_admins(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (_session_factory, client):
                denied_response = client.get(
                    "/fitting-holes/service-rules",
                    headers=self._auth_headers("trial-token"),
                )
                self.assertEqual(denied_response.status_code, 403)

                non_admin_allowed_response = client.get(
                    "/fitting-holes/service-rules",
                    headers=self._auth_headers("pro-token"),
                )
                self.assertEqual(non_admin_allowed_response.status_code, 403)

                admin_response = client.get(
                    "/fitting-holes/service-rules",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(admin_response.status_code, 200)
                self.assertTrue(admin_response.json()["success"])

    @contextmanager
    def _catalog_context(self, database_path: Path, users_by_token: dict[str, UserStub] | None = None):
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            future=True,
        )
        event.listen(engine, "connect", _enable_foreign_keys)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)

        app = FastAPI()
        app.include_router(catalog.router, prefix="/catalog")
        app.include_router(fitting_holes_route.router, prefix="/fitting-holes")

        trial_user = UserStub(
            id="trial-user",
            email="trial@example.com",
            role="trial",
            trial_started_at=datetime.utcnow() - timedelta(hours=1),
            trial_ends_at=datetime.utcnow() + timedelta(days=6),
        )
        admin_user = UserStub(
            id="admin-user",
            email="admin@example.com",
            role="admin",
        )
        pro_user = UserStub(
            id="pro-user",
            email="pro@example.com",
            role="pro",
        )
        business_user = UserStub(
            id="business-user",
            email="business@example.com",
            role="premium",
        )
        owner_user = UserStub(
            id="owner-1",
            email="owner@example.com",
            role="trial",
        )
        stranger_user = UserStub(
            id="stranger-user",
            email="stranger@example.com",
            role="trial",
        )
        free_user = UserStub(
            id="free-user",
            email="free@example.com",
            role="free",
        )
        token_map = {
            "trial-token": trial_user,
            "admin-token": admin_user,
            "pro-token": pro_user,
            "business-token": business_user,
            "owner-token": owner_user,
            "stranger-token": stranger_user,
            "free-token": free_user,
        }
        if users_by_token:
            token_map.update(users_by_token)

        def _resolve_user(token: str):
            return token_map.get(token, trial_user)

        with (
            patch.object(inventory_repository, "SessionLocal", side_effect=session_factory),
            patch.object(material_import_job_repository, "SessionLocal", side_effect=session_factory),
            patch.object(catalog, "SessionLocal", side_effect=session_factory),
            patch.object(entitlement_service, "SessionLocal", side_effect=session_factory),
            patch.object(fitting_holes_service, "SessionLocal", side_effect=session_factory),
            patch.object(fitting_hole_service_rule_repository, "SessionLocal", side_effect=session_factory),
            patch.object(auth_dependencies, "get_user_from_token", side_effect=_resolve_user),
            patch.object(catalog, "get_user_from_token", side_effect=_resolve_user),
        ):
            with session_factory() as session:
                for feature_key, name_uk, sort_order in [
                    ("materials.view", "Доступ до каталогу матеріалів", 10),
                    ("materials.create", "Додавання власних матеріалів", 20),
                    ("materials.edit", "Редагування власних матеріалів", 30),
                    ("materials.delete", "Видалення власних матеріалів", 40),
                ]:
                    feature = EntitlementFeatureModel(
                        feature_key=feature_key,
                        name_uk=name_uk,
                        category="materials",
                        sort_order=sort_order,
                        value_type="boolean",
                    )
                    session.add(feature)
                    session.flush()
                    session.add_all(
                        [
                            PlanEntitlementModel(
                                feature_id=feature.id,
                                plan_code="trial",
                                bool_value=True,
                            ),
                            PlanEntitlementModel(
                                feature_id=feature.id,
                                plan_code="free",
                                bool_value=True,
                            ),
                            PlanEntitlementModel(
                                feature_id=feature.id,
                                plan_code="pro",
                                bool_value=True,
                            ),
                            PlanEntitlementModel(
                                feature_id=feature.id,
                                plan_code="business",
                                bool_value=True,
                            ),
                        ]
                    )

                feature = EntitlementFeatureModel(
                    feature_key="fitting_holes.use",
                    name_uk="Р”РѕСЃС‚СѓРї РґРѕ РїСЂРёСЃР°РґРєРё С„СѓСЂРЅС–С‚СѓСЂРё",
                    category="fitting_holes",
                    sort_order=60,
                    value_type="boolean",
                )
                session.add(feature)
                session.flush()
                session.add_all(
                    [
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="trial",
                            bool_value=True,
                        ),
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="free",
                            bool_value=False,
                        ),
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="pro",
                            bool_value=True,
                        ),
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="business",
                            bool_value=True,
                        ),
                    ]
                )

                feature = EntitlementFeatureModel(
                    feature_key="materials.max_owned",
                    name_uk="Максимальна кількість власних матеріалів",
                    category="materials",
                    sort_order=50,
                    value_type="integer",
                )
                session.add(feature)
                session.flush()
                session.add_all(
                    [
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="trial",
                            is_unlimited=True,
                        ),
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="free",
                            integer_value=3,
                        ),
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="pro",
                            is_unlimited=True,
                        ),
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="business",
                            is_unlimited=True,
                        ),
                    ]
                )

                for feature_key, name_uk, sort_order, values in [
                    (
                        "fittings.view",
                        "Доступ до каталогу фурнітури",
                        60,
                        {
                            "free": True,
                            "trial": True,
                            "pro": True,
                            "business": True,
                        },
                    ),
                    (
                        "fittings.create",
                        "Додавання власної фурнітури",
                        70,
                        {
                            "free": False,
                            "trial": True,
                            "pro": True,
                            "business": True,
                        },
                    ),
                    (
                        "fittings.edit",
                        "Редагування власної фурнітури",
                        80,
                        {
                            "free": False,
                            "trial": True,
                            "pro": True,
                            "business": True,
                        },
                    ),
                    (
                        "fittings.delete",
                        "Видалення власної фурнітури",
                        90,
                        {
                            "free": False,
                            "trial": True,
                            "pro": True,
                            "business": True,
                        },
                    ),
                ]:
                    feature = EntitlementFeatureModel(
                        feature_key=feature_key,
                        name_uk=name_uk,
                        category="fittings",
                        sort_order=sort_order,
                        value_type="boolean",
                    )
                    session.add(feature)
                    session.flush()
                    for plan_code, enabled in values.items():
                        session.add(
                            PlanEntitlementModel(
                                feature_id=feature.id,
                                plan_code=plan_code,
                                bool_value=enabled,
                            )
                        )
                session.commit()
            with TestClient(app) as client:
                yield session_factory, client

    @staticmethod
    def _auth_headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
        }
