from __future__ import annotations

import asyncio
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
from urllib.error import HTTPError, URLError

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
from database.models.material_image import MaterialImageModel
from database.models.canonical_edge import (
    CanonicalEdgeModel,
    EdgeSupplierOfferModel,
    EdgeSupplierOfferPriceModel,
    MaterialEdgeRelationModel,
)
from database.models.material_taxonomy import MaterialManufacturerModel
from database.models import material_edge  # noqa: F401
from database.models import material_edge_price  # noqa: F401
from database.models import material_import_job  # noqa: F401
from database.models import material_price  # noqa: F401
from database.models.material_supplier_offer import MaterialSupplierOfferModel
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
import services.material_import_queue_service as material_import_queue_service
import services.material_catalog_service as material_catalog_service
from services import fitting_source_parser
from services import viyar_parser
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
    def _material_snapshot(session, article: str) -> dict:
        material = session.query(MaterialModel).filter(MaterialModel.article == article).one()
        return {
            "article": material.article,
            "name": material.name,
            "description": material.description,
            "color": material.color,
            "dimensions": material.dimensions,
            "thickness": material.thickness,
            "manufacturer_id": material.manufacturer_id,
            "image": material.image,
            "source_url": material.source_url,
            "source": material.source,
            "product_type": material.product_type,
            "category": material.category,
            "owner_user_id": material.owner_user_id,
            "is_default": material.is_default,
            "image_source_url": material.image_source_url,
        }

    @staticmethod
    def _material_prices_snapshot(session, article: str) -> list[dict]:
        rows = (
            session.query(material_price.MaterialPriceModel)
            .filter(material_price.MaterialPriceModel.article == article)
            .order_by(material_price.MaterialPriceModel.city.asc(), material_price.MaterialPriceModel.id.asc())
            .all()
        )
        return [
            {
                "article": row.article,
                "city": row.city,
                "price": row.price,
                "currency": row.currency,
                "availability": row.availability,
                "old_price": row.old_price,
                "is_promo": row.is_promo,
                "discount_percent": row.discount_percent,
                "promo_label": row.promo_label,
                "promo_valid_until": row.promo_valid_until,
                "source_checked_at": row.source_checked_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]

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

    def test_material_detail_returns_empty_supplier_offers_when_none_exist(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="NO-OFFERS-MAT",
                            name="No Offers Material",
                            category="dsp",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    session.commit()

                detail = client.get(
                    "/catalog/materials/NO-OFFERS-MAT",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(detail.status_code, 200)
                payload = detail.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["item"]["article"], "NO-OFFERS-MAT")
                self.assertEqual(payload["item"]["supplier_offers"], [])

                with session_factory() as session:
                    material_id = session.query(MaterialModel.id).filter(MaterialModel.article == "NO-OFFERS-MAT").one()[0]

                self.assertEqual(inventory_repository.list_material_supplier_offers(material_id), [])
                helper_payload = inventory_repository.get_material_by_article("NO-OFFERS-MAT")
                self.assertIsNotNone(helper_payload)
                self.assertEqual(helper_payload["supplier_offers"], [])

    def test_material_detail_returns_linked_canonical_edge_in_edge_options(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    viyar = SupplierModel(
                        code="viyar",
                        name="VIYAR",
                        logo_url="https://example.test/viyar-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    rehau = MaterialManufacturerModel(
                        code="REHAU",
                        name="Rehau",
                        normalized_name="rehau",
                        logo_url="https://example.test/rehau-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    session.add_all([viyar, rehau])
                    session.flush()

                    material = MaterialModel(
                        id=2126,
                        article="242944",
                        name="K533 material",
                        category="dsp",
                        owner_user_id=None,
                        is_default=True,
                        source_url="https://viyar.ua/ua/catalog/dsp-lam-kronospan-k533-ad-kashtan-arvadonna-mink-e-le-vologost-p3-2800kh2070kh18-mm/?ms_q=533",
                    )
                    edge = CanonicalEdgeModel(
                        id=1,
                        manufacturer_id=rehau.id,
                        manufacturer_article="2941W",
                        name="2941W Крайка ABS Пінія темно-коричнева 23x0,8мм (150 м.п.) REHAU",
                        material_type="ABS",
                        width_mm=23.0,
                        thickness_mm=0.8,
                        image_url="https://viyar.ua/upload/resize_cache/photos/512_512_1/ph152446.jpg",
                        is_active=True,
                    )
                    relation = MaterialEdgeRelationModel(
                        material_id=2126,
                        edge_id=1,
                        relation_type="recommended",
                        source_supplier_id=viyar.id,
                        source_url="https://viyar.ua/ua/catalog/dsp-lam-kronospan-k533-ad-kashtan-arvadonna-mink-e-le-vologost-p3-2800kh2070kh18-mm/?ms_q=533",
                    )
                    offer = EdgeSupplierOfferModel(
                        id=1,
                        edge_id=1,
                        supplier_id=viyar.id,
                        article="152446",
                        source_url="https://viyar.ua/ua/catalog/2941w_kromka_abs_piniya_temno_korichnevaya_23kh0_8mm_150_m_p_rehau/",
                        unit="м.п.",
                        is_active=True,
                        priority=0,
                    )
                    offer_price = EdgeSupplierOfferPriceModel(
                        id=1,
                        offer_id=1,
                        city="kyiv",
                        price=42.36,
                        currency="UAH",
                        availability=None,
                    )
                    session.add_all([material, edge, relation, offer, offer_price])
                    session.commit()

                detail = client.get(
                    "/catalog/materials/242944",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(detail.status_code, 200)
                payload = detail.json()
                self.assertTrue(payload["success"])
                edge_options = payload["item"]["edge_options"]
                self.assertEqual(len(edge_options), 1)
                edge_item = edge_options[0]
                self.assertEqual(edge_item["id"], "1")
                self.assertEqual(edge_item["edge_key"], "recommended:1")
                self.assertEqual(edge_item["relation_type"], "recommended")
                self.assertEqual(edge_item["manufacturer_name"], "Rehau")
                self.assertEqual(edge_item["manufacturer_article"], "2941W")
                self.assertEqual(edge_item["material_type"], "ABS")
                self.assertEqual(edge_item["width_mm"], 23.0)
                self.assertEqual(edge_item["thickness_mm"], 0.8)
                self.assertEqual(edge_item["article"], "152446")
                self.assertEqual(edge_item["current_price"], 42.36)
                self.assertEqual(edge_item["current_price_city"], "kyiv")
                self.assertEqual(edge_item["source_supplier_id"], 1)
                self.assertEqual(edge_item["supplier_offers"][0]["article"], "152446")
                self.assertEqual(edge_item["supplier_offers"][0]["prices"][0]["city"], "kyiv")
                self.assertEqual(edge_item["supplier_offers"][0]["prices"][0]["price"], 42.36)

    def test_material_detail_get_does_not_call_viyar_edge_preview(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add(
                        MaterialModel(
                            article="NO-PREVIEW-MAT",
                            name="No Preview Material",
                            category="dsp",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    session.commit()

                with patch.object(
                    viyar_parser,
                    "preview_viyar_recommended_edges",
                    side_effect=AssertionError("Material detail GET must not call edge preview"),
                ) as preview_mock:
                    detail = client.get(
                        "/catalog/materials/NO-PREVIEW-MAT",
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(detail.status_code, 200)
                self.assertTrue(detail.json()["success"])
                preview_mock.assert_not_called()

    def test_material_detail_serializes_material_supplier_offers_with_supplier_profiles(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    viyar = SupplierModel(
                        code="viyar",
                        name="VIYAR",
                        logo_url="https://example.test/viyar-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    kronas = SupplierModel(
                        code="kronas",
                        name="KRONAS",
                        logo_url="https://example.test/kronas-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=False,
                    )
                    session.add_all(
                        [
                            viyar,
                            kronas,
                            MaterialModel(
                                article="WITH-OFFERS-MAT",
                                name="With Offers Material",
                                category="dsp",
                                owner_user_id=None,
                                is_default=True,
                            ),
                            material_price.MaterialPriceModel(
                                article="WITH-OFFERS-MAT",
                                city="kyiv",
                                price=99.5,
                                currency="UAH",
                                availability="В наявності",
                            ),
                        ]
                    )
                    session.commit()

                    material = session.query(MaterialModel).filter(MaterialModel.article == "WITH-OFFERS-MAT").one()
                    session.add_all(
                        [
                            MaterialSupplierOfferModel(
                                material_id=material.id,
                                supplier_id=viyar.id,
                                article="VIYAR-123",
                                external_product_id="viyar-offer-1",
                                source_url="https://example.test/viyar/material",
                                price=88.0,
                                currency="UAH",
                                unit="лист",
                                stock="12 шт",
                                city="Kyiv",
                                region="Kyivska oblast",
                                is_active=True,
                                priority=10,
                            ),
                            MaterialSupplierOfferModel(
                                material_id=material.id,
                                supplier_id=kronas.id,
                                article="KRONAS-777",
                                external_product_id=None,
                                source_url="https://example.test/kronas/material",
                                price=91.25,
                                currency="UAH",
                                unit="лист",
                                stock="0",
                                city="Lviv",
                                region="Lvivska oblast",
                                is_active=False,
                                priority=20,
                            ),
                        ]
                    )
                    session.commit()

                    stored_offer = session.query(MaterialSupplierOfferModel).filter(
                        MaterialSupplierOfferModel.supplier_id == viyar.id
                    ).one()

                detail = client.get(
                    "/catalog/materials/WITH-OFFERS-MAT",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(detail.status_code, 200)
                payload = detail.json()["item"]
                self.assertEqual(payload["article"], "WITH-OFFERS-MAT")
                self.assertEqual(payload["supplier_offers"][0]["supplier_name"], "VIYAR")
                self.assertEqual(payload["supplier_offers"][0]["supplier_logo_url"], "https://example.test/viyar-logo.png")
                self.assertEqual(payload["supplier_offers"][0]["stock"], "12 шт")
                self.assertEqual(payload["supplier_offers"][0]["city"], "Kyiv")
                self.assertEqual(payload["supplier_offers"][0]["region"], "Kyivska oblast")
                self.assertTrue(payload["supplier_offers"][0]["is_active"])
                self.assertEqual(payload["supplier_offers"][1]["supplier_name"], "KRONAS")
                self.assertFalse(payload["supplier_offers"][1]["is_active"])
                self.assertEqual(payload["current_price_details"]["city"], "kyiv")
                self.assertEqual(payload["current_price_details"]["price"], 99.5)
                with session_factory() as session:
                    material_id = session.query(MaterialModel.id).filter(MaterialModel.article == "WITH-OFFERS-MAT").one()[0]

                self.assertEqual(len(inventory_repository.list_material_supplier_offers(material_id)), 2)
                self.assertEqual(
                    inventory_repository.get_material_supplier_offer(stored_offer.id)["supplier_name"],
                    "VIYAR",
                )

    def test_material_detail_preserves_existing_fields_and_list_endpoint_stays_unchanged(self) -> None:
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
                        MaterialModel(
                            article="LIST-MAT",
                            name="List Material",
                            category="dsp",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    session.add(
                        material_price.MaterialPriceModel(
                            article="LIST-MAT",
                            city="kyiv",
                            price=55.0,
                            currency="UAH",
                            availability="В наявності",
                        )
                    )
                    session.commit()

                    material = session.query(MaterialModel).filter(MaterialModel.article == "LIST-MAT").one()
                    session.add(
                        MaterialSupplierOfferModel(
                            material_id=material.id,
                            supplier_id=supplier.id,
                            article="LIST-OFFER-1",
                            source_url="https://example.test/list-offer",
                            price=52.0,
                            currency="UAH",
                            unit="лист",
                            stock="7",
                            city="Kyiv",
                            region="Kyivska oblast",
                            is_active=False,
                            priority=100,
                        )
                    )
                    session.commit()

                list_response = client.get(
                    "/catalog/materials?city=kyiv&search=LIST-MAT",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(list_response.status_code, 200)
                list_payload = list_response.json()
                self.assertEqual(len(list_payload["items"]), 1)
                self.assertNotIn("supplier_offers", list_payload["items"][0])
                self.assertEqual(list_payload["items"][0]["current_price_details"]["price"], 55.0)

                detail_response = client.get(
                    "/catalog/materials/LIST-MAT",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(detail_response.status_code, 200)
                detail_payload = detail_response.json()["item"]
                self.assertEqual(detail_payload["article"], "LIST-MAT")
                self.assertEqual(detail_payload["name"], "List Material")
                self.assertEqual(detail_payload["current_price_details"]["price"], 55.0)
                self.assertEqual(detail_payload["supplier_offers"][0]["supplier_name"], "VIYAR")
                self.assertFalse(detail_payload["supplier_offers"][0]["is_active"])

    def test_material_supplier_offer_crud_flow_and_validation_contract(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add_all(
                        [
                            SupplierModel(
                                code="viyar",
                                name="VIYAR",
                                logo_url="https://example.test/viyar-logo.png",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                            ),
                            SupplierModel(
                                code="kronas",
                                name="KRONAS",
                                logo_url="https://example.test/kronas-logo.png",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                            ),
                            MaterialModel(
                                article="MAT-OFFER-CRUD",
                                name="Material Offer CRUD",
                                category="dsp",
                                owner_user_id=None,
                                is_default=True,
                            ),
                        ],
                    )
                    session.commit()
                    material_id = session.query(MaterialModel.id).filter(MaterialModel.article == "MAT-OFFER-CRUD").one()[0]
                    viyar_id = session.query(SupplierModel.id).filter(SupplierModel.code == "viyar").one()[0]
                    kronas_id = session.query(SupplierModel.id).filter(SupplierModel.code == "kronas").one()[0]

                create_response = client.post(
                    "/catalog/materials/MAT-OFFER-CRUD/supplier-offers",
                    json={
                        "supplier_id": viyar_id,
                        "article": "VIYAR-001",
                        "external_product_id": "viyar-mat-001",
                        "source_url": "https://example.test/viyar/material-001",
                        "price": 125.5,
                        "currency": "uah",
                        "unit": "лист",
                        "stock": "12",
                        "city": "Kyiv",
                        "region": "Kyivska oblast",
                        "is_active": True,
                        "priority": 10,
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(create_response.status_code, 200)
                create_payload = create_response.json()
                self.assertTrue(create_payload["success"])
                self.assertEqual(create_payload["item"]["supplier_name"], "VIYAR")
                self.assertEqual(create_payload["item"]["supplier_logo_url"], "https://example.test/viyar-logo.png")

                duplicate_response = client.post(
                    "/catalog/materials/MAT-OFFER-CRUD/supplier-offers",
                    json={
                        "supplier_id": viyar_id,
                        "article": "VIYAR-001",
                        "external_product_id": "viyar-mat-001",
                        "source_url": "https://example.test/viyar/material-001",
                        "price": 125.5,
                        "currency": "UAH",
                        "unit": "лист",
                        "stock": "12",
                        "city": "Kyiv",
                        "region": "Kyivska oblast",
                        "is_active": True,
                        "priority": 10,
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(duplicate_response.status_code, 200)
                self.assertFalse(duplicate_response.json()["success"])

                invalid_supplier_response = client.post(
                    "/catalog/materials/MAT-OFFER-CRUD/supplier-offers",
                    json={
                        "supplier_id": 999999,
                        "article": "BAD-SUPPLIER",
                        "price": 10.0,
                        "currency": "UAH",
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(invalid_supplier_response.status_code, 200)
                self.assertFalse(invalid_supplier_response.json()["success"])

                invalid_material_response = client.post(
                    "/catalog/materials/UNKNOWN-MATERIAL/supplier-offers",
                    json={
                        "supplier_id": viyar_id,
                        "article": "BAD-MATERIAL",
                        "price": 10.0,
                        "currency": "UAH",
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(invalid_material_response.status_code, 404)

                negative_price_response = client.post(
                    "/catalog/materials/MAT-OFFER-CRUD/supplier-offers",
                    json={
                        "supplier_id": kronas_id,
                        "article": "KRONAS-NEG",
                        "price": -1,
                        "currency": "UAH",
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(negative_price_response.status_code, 200)
                self.assertFalse(negative_price_response.json()["success"])

                second_offer_response = client.post(
                    "/catalog/materials/MAT-OFFER-CRUD/supplier-offers",
                    json={
                        "supplier_id": kronas_id,
                        "article": "KRONAS-002",
                        "source_url": "https://example.test/kronas/material-002",
                        "price": 118.0,
                        "currency": "UAH",
                        "unit": "лист",
                        "stock": "available",
                        "city": "Lviv",
                        "region": "Lvivska oblast",
                        "is_active": True,
                        "priority": 20,
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(second_offer_response.status_code, 200)
                self.assertTrue(second_offer_response.json()["success"])

                offers_response = client.get(
                    "/catalog/materials/MAT-OFFER-CRUD/supplier-offers",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(offers_response.status_code, 200)
                offers_payload = offers_response.json()
                self.assertEqual(len(offers_payload["items"]), 2)
                self.assertEqual(len(inventory_repository.list_material_supplier_offers(material_id)), 2)

                first_offer_id = create_payload["item"]["id"]
                update_response = client.patch(
                    f"/catalog/material-supplier-offers/{first_offer_id}",
                    json={
                        "article": "VIYAR-001-UPDATED",
                        "price": 131.0,
                        "is_active": False,
                        "priority": 5,
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(update_response.status_code, 200)
                update_payload = update_response.json()
                self.assertTrue(update_payload["success"])
                self.assertEqual(update_payload["item"]["article"], "VIYAR-001-UPDATED")
                self.assertFalse(update_payload["item"]["is_active"])

                reactivate_response = client.patch(
                    f"/catalog/material-supplier-offers/{first_offer_id}",
                    json={
                        "is_active": True,
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(reactivate_response.status_code, 200)
                self.assertTrue(reactivate_response.json()["success"])
                self.assertTrue(reactivate_response.json()["item"]["is_active"])

                delete_response = client.delete(
                    f"/catalog/material-supplier-offers/{second_offer_response.json()['item']['id']}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(delete_response.status_code, 200)
                self.assertTrue(delete_response.json()["success"])

                detail_response = client.get(
                    "/catalog/materials/MAT-OFFER-CRUD",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(detail_response.status_code, 200)
                detail_payload = detail_response.json()["item"]
                self.assertEqual(len(detail_payload["supplier_offers"]), 1)
                self.assertEqual(detail_payload["supplier_offers"][0]["supplier_name"], "VIYAR")
                self.assertTrue(detail_payload["supplier_offers"][0]["is_active"])

    def test_material_supplier_offer_manual_create_without_source_url_is_supported(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add_all(
                        [
                            SupplierModel(
                                code="viyar",
                                name="VIYAR",
                                logo_url="https://example.test/viyar-logo.png",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                            ),
                            MaterialModel(
                                article="MAT-OFFER-MANUAL",
                                name="Material Offer Manual",
                                category="dsp",
                                owner_user_id=None,
                                is_default=True,
                            ),
                        ],
                    )
                    session.commit()
                    viyar_id = session.query(SupplierModel.id).filter(SupplierModel.code == "viyar").one()[0]

                create_response = client.post(
                    "/catalog/materials/MAT-OFFER-MANUAL/supplier-offers",
                    json={
                        "supplier_id": viyar_id,
                        "article": "VIYAR-MANUAL-001",
                        "price": 99.5,
                        "currency": "UAH",
                        "unit": "лист",
                        "stock": "5",
                        "city": "Kyiv",
                        "region": "Kyivska oblast",
                        "is_active": True,
                        "priority": 1,
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(create_response.status_code, 200)
                create_payload = create_response.json()
                self.assertTrue(create_payload["success"])
                self.assertIsNone(create_payload["item"]["source_url"])

                detail_response = client.get(
                    "/catalog/materials/MAT-OFFER-MANUAL",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(detail_response.status_code, 200)
                detail_payload = detail_response.json()["item"]
                self.assertEqual(len(detail_payload["supplier_offers"]), 1)
                self.assertEqual(detail_payload["supplier_offers"][0]["supplier_name"], "VIYAR")
                self.assertIsNone(detail_payload["supplier_offers"][0]["source_url"])
                self.assertEqual(detail_payload["supplier_offers"][0]["city"], "Kyiv")
                self.assertEqual(detail_payload["supplier_offers"][0]["region"], "Kyivska oblast")

    def test_material_supplier_offer_attach_from_source_uses_url_only_and_persists_supplier_offer(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add_all(
                        [
                            SupplierModel(
                                code="kronas",
                                name="KRONAS",
                                logo_url="https://example.test/kronas-logo.png",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                            ),
                            MaterialModel(
                                article="MAT-URL-ATTACH",
                                name="Canonical MAT-URL-ATTACH",
                                category="dsp",
                                owner_user_id=None,
                                is_default=True,
                            ),
                        ],
                    )
                    session.commit()

                fetch_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "KRONAS-URL-001",
                            "name": "KRONAS 5994 PD",
                            "source_url": "https://kronas.ua/catalog/materials/url-001",
                            "price": 133.0,
                            "currency": "UAH",
                            "unit": "лист",
                            "availability": "in stock",
                            "external_product_id": "kronas-url-001",
                            "region": "Lvivska oblast",
                        },
                        {
                            "strategy": "direct_url_html",
                            "source_url": "https://kronas.ua/catalog/materials/url-001",
                            "trace": [],
                        },
                    )
                )

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_mock),
                    patch.object(
                        catalog,
                        "validate_material_supplier_offer_identity",
                        return_value={
                            "status": "compatible",
                            "conflicts": [],
                            "missing_fields": [],
                            "matched_fields": ["article", "name"],
                        },
                    ),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                ):
                    response = client.post(
                        "/catalog/materials/MAT-URL-ATTACH/supplier-offers/from-source",
                        json={
                            "source_url": "https://kronas.ua/catalog/materials/url-001",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["source_site"], "kronas")
                self.assertEqual(payload["parsed_material"]["article"], "KRONAS-URL-001")
                self.assertEqual(payload["item"]["supplier_name"], "KRONAS")
                self.assertEqual(payload["item"]["article"], "KRONAS-URL-001")
                self.assertEqual(payload["item"]["source_url"], "https://kronas.ua/catalog/materials/url-001")
                self.assertEqual(payload["item"]["price"], 133.0)
                self.assertEqual(payload["item"]["currency"], "UAH")
                self.assertEqual(payload["item"]["unit"], "лист")
                self.assertEqual(payload["item"]["stock"], "in stock")
                self.assertEqual(payload["item"]["region"], "Lvivska oblast")
                self.assertIsNotNone(payload["material_identity_validation"])
                self.assertEqual(payload["material_identity_validation"]["status"], "compatible")

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-URL-ATTACH").one()

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["supplier_name"], "KRONAS")
                self.assertEqual(offers[0]["article"], "KRONAS-URL-001")
                self.assertEqual(offers[0]["source_url"], "https://kronas.ua/catalog/materials/url-001")
                self.assertEqual(offers[0]["price"], 133.0)
                self.assertEqual(offers[0]["currency"], "UAH")
                self.assertEqual(offers[0]["unit"], "лист")
                self.assertEqual(offers[0]["stock"], "in stock")

    def test_material_import_viyar_continues_when_image_resolution_fails_and_runs_recommended_edges(self) -> None:
        control_url = (
            "https://viyar.ua/ua/catalog/"
            "dsp-lam-kronospan-k533-ad-kashtan-arvadonna-mink-e-le-vologost-p3-2800kh2070kh18-mm/"
            "?ms_q=533"
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
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
                    session.commit()

                fetch_material_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "242944",
                            "name": "ДСП лам. Kronospan K533 AD Каштан Арвадонна Мінк E-LE вологост. P3 2800x2070x18 мм",
                            "source_url": control_url,
                            "image": "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
                            "price": 5800.98,
                            "currency": "UAH",
                            "unit": "лист",
                            "stock": "В наявності",
                        },
                        {
                            "strategy": "direct_url_html",
                            "source_url": control_url,
                            "trace": [],
                        },
                    )
                )

                async def _fake_collect_material_prices_for_all_cities(**_kwargs):
                    return (
                        {
                            "article": "242944",
                            "name": "ДСП лам. Kronospan K533 AD Каштан Арвадонна Мінк E-LE вологост. P3 2800x2070x18 мм",
                            "source_url": control_url,
                            "image": "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg",
                            "price": 5800.98,
                            "currency": "UAH",
                            "unit": "лист",
                            "stock": "В наявності",
                        },
                        {
                            "kyiv": 5800.98,
                        },
                    )

                recommended_edges_mock = AsyncMock(
                    return_value={
                        "summary": {
                            "discovered": 0,
                            "persisted": 0,
                            "needs_review": 0,
                            "failed": 0,
                        }
                    }
                )

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_material_mock),
                    patch.object(
                        catalog,
                        "_collect_material_prices_for_all_cities",
                        side_effect=_fake_collect_material_prices_for_all_cities,
                    ),
                    patch.object(catalog, "prefetch_material_image_cache", return_value=None),
                    patch.object(
                        catalog,
                        "persist_viyar_recommended_edges_for_material_import",
                        new=recommended_edges_mock,
                    ),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "242944",
                            "name": "ДСП лам. Kronospan K533 AD Каштан Арвадонна Мінк E-LE вологост. P3 2800x2070x18 мм",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": control_url,
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(
                    payload["recommended_edges"],
                    {
                        "discovered": 0,
                        "persisted": 0,
                        "needs_review": 0,
                        "failed": 0,
                    },
                )
                fetch_material_mock.assert_awaited_once()
                recommended_edges_mock.assert_awaited_once()

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "242944").one()
                    jobs_after = session.query(material_import_job.MaterialImportJobModel).count()

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(jobs_after, 0)
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["supplier_name"], "VIYAR")
                self.assertEqual(offers[0]["article"], "242944")
                self.assertEqual(offers[0]["source_url"], control_url)
                self.assertEqual(material.image, "https://www.viyar.ua/store/Items/photos/ph242944_lOLfy.jpg")
                self.assertIsNone(material.image_cached_bytes)

    def test_material_detail_returns_gallery_images(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                image_one = self._make_png_bytes((10, 20, 30))
                image_two = self._make_png_bytes((40, 50, 60))

                with session_factory() as session:
                    material = MaterialModel(
                        article="MAT-GALLERY-001",
                        name="Gallery Material",
                        category="dsp",
                        owner_user_id=None,
                        is_default=True,
                        source="viyar",
                        source_url="https://viyar.ua/ua/catalog/mat-gallery-001/",
                    )
                    session.add(material)
                    session.flush()
                    session.add_all(
                        [
                            MaterialImageModel(
                                material_id=material.id,
                                sort_order=0,
                                is_primary=True,
                                source_url="https://cdn.example.com/materials/gallery-1.png",
                                image_cached_bytes=image_one,
                                image_cached_content_type="image/png",
                                image_sha256=sha256(image_one).hexdigest(),
                            ),
                            MaterialImageModel(
                                material_id=material.id,
                                sort_order=1,
                                is_primary=False,
                                source_url="https://cdn.example.com/materials/gallery-2.png",
                                image_cached_bytes=image_two,
                                image_cached_content_type="image/png",
                                image_sha256=sha256(image_two).hexdigest(),
                            ),
                        ],
                    )
                    session.commit()

                response = client.get(
                    "/catalog/materials/MAT-GALLERY-001",
                    headers=self._auth_headers("admin-token"),
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                item = payload["item"]
                self.assertEqual(item["article"], "MAT-GALLERY-001")
                self.assertEqual(len(item["images"]), 2)
                self.assertEqual([image["sort_order"] for image in item["images"]], [0, 1])
                self.assertEqual([image["is_primary"] for image in item["images"]], [True, False])
                self.assertEqual([image["content_type"] for image in item["images"]], ["image/png", "image/png"])

                image_response = client.get(
                    f"/catalog/materials/MAT-GALLERY-001/images/{item['images'][0]['id']}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(image_response.status_code, 200)
                self.assertEqual(image_response.headers["content-type"], "image/png")
                self.assertGreater(len(image_response.content), 0)

    def test_viyar_product_details_parser_detects_clean_size_badge_without_hardcoding_article(self) -> None:
        viyar_url = "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/"
        viyar_html = """
            <html>
              <body>
                <h1>ДСП лам. Kronospan K520 PD Смарагд Темний 2800х2070х18мм</h1>
                <span id="artikul" itemprop="sku">189874</span>
                <span class="price-actual">4 657.44</span><span class="text-unit">₴/лист</span>
                <div class="product-badges">Чистий розмір</div>
              </body>
            </html>
        """

        with patch.object(material_catalog_service, "_fetch_html", return_value=(viyar_html, viyar_url)):
            material, debug_payload = asyncio.run(
                material_catalog_service.fetch_viyar_product_details_by_url_traced(
                    viyar_url,
                    article_hint="189874",
                )
            )

        self.assertEqual(material["article"], "189874")
        self.assertIn("лист", material["unit"])
        self.assertEqual(material["price"], 4657.44)
        self.assertTrue(material["supports_square_meter_sale"])
        self.assertEqual(debug_payload["strategy"], "direct_url_html")
        self.assertEqual(
            [entry["stage"] for entry in debug_payload["trace"]],
            ["direct.product_url", "direct.fetch.result", "direct.extract", "direct.success"],
        )

    def test_viyar_fetch_html_builds_browser_like_request_headers_and_preserves_query(self) -> None:
        viyar_url = "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k533-ad-kashtan-arvadonna-mink-e-le-vologost-p3-2800kh2070kh18-mm/?ms_q=533"
        captured: dict[str, object] = {}

        class _DummyHeaders:
            @staticmethod
            def get_content_charset() -> None:
                return None

        class _DummyResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return b"<html><body>ok</body></html>"

            def geturl(self) -> str:
                return viyar_url

            headers = _DummyHeaders()

        def _fake_urlopen(request, timeout=10):
            captured["request"] = request
            captured["timeout"] = timeout
            return _DummyResponse()

        with patch.object(material_catalog_service, "urlopen", side_effect=_fake_urlopen):
            html, final_url = material_catalog_service._fetch_html(viyar_url, return_final_url=True)

        self.assertEqual(html, "<html><body>ok</body></html>")
        self.assertEqual(final_url, viyar_url)
        self.assertEqual(captured["timeout"], 10)

        request = captured["request"]
        self.assertEqual(request.full_url, viyar_url)
        self.assertIn("ms_q=533", request.full_url)

        header_map = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(
            header_map["user-agent"],
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        )
        self.assertEqual(header_map["accept-language"], "uk-UA,uk;q=0.9,en;q=0.8")
        self.assertEqual(header_map["accept"], "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        self.assertEqual(header_map["referer"], "https://www.viyar.ua/ua/")

    def test_viyar_product_details_parser_reports_fetch_error_diagnostics(self) -> None:
        viyar_url = "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k533-ad-kashtan-arvadonna-mink-e-le-vologost-p3-2800kh2070kh18-mm/"

        with patch.object(
            material_catalog_service,
            "_fetch_html",
            side_effect=URLError("net::ERR_NETWORK_ACCESS_DENIED"),
        ):
            with self.assertRaises(material_catalog_service.MaterialImportError) as ctx:
                asyncio.run(
                    material_catalog_service.fetch_viyar_product_details_by_url_traced(
                        viyar_url,
                        article_hint="242944",
                    )
                )

        trace_stages = [entry["stage"] for entry in ctx.exception.trace]
        self.assertIn("direct.product_url", trace_stages)
        self.assertIn("direct.fetch.error", trace_stages)
        self.assertIn("direct.error", trace_stages)
        fetch_error = next(entry for entry in ctx.exception.trace if entry["stage"] == "direct.fetch.error")
        self.assertEqual(fetch_error["error_type"], "URLError")
        self.assertIn("Viyar", fetch_error["message"])
        self.assertIn("net::ERR_NETWORK_ACCESS_DENIED", fetch_error["error_text"])
        self.assertEqual(fetch_error["article_hint"], "242944")

    def test_viyar_product_details_parser_reports_http_403_diagnostics(self) -> None:
        viyar_url = "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k533-ad-kashtan-arvadonna-mink-e-le-vologost-p3-2800kh2070kh18-mm/"

        def _fake_urlopen(request, timeout=10):
            raise HTTPError(request.full_url, 403, "Forbidden", hdrs=None, fp=None)

        with patch.object(material_catalog_service, "urlopen", side_effect=_fake_urlopen):
            with self.assertRaises(material_catalog_service.MaterialImportError) as ctx:
                asyncio.run(
                    material_catalog_service.fetch_viyar_product_details_by_url_traced(
                        viyar_url,
                        article_hint="242944",
                    )
                )

        trace_stages = [entry["stage"] for entry in ctx.exception.trace]
        self.assertIn("direct.fetch.error", trace_stages)
        self.assertIn("direct.error", trace_stages)
        fetch_error = next(entry for entry in ctx.exception.trace if entry["stage"] == "direct.fetch.error")
        self.assertEqual(fetch_error["error_type"], "HTTPError")
        self.assertEqual(fetch_error["message"], "Viyar повернув HTTP 403")
        self.assertIn("HTTP Error 403", fetch_error["error_text"])

    def test_viyar_product_details_parser_reports_extract_failure_reason(self) -> None:
        viyar_url = "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k533-ad-kashtan-arvadonna-mink-e-le-vologost-p3-2800kh2070kh18-mm/"
        viyar_html = "<html><body><div>not a product page</div></body></html>"

        with (
            patch.object(material_catalog_service, "_fetch_html", return_value=(viyar_html, viyar_url)),
            patch.object(material_catalog_service, "_extract_material_from_product_html", return_value=None),
        ):
            with self.assertRaises(material_catalog_service.MaterialImportError) as ctx:
                asyncio.run(
                    material_catalog_service.fetch_viyar_product_details_by_url_traced(
                        viyar_url,
                        article_hint="242944",
                    )
                )

        trace_stages = [entry["stage"] for entry in ctx.exception.trace]
        self.assertIn("direct.fetch.result", trace_stages)
        self.assertIn("direct.extract.failed", trace_stages)
        self.assertNotIn("direct.success", trace_stages)
        extract_failed = next(entry for entry in ctx.exception.trace if entry["stage"] == "direct.extract.failed")
        self.assertEqual(extract_failed["reason"], "material_not_found")
        self.assertFalse(extract_failed["has_material"])
        self.assertFalse(extract_failed["has_name"])

    def test_material_supplier_offer_attach_from_source_persists_viyar_square_meter_sale_flag(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
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
                        MaterialModel(
                            article="MAT-VIYAR-CLEAN-SIZE",
                            name="Kronospan K520 PD Смарагд Темний 2800x2070x18мм",
                            category="dsp",
                            dimensions="2800x2070",
                            thickness="18 мм",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    session.commit()

                fetch_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "189874",
                            "name": "ДСП лам. Kronospan K520 PD Смарагд Темний 2800x2070x18мм",
                            "source_url": "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/",
                            "price": 4657.44,
                            "currency": "UAH",
                            "unit": "лист",
                            "stock": "В наявності",
                            "supports_square_meter_sale": True,
                        },
                        {
                            "strategy": "direct_url_html",
                            "source_url": "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/",
                            "trace": [],
                        },
                    )
                )

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_mock),
                    patch.object(
                        catalog,
                        "validate_material_supplier_offer_identity",
                        return_value={
                            "status": "compatible",
                            "conflicts": [],
                            "missing_fields": [],
                            "matched_fields": ["article", "name"],
                        },
                    ),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                ):
                    response = client.post(
                        "/catalog/materials/MAT-VIYAR-CLEAN-SIZE/supplier-offers/from-source",
                        json={
                            "source_url": "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertTrue(payload["item"]["supports_square_meter_sale"])
                self.assertEqual(payload["item"]["unit"], "лист")
                self.assertEqual(payload["item"]["city"], "kyiv")

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-VIYAR-CLEAN-SIZE").one()

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(len(offers), 1)
                self.assertTrue(offers[0]["supports_square_meter_sale"])
                self.assertEqual(offers[0]["unit"], "лист")
                self.assertEqual(offers[0]["city"], "kyiv")

    def test_material_detail_does_not_hydrate_missing_viyar_clean_size_flag_from_source_url(self) -> None:
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
                        MaterialModel(
                            article="MAT-VIYAR-LIVE-LEGACY",
                            name="Kronospan K520 PD Смарагд Темний 2800x2070x18мм",
                            category="dsp",
                            dimensions="2800x2070",
                            thickness="18 мм",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    session.commit()

                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-VIYAR-LIVE-LEGACY").one()
                    session.add(
                        MaterialSupplierOfferModel(
                            material_id=material.id,
                            supplier_id=supplier.id,
                            article="189874",
                            source_url="https://viyar.ua/ua/catalog/dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/",
                            price=4657.44,
                            currency="UAH",
                            unit="лист",
                            stock="В наявності",
                            city="kyiv",
                            region=None,
                            is_active=True,
                            priority=0,
                            source_payload_json=None,
                        )
                    )
                    session.commit()

                with patch.object(
                    catalog,
                    "fetch_viyar_product_details_by_url_traced",
                    side_effect=AssertionError("GET detail must not hydrate supplier offers from external source"),
                ):
                    response = client.get(
                        "/catalog/materials/MAT-VIYAR-LIVE-LEGACY",
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()["item"]
                self.assertEqual(payload["supplier_offers"][0]["city"], "kyiv")
                self.assertIsNone(payload["supplier_offers"][0]["region"])
                self.assertIsNone(payload["supplier_offers"][0]["supports_square_meter_sale"])

    def test_material_supplier_offer_attach_from_source_resolves_kronas_alias_and_keeps_viyar_lookup_working(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    viyar_supplier = SupplierModel(
                        code="viyar",
                        name="VIYAR",
                        logo_url="https://example.test/viyar-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    kronas_supplier = SupplierModel(
                        code="supplier-b1749a95",
                        name="Кронас",
                        logo_url="https://example.test/kronas-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    session.add_all(
                        [
                            viyar_supplier,
                            kronas_supplier,
                            MaterialModel(
                                article="MAT-URL-ALIAS",
                                name="Kronospan K520 PD Смарагд Темний 2800x2070x18",
                                manufacturer_id=None,
                                category="dsp",
                                dimensions="2800x2070",
                                thickness="18 мм",
                                owner_user_id=None,
                                is_default=True,
                            ),
                        ],
                    )
                    session.commit()

                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-URL-ALIAS").one()
                    existing_offer = inventory_repository.create_material_supplier_offer(
                        material_id=material.id,
                        supplier_id=kronas_supplier.id,
                        article="139610",
                        external_product_id="legacy-kronas-139610",
                        source_url="https://kronas.com.ua/old/path/139610",
                        price=None,
                        currency="UAH",
                        unit="шт",
                        stock=None,
                        city="Kyiv",
                        region="Kyivska oblast",
                        is_active=True,
                        priority=0,
                    )
                    self.assertIsNotNone(existing_offer)
                    existing_offer_id = existing_offer["id"]
                    material_before = self._material_snapshot(session, "MAT-URL-ALIAS")

                fetch_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "139610",
                            "name": "Kronospan K520 PD Смарагд Темний 2800x2070x18мм",
                            "source_url": "https://kronas.com.ua/catalog/materials/139610",
                            "price": 219.4,
                            "currency": "UAH",
                            "unit": "шт",
                            "stock": "в наявності",
                            "external_product_id": "kronas-139610-fresh",
                            "region": "Kyivska oblast",
                        },
                        {
                            "strategy": "direct_url_html",
                            "source_url": "https://kronas.com.ua/catalog/materials/139610",
                            "trace": [],
                        },
                    )
                )

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_mock),
                    patch.object(
                        catalog,
                        "validate_material_supplier_offer_identity",
                        return_value={
                            "status": "compatible",
                            "conflicts": [],
                            "missing_fields": [],
                            "matched_fields": ["article", "name"],
                        },
                    ),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                ):
                    response = client.post(
                        "/catalog/materials/MAT-URL-ALIAS/supplier-offers/from-source",
                        json={
                            "source_url": "https://kronas.com.ua/catalog/materials/139610",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["source_site"], "kronas")
                self.assertEqual(payload["item"]["id"], existing_offer_id)
                self.assertEqual(payload["item"]["supplier_name"], "Кронас")
                self.assertEqual(payload["item"]["article"], "139610")
                self.assertEqual(payload["item"]["source_url"], "https://kronas.com.ua/catalog/materials/139610")
                self.assertEqual(payload["item"]["price"], 219.4)
                self.assertEqual(payload["item"]["currency"], "UAH")
                self.assertEqual(payload["item"]["unit"], "шт")
                self.assertEqual(payload["item"]["stock"], "в наявності")
                self.assertEqual(payload["material_identity_validation"]["status"], "compatible")
                self.assertEqual(inventory_repository.get_supplier_by_code("viyar")["code"], "viyar")
                self.assertEqual(inventory_repository.get_supplier_by_code("kronas")["name"], "Кронас")

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-URL-ALIAS").one()
                    material_after = self._material_snapshot(session, "MAT-URL-ALIAS")

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material_after, material_before)
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["id"], existing_offer_id)
                self.assertEqual(offers[0]["supplier_id"], kronas_supplier.id)
                self.assertEqual(offers[0]["supplier_name"], "Кронас")
                self.assertEqual(offers[0]["article"], "139610")
                self.assertEqual(offers[0]["source_url"], "https://kronas.com.ua/catalog/materials/139610")
                self.assertEqual(offers[0]["price"], 219.4)
                self.assertEqual(offers[0]["currency"], "UAH")
                self.assertEqual(offers[0]["unit"], "шт")
                self.assertEqual(offers[0]["stock"], "в наявності")

    def test_material_supplier_offer_attach_from_source_updates_existing_same_supplier_offer_without_duplicate(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    kronas_supplier = SupplierModel(
                        code="kronas",
                        name="KRONAS",
                        logo_url="https://example.test/kronas-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    kronospan_manufacturer = MaterialManufacturerModel(
                        name="Kronospan",
                        normalized_name="kronospan",
                        code="kronospan",
                        website_url=None,
                        logo_url=None,
                        owner_user_id=None,
                        is_active=True,
                        is_system=True,
                    )
                    session.add_all([kronas_supplier, kronospan_manufacturer])
                    session.flush()
                    session.add(
                        MaterialModel(
                            article="MAT-URL-REFRESH",
                            name="Kronospan K520 PD Смарагд Темний 2800x2070x18",
                            manufacturer_id=kronospan_manufacturer.id,
                            category="dsp",
                            dimensions="2800x2070",
                            thickness="18 мм",
                            owner_user_id=None,
                            is_default=True,
                        ),
                    )
                    session.commit()

                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-URL-REFRESH").one()
                    kronas_id = session.query(SupplierModel.id).filter(SupplierModel.code == "kronas").one()[0]
                    existing_offer = inventory_repository.create_material_supplier_offer(
                        material_id=material.id,
                        supplier_id=kronas_id,
                        article="KRONAS-LEGACY-139610",
                        external_product_id="legacy-kronas-139610",
                        source_url="https://kronas.ua/catalog/materials/legacy-139610",
                        price=None,
                        currency="UAH",
                        unit="old-unit",
                        stock=None,
                        city="Kyiv",
                        region="Kyivska oblast",
                        is_active=True,
                        priority=0,
                    )
                    self.assertIsNotNone(existing_offer)
                    existing_offer_id = existing_offer["id"]
                    material_before = self._material_snapshot(session, "MAT-URL-REFRESH")

                fetch_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "139610",
                            "name": "Kronospan K520 PD Смарагд Темний 2800x2070x18мм",
                            "source_url": "https://kronas.ua/catalog/materials/139610",
                            "price": 219.4,
                            "currency": "UAH",
                            "unit": "лист",
                            "availability": "в наявності",
                            "external_product_id": "kronas-139610-fresh",
                            "region": "Kyivska oblast",
                        },
                        {
                            "strategy": "direct_url_html",
                            "source_url": "https://kronas.ua/catalog/materials/139610",
                            "trace": [],
                        },
                    )
                )

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_mock),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                ):
                    response = client.post(
                        "/catalog/materials/MAT-URL-REFRESH/supplier-offers/from-source",
                        json={
                            "source_url": "https://kronas.ua/catalog/materials/139610",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["item"]["id"], existing_offer_id)
                self.assertEqual(payload["item"]["supplier_name"], "KRONAS")
                self.assertEqual(payload["item"]["article"], "139610")
                self.assertEqual(payload["item"]["price"], 219.4)
                self.assertEqual(payload["item"]["currency"], "UAH")
                self.assertEqual(payload["item"]["unit"], "лист")
                self.assertEqual(payload["item"]["stock"], "в наявності")
                self.assertEqual(payload["item"]["source_url"], "https://kronas.ua/catalog/materials/139610")
                self.assertEqual(payload["item"]["external_product_id"], "kronas-139610-fresh")
                self.assertEqual(payload["parsed_material"]["article"], "139610")
                self.assertEqual(payload["parsed_material"]["price"], 219.4)
                self.assertEqual(payload["material_identity_validation"]["status"], "compatible")

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-URL-REFRESH").one()
                    material_after = self._material_snapshot(session, "MAT-URL-REFRESH")

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material_after, material_before)
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["id"], existing_offer_id)
                self.assertEqual(offers[0]["supplier_name"], "KRONAS")
                self.assertEqual(offers[0]["article"], "139610")
                self.assertEqual(offers[0]["price"], 219.4)
                self.assertEqual(offers[0]["currency"], "UAH")
                self.assertEqual(offers[0]["unit"], "лист")
                self.assertEqual(offers[0]["stock"], "в наявності")
                self.assertEqual(offers[0]["source_url"], "https://kronas.ua/catalog/materials/139610")
                self.assertEqual(offers[0]["external_product_id"], "kronas-139610-fresh")

    def test_material_supplier_offer_attach_from_source_conflict_does_not_mutate(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    session.add_all(
                        [
                            SupplierModel(
                                code="kronas",
                                name="KRONAS",
                                logo_url="https://example.test/kronas-logo.png",
                                owner_user_id=None,
                                is_system=True,
                                is_active=True,
                            ),
                            MaterialModel(
                                article="MAT-URL-CONFLICT",
                                name="Canonical MAT-URL-CONFLICT",
                                category="dsp",
                                dimensions="2800x2070",
                                thickness="18 мм",
                                owner_user_id=None,
                                is_default=True,
                            ),
                        ],
                    )
                    session.commit()
                    material_before = self._material_snapshot(session, "MAT-URL-CONFLICT")

                fetch_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "KRONAS-URL-CONFLICT",
                            "name": "KRONAS 5994 PD",
                            "source_url": "https://kronas.ua/catalog/materials/conflict",
                            "price": 140.0,
                            "currency": "UAH",
                            "unit": "лист",
                            "availability": "in stock",
                        },
                        {
                            "strategy": "direct_url_html",
                            "source_url": "https://kronas.ua/catalog/materials/conflict",
                            "trace": [],
                        },
                    )
                )

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_mock),
                    patch.object(
                        catalog,
                        "validate_material_supplier_offer_identity",
                        return_value={
                            "status": "conflict",
                            "conflicts": [
                                {
                                    "field": "structure",
                                    "existing": "Canonical MAT-URL-CONFLICT",
                                    "incoming": "KRONAS 5994 PD",
                                }
                            ],
                            "missing_fields": [],
                            "matched_fields": ["article"],
                        },
                    ),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                ):
                    response = client.post(
                        "/catalog/materials/MAT-URL-CONFLICT/supplier-offers/from-source",
                        json={
                            "source_url": "https://kronas.ua/catalog/materials/conflict",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertFalse(payload["success"])
                self.assertEqual(payload["material_identity_validation"]["status"], "conflict")
                self.assertIn("conflicts with the existing canonical material", payload["error"])

                with session_factory() as session:
                    material_after = self._material_snapshot(session, "MAT-URL-CONFLICT")
                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-URL-CONFLICT").one()

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material_after, material_before)
                self.assertEqual(offers, [])

    def test_material_import_creates_supplier_offer_for_viyar_and_stays_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
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
                    session.commit()

                async def _fake_collect_material_prices_for_all_cities(**_kwargs):
                    return (
                        {
                            "article": "VIYAR-IMPORTED-1",
                            "name": "VIYAR Imported Material",
                            "source_url": "https://viyar.ua/catalog/materials/1",
                            "price": 123.45,
                            "currency": "uah",
                            "unit": "лист",
                            "stock": "10",
                            "region": "Kyivska oblast",
                            "external_product_id": "viyar-imported-1",
                        },
                        {
                            "kyiv": 123.45,
                        },
                    )

                recommended_edges_mock = AsyncMock(
                    return_value={
                        "success": True,
                        "summary": {
                            "discovered": 4,
                            "persisted": 4,
                            "needs_review": 0,
                            "failed": 0,
                        },
                    }
                )

                with (
                    patch.object(catalog, "_collect_material_prices_for_all_cities", side_effect=_fake_collect_material_prices_for_all_cities),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                    patch.object(catalog, "persist_viyar_recommended_edges_for_material_import", new=recommended_edges_mock),
                    patch.object(
                        catalog,
                        "prefetch_material_image_cache",
                        return_value={
                            "bytes": b"fake-image",
                            "content_type": "image/png",
                            "resolved_url": "https://example.test/material.png",
                        },
                    ),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "VIYAR-IMPORTED-1",
                            "name": "VIYAR Imported Material",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": "https://viyar.ua/catalog/materials/1",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                    repeat_response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "VIYAR-IMPORTED-1",
                            "name": "VIYAR Imported Material",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": "https://viyar.ua/catalog/materials/1",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["recommended_edges"], {"discovered": 4, "persisted": 4, "needs_review": 0, "failed": 0})
                self.assertEqual(
                    recommended_edges_mock.await_args.kwargs["selected_city"],
                    "kyiv",
                )
                self.assertEqual(
                    recommended_edges_mock.await_args.kwargs["relation_source_url"],
                    "https://viyar.ua/catalog/materials/1",
                )
                self.assertEqual(repeat_response.status_code, 200)
                repeat_payload = repeat_response.json()
                self.assertFalse(repeat_payload["success"])
                self.assertEqual(repeat_payload["error"], "Incoming material needs review before it can be attached.")
                self.assertIsNone(repeat_payload["recommended_edges"])
                self.assertEqual(recommended_edges_mock.await_count, 1)

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "VIYAR-IMPORTED-1").one()
                    supplier_id = session.query(SupplierModel.id).filter(SupplierModel.code == "viyar").one()[0]

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material.source, "viyar")
                self.assertEqual(material.source_url, "https://viyar.ua/catalog/materials/1")
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["supplier_id"], supplier_id)
                self.assertEqual(offers[0]["article"], "VIYAR-IMPORTED-1")
                self.assertEqual(offers[0]["source_url"], "https://viyar.ua/catalog/materials/1")
                self.assertEqual(offers[0]["price"], 123.45)
                self.assertEqual(offers[0]["currency"], "UAH")
                self.assertEqual(offers[0]["unit"], "лист")
                self.assertEqual(offers[0]["city"], "kyiv")

    def test_material_import_viyar_recommended_edges_failure_does_not_block_material_import(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
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
                    session.commit()

                fetch_material_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "VIYAR-IMPORTED-2",
                            "name": "VIYAR Imported Material 2",
                            "source_url": "https://viyar.ua/catalog/materials/2",
                            "price": 123.45,
                            "currency": "uah",
                            "unit": "лист",
                            "stock": "10",
                            "region": "Kyivska oblast",
                            "external_product_id": "viyar-imported-2",
                        },
                        {
                            "strategy": "direct_url_html",
                            "source_url": "https://viyar.ua/catalog/materials/2",
                            "trace": [],
                        },
                    )
                )

                async def _fake_collect_material_prices_for_all_cities(**_kwargs):
                    return (
                        {
                            "article": "VIYAR-IMPORTED-2",
                            "name": "VIYAR Imported Material 2",
                            "source_url": "https://viyar.ua/catalog/materials/2",
                            "price": 123.45,
                            "currency": "uah",
                            "unit": "лист",
                            "stock": "10",
                            "region": "Kyivska oblast",
                            "external_product_id": "viyar-imported-2",
                        },
                        {
                            "kyiv": 123.45,
                        },
                )

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_material_mock),
                    patch.object(catalog, "_collect_material_prices_for_all_cities", side_effect=_fake_collect_material_prices_for_all_cities),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                    patch.object(catalog, "persist_viyar_recommended_edges_for_material_import", side_effect=RuntimeError("edge preview failed")),
                    patch.object(
                        catalog,
                        "prefetch_material_image_cache",
                        return_value={
                            "bytes": b"fake-image",
                            "content_type": "image/png",
                            "resolved_url": "https://example.test/material.png",
                        },
                    ),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "VIYAR-IMPORTED-2",
                            "name": "VIYAR Imported Material 2",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": "https://viyar.ua/catalog/materials/2",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["recommended_edges"], {"discovered": 0, "persisted": 0, "needs_review": 0, "failed": 1})
                fetch_material_mock.assert_awaited_once()

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "VIYAR-IMPORTED-2").one()
                    supplier_id = session.query(SupplierModel.id).filter(SupplierModel.code == "viyar").one()[0]

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["supplier_id"], supplier_id)
                self.assertEqual(offers[0]["source_url"], "https://viyar.ua/catalog/materials/2")

    def test_material_import_creates_first_offer_from_source_url_without_article(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
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
                    session.commit()

                fetch_material_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "VIYAR-URL-ONLY-1",
                            "name": "VIYAR URL Imported Material",
                            "source_url": "https://viyar.ua/catalog/materials/url-only-1",
                            "price": 210.0,
                            "currency": "uah",
                            "unit": "лист",
                            "stock": "12",
                            "region": "Kyivska oblast",
                            "external_product_id": "viyar-url-only-1",
                        },
                        {
                            "strategy": "direct_url_html",
                            "source_url": "https://viyar.ua/catalog/materials/url-only-1",
                            "trace": [],
                        },
                    )
                )

                collect_prices_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "VIYAR-URL-ONLY-1",
                            "name": "VIYAR URL Imported Material",
                            "source_url": "https://viyar.ua/catalog/materials/url-only-1",
                            "price": 210.0,
                            "currency": "uah",
                            "unit": "лист",
                            "stock": "12",
                            "region": "Kyivska oblast",
                            "external_product_id": "viyar-url-only-1",
                        },
                        {
                            "kyiv": 210.0,
                        },
                    )
                )

                with (
                    patch.object(
                        catalog,
                        "fetch_material_by_source_url_live_traced",
                        new=fetch_material_mock,
                    ),
                    patch.object(catalog, "_collect_material_prices_for_all_cities", new=collect_prices_mock),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                    patch.object(
                        catalog,
                        "prefetch_material_image_cache",
                        return_value={
                            "bytes": b"fake-image",
                            "content_type": "image/png",
                            "resolved_url": "https://example.test/material.png",
                        },
                    ),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": "https://viyar.ua/catalog/materials/url-only-1",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["item"]["article"], "VIYAR-URL-ONLY-1")
                self.assertIsNone(payload["material_identity_validation"])
                fetch_material_mock.assert_awaited_once()
                collect_prices_mock.assert_awaited_once()

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "VIYAR-URL-ONLY-1").one()
                    supplier_id = session.query(SupplierModel.id).filter(SupplierModel.code == "viyar").one()[0]

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material.source, "viyar")
                self.assertEqual(material.source_url, "https://viyar.ua/catalog/materials/url-only-1")
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["supplier_id"], supplier_id)
                self.assertEqual(offers[0]["article"], "VIYAR-URL-ONLY-1")
                self.assertEqual(offers[0]["source_url"], "https://viyar.ua/catalog/materials/url-only-1")
                self.assertEqual(offers[0]["price"], 210.0)

    def test_material_import_viyar_source_url_with_article_still_uses_url_first_parsed_material(self) -> None:
        control_url = (
            "https://viyar.ua/ua/catalog/"
            "dsp-lam-kronospan-k533-ad-kashtan-arvadonna-mink-e-le-vologost-p3-2800kh2070kh18-mm/"
            "?ms_q=533"
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
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
                    session.commit()

                fetch_material_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "242944",
                            "name": "ДСП лам. Kronospan K533 AD Каштан Арвадонна Мінк E-LE вологост. P3 2800x2070x18 мм",
                            "source_url": control_url,
                            "price": 5800.98,
                            "currency": "UAH",
                            "unit": "лист",
                            "stock": "В наявності",
                            "dimensions": "2800x2070x18 мм",
                            "thickness": "18 мм",
                            "external_product_id": "viyar-k533-242944",
                        },
                        {
                            "strategy": "direct_url_html",
                            "source_url": control_url,
                            "trace": [],
                        },
                    )
                )

                collect_prices_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "242944",
                            "name": "ДСП лам. Kronospan K533 AD Каштан Арвадонна Мінк E-LE вологост. P3 2800x2070x18 мм",
                            "source_url": control_url,
                            "price": 5800.98,
                            "currency": "UAH",
                            "unit": "лист",
                            "stock": "В наявності",
                            "dimensions": "2800x2070x18 мм",
                            "thickness": "18 мм",
                            "external_product_id": "viyar-k533-242944",
                        },
                        {
                            "kyiv": 5800.98,
                        },
                    )
                )

                recommended_edges_mock = AsyncMock(
                    return_value={
                        "summary": {
                            "discovered": 1,
                            "persisted": 1,
                            "needs_review": 0,
                            "failed": 0,
                        }
                    }
                )

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_material_mock),
                    patch.object(catalog, "_collect_material_prices_for_all_cities", new=collect_prices_mock),
                    patch.object(catalog, "persist_viyar_recommended_edges_for_material_import", new=recommended_edges_mock),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                    patch.object(
                        catalog,
                        "prefetch_material_image_cache",
                        return_value={
                            "bytes": b"fake-image",
                            "content_type": "image/png",
                            "resolved_url": "https://www.viyar.ua/store/Items/photos/ph242944_main.jpg",
                        },
                    ),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "999999",
                            "name": "999999",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": control_url,
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["item"]["article"], "242944")
                self.assertEqual(
                    payload["item"]["name"],
                    "ДСП лам. Kronospan K533 AD Каштан Арвадонна Мінк E-LE вологост. P3 2800x2070x18 мм",
                )
                self.assertEqual(payload["recommended_edges"], {"discovered": 1, "persisted": 1, "needs_review": 0, "failed": 0})
                fetch_material_mock.assert_awaited_once()
                self.assertEqual(fetch_material_mock.await_args.kwargs["article_hint"], "999999")
                self.assertEqual(collect_prices_mock.await_count, 1)
                self.assertEqual(collect_prices_mock.await_args.kwargs["article"], "242944")
                recommended_edges_mock.assert_awaited_once()

                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "242944").one()

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material.name, "ДСП лам. Kronospan K533 AD Каштан Арвадонна Мінк E-LE вологост. P3 2800x2070x18 мм")
                self.assertEqual(material.source, "viyar")
                self.assertEqual(material.source_url, control_url)
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["article"], "242944")
                self.assertEqual(offers[0]["source_url"], control_url)
                self.assertEqual(offers[0]["city"], "kyiv")

    def test_material_import_refreshes_existing_default_material_from_supported_source_url(self) -> None:
        source_url = (
            "https://viyar.ua/ua/catalog/"
            "dsp-lam-kronospan-k520-pd-smaragd-temniy-2800kh2070kh18mm/"
            "?ms_q=K520%20PD"
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
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
                        MaterialModel(
                            article="189874",
                            name="ДСП лам. Kronospan K520 PD Смарагд Темний 2800х2070х18мм",
                            dimensions="2800x2070",
                            thickness="18 мм",
                            category="dsp",
                            source="viyar",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    session.flush()
                    session.add(
                        MaterialSupplierOfferModel(
                            material_id=session.query(MaterialModel.id).filter(MaterialModel.article == "189874").one()[0],
                            supplier_id=session.query(SupplierModel.id).filter(SupplierModel.code == "viyar").one()[0],
                            article="189874",
                            source_url=None,
                            price=18.0,
                            currency="UAH",
                            unit="м.п.",
                            city="kyiv",
                            is_active=True,
                            priority=0,
                        )
                    )
                    session.commit()
                    material_before = self._material_snapshot(session, "189874")

                fetch_material_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "189874",
                            "name": "ДСП лам. Kronospan K520 PD Смарагд Темний 2800х2070х18мм",
                            "source_url": source_url,
                            "price": 19.26,
                            "currency": "UAH",
                            "unit": "м.п.",
                            "stock": "СКОРО У ПРОДАЖУ",
                            "region": "kyiv",
                            "image": "https://www.viyar.ua/store/Items/photos/ph189874.jpg",
                            "image_urls": [
                                "https://www.viyar.ua/store/Items/photos/ph189874.jpg",
                            ],
                            "external_product_id": "185187",
                        },
                        {
                            "strategy": "direct_url_html",
                            "source_url": source_url,
                            "trace": [],
                        },
                    )
                )
                collect_prices_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "189874",
                            "name": "ДСП лам. Kronospan K520 PD Смарагд Темний 2800х2070х18мм",
                            "source_url": source_url,
                            "price": 19.26,
                            "currency": "UAH",
                            "unit": "м.п.",
                            "stock": "СКОРО У ПРОДАЖУ",
                            "region": "kyiv",
                            "image": "https://www.viyar.ua/store/Items/photos/ph189874.jpg",
                            "image_urls": [
                                "https://www.viyar.ua/store/Items/photos/ph189874.jpg",
                            ],
                            "external_product_id": "185187",
                        },
                        {
                            "kyiv": 19.26,
                        },
                    )
                )
                recommended_edges_mock = AsyncMock(
                    return_value={
                        "success": True,
                        "summary": {
                            "discovered": 2,
                            "persisted": 2,
                            "needs_review": 0,
                            "failed": 0,
                        },
                    }
                )
                gallery_image = PreparedFittingGalleryImage(
                    sort_order=0,
                    is_primary=True,
                    source_url="https://www.viyar.ua/store/Items/photos/ph189874.jpg",
                    image_bytes=b"fake-gallery-image",
                    content_type="image/jpeg",
                    sha256=sha256(b"fake-gallery-image").hexdigest(),
                )

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_material_mock),
                    patch.object(catalog, "_collect_material_prices_for_all_cities", new=collect_prices_mock),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                    patch.object(catalog, "_prepare_remote_material_gallery_images", return_value=(gallery_image,)),
                    patch.object(catalog, "prefetch_material_image_cache", return_value={
                        "bytes": b"fake-primary-image",
                        "content_type": "image/jpeg",
                        "resolved_url": "https://www.viyar.ua/store/Items/photos/ph189874.jpg",
                    }),
                    patch.object(catalog, "persist_viyar_recommended_edges_for_material_import", new=recommended_edges_mock),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "189874",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": source_url,
                        },
                        headers=self._auth_headers("trial-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertEqual(payload["item"]["article"], "189874")
                self.assertEqual(payload["recommended_edges"], {"discovered": 2, "persisted": 2, "needs_review": 0, "failed": 0})
                fetch_material_mock.assert_awaited_once()
                collect_prices_mock.assert_awaited_once()
                recommended_edges_mock.assert_awaited_once()

                with session_factory() as session:
                    material_after = self._material_snapshot(session, "189874")
                    material = session.query(MaterialModel).filter(MaterialModel.article == "189874").one()
                    supplier_id = session.query(SupplierModel.id).filter(SupplierModel.code == "viyar").one()[0]
                    image_count = (
                        session.query(MaterialImageModel)
                        .filter(MaterialImageModel.material_id == material.id)
                        .count()
                    )

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material_before["article"], material_after["article"])
                self.assertEqual(material_before["owner_user_id"], material_after["owner_user_id"])
                self.assertEqual(material_after["source_url"], source_url)
                self.assertEqual(material_after["image"], "https://www.viyar.ua/store/Items/photos/ph189874.jpg")
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["supplier_id"], supplier_id)
                self.assertEqual(offers[0]["article"], "189874")
                self.assertEqual(offers[0]["source_url"], source_url)
                self.assertEqual(offers[0]["price"], 19.26)
                self.assertEqual(offers[0]["currency"], "UAH")
                self.assertEqual(offers[0]["unit"], "м.п.")
                self.assertEqual(offers[0]["city"], "kyiv")
                self.assertEqual(image_count, 1)

    def test_material_import_source_url_without_article_returns_readable_error_when_parser_cannot_resolve(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                fetch_material_mock = AsyncMock(
                    return_value=(
                        {
                            "article": "",
                            "name": "VIYAR URL Imported Material",
                            "source_url": "https://viyar.ua/catalog/materials/url-only-1",
                        },
                        {
                            "strategy": "direct_url_html",
                            "source_url": "https://viyar.ua/catalog/materials/url-only-1",
                            "trace": [],
                        },
                    )
                )
                collect_prices_mock = AsyncMock()

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_material_mock),
                    patch.object(catalog, "_collect_material_prices_for_all_cities", new=collect_prices_mock),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                    patch.object(catalog, "prefetch_material_image_cache"),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": "https://viyar.ua/catalog/materials/url-only-1",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertFalse(payload["success"])
                self.assertEqual(
                    payload["error"],
                    "Не вдалося визначити артикул товару за посиланням. Вкажіть артикул вручну.",
                )
                fetch_material_mock.assert_awaited_once()
                collect_prices_mock.assert_not_awaited()

                with session_factory() as session:
                    self.assertEqual(session.query(MaterialModel).count(), 0)

    def test_material_import_viyar_source_url_transient_failure_does_not_create_stub_or_jobs(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                fetch_material_mock = AsyncMock(side_effect=URLError("net::ERR_NETWORK_ACCESS_DENIED"))
                collect_prices_mock = AsyncMock()

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_material_mock),
                    patch.object(catalog, "_collect_material_prices_for_all_cities", new=collect_prices_mock),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                    patch.object(catalog, "prefetch_material_image_cache"),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "242944",
                            "name": "242944",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": "https://viyar.ua/ua/catalog/dsp-lam-kronospan-k533-ad-kashtan-arvadonna-mink-e-le-vologost-p3-2800kh2070kh18-mm/?ms_q=533",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertFalse(payload["success"])
                self.assertEqual(
                    payload["error"],
                    "Не вдалося отримати дані товару від VIYAR. Спробуйте повторити імпорт пізніше.",
                )
                fetch_material_mock.assert_awaited_once()
                collect_prices_mock.assert_not_awaited()

                with session_factory() as session:
                    self.assertEqual(session.query(MaterialModel).count(), 0)
                    self.assertEqual(session.query(material_price.MaterialPriceModel).count(), 0)
                    self.assertEqual(session.query(MaterialSupplierOfferModel).count(), 0)
                    self.assertEqual(session.query(material_import_job.MaterialImportJobModel).count(), 0)

    def test_material_import_viyar_source_url_missing_parsed_material_returns_retryable_failure(self) -> None:
        control_url = (
            "https://viyar.ua/ua/catalog/"
            "dsp-lam-kronospan-k533-ad-kashtan-arvadonna-mink-e-le-vologost-p3-2800kh2070kh18-mm/"
            "?ms_q=533"
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
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
                    session.commit()

                fetch_material_mock = AsyncMock(
                    return_value=(
                        None,
                        {
                            "strategy": "direct_url_html",
                            "source_url": control_url,
                            "trace": [],
                        },
                    )
                )
                collect_prices_mock = AsyncMock(
                    return_value=(
                        {"article": "242944"},
                        {"kyiv": None},
                    )
                )
                recommended_edges_mock = AsyncMock()

                with (
                    patch.object(catalog, "fetch_material_by_source_url_live_traced", new=fetch_material_mock),
                    patch.object(catalog, "_collect_material_prices_for_all_cities", new=collect_prices_mock),
                    patch.object(catalog, "persist_viyar_recommended_edges_for_material_import", new=recommended_edges_mock),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                    patch.object(catalog, "prefetch_material_image_cache"),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "242944",
                            "name": "242944",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": control_url,
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertFalse(payload["success"])
                self.assertEqual(
                    payload["error"],
                    "Не вдалося отримати дані товару від VIYAR. Спробуйте повторити імпорт пізніше.",
                )
                fetch_material_mock.assert_awaited_once()
                collect_prices_mock.assert_not_awaited()
                recommended_edges_mock.assert_not_awaited()

                with session_factory() as session:
                    self.assertEqual(session.query(MaterialModel).count(), 0)
                    self.assertEqual(session.query(material_price.MaterialPriceModel).count(), 0)
                    self.assertEqual(session.query(MaterialSupplierOfferModel).count(), 0)
                    self.assertEqual(session.query(material_import_job.MaterialImportJobModel).count(), 0)
                    self.assertEqual(session.query(material_edge.MaterialEdgeModel).count(), 0)
                    self.assertEqual(session.query(material_edge_price.MaterialEdgePriceModel).count(), 0)

    def test_material_import_viyar_compatible_second_supplier_preserves_origin(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    viyar_supplier = SupplierModel(
                        code="viyar",
                        name="VIYAR",
                        logo_url="https://example.test/viyar-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    kronas_supplier = SupplierModel(
                        code="kronas",
                        name="KRONAS",
                        logo_url="https://example.test/kronas-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    session.add_all([viyar_supplier, kronas_supplier])
                    session.add(
                        MaterialModel(
                            article="MAT-SECOND-SUPPLIER",
                            name="VIYAR Canonical 5994 PD",
                            category="dsp",
                            dimensions="2800x2070",
                            thickness="18 мм",
                            image="https://example.test/viyar-image.png",
                            source_url="https://viyar.ua/catalog/materials/origin",
                            source="viyar",
                            product_type="dsp",
                            owner_user_id=None,
                            is_default=True,
                            image_source_url="https://example.test/viyar-image.png",
                            image_cached_bytes=b"cached-image",
                            image_cached_content_type="image/png",
                            image_cached_hash=sha256(b"cached-image").hexdigest(),
                            imported_at=datetime.utcnow(),
                            static_updated_at=datetime.utcnow(),
                        )
                    )
                    session.add(
                        material_price.MaterialPriceModel(
                            article="MAT-SECOND-SUPPLIER",
                            city="kyiv",
                            price=111.0,
                            currency="UAH",
                            availability="in stock",
                        )
                    )
                    session.commit()

                    viyar_supplier_id = session.query(SupplierModel.id).filter(SupplierModel.code == "viyar").one()[0]
                    kronas_supplier_id = int(kronas_supplier.id)

                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-SECOND-SUPPLIER").one()
                    inventory_repository.create_material_supplier_offer(
                        material_id=material.id,
                        supplier_id=viyar_supplier_id,
                        article="MAT-SECOND-SUPPLIER",
                        source_url="https://viyar.ua/catalog/materials/origin",
                        price=111.0,
                        currency="UAH",
                        unit="лист",
                        city="kyiv",
                        is_active=True,
                        priority=1,
                    )
                    material_before = self._material_snapshot(session, "MAT-SECOND-SUPPLIER")

                async def _fake_collect_material_prices_for_all_cities(**_kwargs):
                    return (
                        {
                            "article": "MAT-SECOND-SUPPLIER",
                            "name": "KRONAS 5994 PD",
                            "source_url": "https://kronas.ua/catalog/materials/compatible",
                            "price": 133.0,
                            "currency": "uah",
                            "unit": "лист",
                            "stock": "7",
                            "external_product_id": "kronas-compatible-1",
                        },
                        {
                            "kyiv": 133.0,
                        },
                    )

                with (
                    patch.object(catalog, "_collect_material_prices_for_all_cities", side_effect=_fake_collect_material_prices_for_all_cities),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "MAT-SECOND-SUPPLIER",
                            "name": "KRONAS 5994 PD",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": "https://kronas.ua/catalog/materials/compatible",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])
                self.assertIsNotNone(payload["job"])
                self.assertEqual(payload["job"]["status"], "queued")
                self.assertIn("queued", payload["error"].lower())

                with session_factory() as session:
                    material_after = self._material_snapshot(session, "MAT-SECOND-SUPPLIER")
                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-SECOND-SUPPLIER").one()

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material_after, material_before)
                self.assertEqual([offer["supplier_id"] for offer in offers], [viyar_supplier_id])
                self.assertEqual(offers[0]["source_url"], "https://viyar.ua/catalog/materials/origin")
                self.assertEqual(material_after["source"], "viyar")
                self.assertEqual(material_after["source_url"], "https://viyar.ua/catalog/materials/origin")
                self.assertEqual(material_after["name"], "VIYAR Canonical 5994 PD")

    def test_material_import_viyar_legacy_material_without_offer_creates_first_offer(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
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
                        MaterialModel(
                            article="MAT-LEGACY-OFFER",
                            name="VIYAR Legacy 5994 PD",
                            category="dsp",
                            dimensions="2800x2070",
                            thickness="18 мм",
                            image="https://example.test/legacy-image.png",
                            source_url="https://viyar.ua/catalog/materials/legacy",
                            source="viyar",
                            product_type="dsp",
                            owner_user_id=None,
                            is_default=True,
                            image_source_url="https://example.test/legacy-image.png",
                            image_cached_bytes=b"cached-image",
                            image_cached_content_type="image/png",
                            image_cached_hash=sha256(b"cached-image").hexdigest(),
                            imported_at=datetime.utcnow(),
                            static_updated_at=datetime.utcnow(),
                        )
                    )
                    session.add(
                        material_price.MaterialPriceModel(
                            article="MAT-LEGACY-OFFER",
                            city="kyiv",
                            price=111.0,
                            currency="UAH",
                            availability="in stock",
                        )
                    )
                    session.commit()

                    viyar_supplier_id = session.query(SupplierModel.id).filter(SupplierModel.code == "viyar").one()[0]

                    material_before = self._material_snapshot(session, "MAT-LEGACY-OFFER")

                async def _fake_collect_material_prices_for_all_cities(**_kwargs):
                    return (
                        {
                            "article": "MAT-LEGACY-OFFER",
                            "name": "VIYAR Legacy 5994 PD",
                            "image": "https://example.test/legacy-image.png",
                            "source_url": "https://viyar.ua/catalog/materials/legacy",
                            "dimensions": "2800x2070",
                            "thickness": "18 мм",
                            "price": 111.0,
                            "currency": "uah",
                            "unit": "лист",
                            "stock": "4",
                            "external_product_id": "viyar-legacy-1",
                        },
                        {
                            "kyiv": 111.0,
                        },
                    )

                with (
                    patch.object(catalog, "_collect_material_prices_for_all_cities", side_effect=_fake_collect_material_prices_for_all_cities),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                    patch.object(
                        catalog,
                        "prefetch_material_image_cache",
                        return_value={
                            "bytes": b"legacy-image",
                            "content_type": "image/png",
                            "resolved_url": "https://example.test/legacy-image.png",
                        },
                    ),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "MAT-LEGACY-OFFER",
                            "name": "VIYAR Legacy 5994 PD",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": "https://viyar.ua/catalog/materials/legacy",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["success"])

                with session_factory() as session:
                    material_after = self._material_snapshot(session, "MAT-LEGACY-OFFER")
                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-LEGACY-OFFER").one()

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material_after, material_before)
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["supplier_id"], viyar_supplier_id)
                self.assertEqual(offers[0]["source_url"], "https://viyar.ua/catalog/materials/legacy")

    def test_material_import_job_creates_supplier_offer_for_kronas_source(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, _client):
                with session_factory() as session:
                    session.add(
                        SupplierModel(
                            code="kronas",
                            name="KRONAS",
                            logo_url="https://example.test/kronas-logo.png",
                            owner_user_id=None,
                            is_system=True,
                            is_active=True,
                        )
                    )
                    session.commit()

                job = material_import_job_repository.create_material_import_job(
                    article="KRONAS-IMPORTED-1",
                    category="dsp",
                    city="kyiv",
                    owner_user_id="admin-user",
                    preferred_url="https://kronas.ua/catalog/materials/1",
                )

                async def _fake_fetch_material_by_source_live_traced(*_args, **_kwargs):
                    return (
                        {
                            "article": "KRONAS-IMPORTED-1",
                            "name": "KRONAS Imported Material",
                            "source_url": "https://kronas.ua/catalog/materials/1",
                            "price": 88.0,
                            "currency": "UAH",
                            "unit": "лист",
                            "stock": "5",
                            "region": "Lvivska oblast",
                            "external_product_id": "kronas-imported-1",
                        },
                        {
                            "strategy": "test",
                            "source_url": "https://kronas.ua/catalog/materials/1",
                            "trace": [],
                        },
                    )

                with (
                    patch.object(
                        material_import_queue_service,
                        "fetch_material_by_source_live_traced",
                        side_effect=_fake_fetch_material_by_source_live_traced,
                    ),
                    patch.object(
                        material_import_queue_service,
                        "prefetch_material_image_cache",
                        return_value={
                            "bytes": b"fake-image",
                            "content_type": "image/png",
                            "resolved_url": "https://example.test/material.png",
                        },
                    ),
                ):
                    result = asyncio.run(
                        material_import_queue_service.process_material_import_job(int(job["id"]))
                    )

                self.assertIsNotNone(result)
                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "KRONAS-IMPORTED-1").one()
                    supplier_id = session.query(SupplierModel.id).filter(SupplierModel.code == "kronas").one()[0]

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["supplier_id"], supplier_id)
                self.assertEqual(offers[0]["article"], "KRONAS-IMPORTED-1")
                self.assertEqual(offers[0]["source_url"], "https://kronas.ua/catalog/materials/1")
                self.assertEqual(offers[0]["price"], 88.0)
                self.assertEqual(offers[0]["currency"], "UAH")
                self.assertEqual(offers[0]["unit"], "лист")
                self.assertEqual(offers[0]["city"], "kyiv")

    def test_material_import_job_compatible_second_supplier_preserves_origin(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, _client):
                with session_factory() as session:
                    viyar_supplier = SupplierModel(
                        code="viyar",
                        name="VIYAR",
                        logo_url="https://example.test/viyar-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    kronas_supplier = SupplierModel(
                        code="kronas",
                        name="KRONAS",
                        logo_url="https://example.test/kronas-logo.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    session.add_all([viyar_supplier, kronas_supplier])
                    session.add(
                        MaterialModel(
                            article="JOB-SECOND-SUPPLIER",
                            name="VIYAR Canonical 5994 PD",
                            category="dsp",
                            dimensions="2800x2070",
                            thickness="18 мм",
                            source_url="https://viyar.ua/catalog/materials/origin",
                            source="viyar",
                            product_type="dsp",
                            owner_user_id=None,
                            is_default=True,
                            image_cached_bytes=b"cached-image",
                            image_cached_content_type="image/png",
                            image_cached_hash=sha256(b"cached-image").hexdigest(),
                            imported_at=datetime.utcnow(),
                            static_updated_at=datetime.utcnow(),
                        )
                    )
                    session.add(
                        material_price.MaterialPriceModel(
                            article="JOB-SECOND-SUPPLIER",
                            city="kyiv",
                            price=111.0,
                            currency="UAH",
                            availability="in stock",
                        )
                    )
                    session.commit()

                    viyar_supplier_id = int(viyar_supplier.id)
                    kronas_supplier_id = int(kronas_supplier.id)

                    material = session.query(MaterialModel).filter(MaterialModel.article == "JOB-SECOND-SUPPLIER").one()
                    inventory_repository.create_material_supplier_offer(
                        material_id=material.id,
                        supplier_id=viyar_supplier_id,
                        article="JOB-SECOND-SUPPLIER",
                        source_url="https://viyar.ua/catalog/materials/origin",
                        price=111.0,
                        currency="UAH",
                        unit="лист",
                        city="kyiv",
                        is_active=True,
                        priority=1,
                    )

                job = material_import_job_repository.create_material_import_job(
                    article="JOB-SECOND-SUPPLIER",
                    category="dsp",
                    city="kyiv",
                    owner_user_id="admin-user",
                    preferred_url="https://kronas.ua/catalog/materials/compatible",
                )

                async def _fake_fetch_material_by_source_live_traced(*_args, **_kwargs):
                    return (
                        {
                            "article": "JOB-SECOND-SUPPLIER",
                            "name": "KRONAS 5994 PD",
                            "source_url": "https://kronas.ua/catalog/materials/compatible",
                            "dimensions": "2800x2070",
                            "thickness": "18 мм",
                            "price": 133.0,
                            "currency": "UAH",
                            "unit": "лист",
                            "stock": "7",
                            "external_product_id": "kronas-compatible-1",
                        },
                        {
                            "strategy": "test",
                            "source_url": "https://kronas.ua/catalog/materials/compatible",
                            "trace": [],
                        },
                    )

                with patch.object(
                    material_import_queue_service,
                    "fetch_material_by_source_live_traced",
                    side_effect=_fake_fetch_material_by_source_live_traced,
                ):
                    result = asyncio.run(
                        material_import_queue_service.process_material_import_job(int(job["id"]))
                    )

                self.assertIsNotNone(result)
                with session_factory() as session:
                    material_after = self._material_snapshot(session, "JOB-SECOND-SUPPLIER")
                    material = session.query(MaterialModel).filter(MaterialModel.article == "JOB-SECOND-SUPPLIER").one()

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material_after["source"], "viyar")
                self.assertEqual(material_after["source_url"], "https://viyar.ua/catalog/materials/origin")
                self.assertEqual(material_after["name"], "VIYAR Canonical 5994 PD")
                self.assertEqual({offer["supplier_id"] for offer in offers}, {viyar_supplier_id, kronas_supplier_id})
                offers_by_supplier = {offer["supplier_id"]: offer for offer in offers}
                self.assertEqual(offers_by_supplier[viyar_supplier_id]["source_url"], "https://viyar.ua/catalog/materials/origin")
                self.assertEqual(offers_by_supplier[kronas_supplier_id]["source_url"], "https://kronas.ua/catalog/materials/compatible")

    def test_material_import_viyar_conflict_does_not_create_supplier_offer(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
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
                        MaterialModel(
                            article="MAT-GUARD-VIYAR",
                            name="Kronospan 5994 PD Синій Альбі 2800x2070x18",
                            category="dsp",
                            dimensions="2800x2070",
                            thickness="18 мм",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    session.add(
                        material_price.MaterialPriceModel(
                            article="MAT-GUARD-VIYAR",
                            city="kyiv",
                            price=111.0,
                            currency="UAH",
                            availability="in stock",
                        )
                    )
                    session.commit()

                    material_before = self._material_snapshot(session, "MAT-GUARD-VIYAR")
                    prices_before = self._material_prices_snapshot(session, "MAT-GUARD-VIYAR")

                async def _fake_collect_material_prices_for_all_cities(**_kwargs):
                    return (
                        {
                            "article": "MAT-GUARD-VIYAR",
                            "name": "ЛДСП KRONOSPAN 5994 SU СИНИЙ АЛЬБІ 2800X2070X18",
                            "source_url": "https://viyar.ua/catalog/materials/guard",
                            "price": 140.0,
                            "currency": "uah",
                            "unit": "лист",
                            "stock": "8",
                        },
                        {
                            "kyiv": 140.0,
                        },
                    )

                with (
                    patch.object(catalog, "_collect_material_prices_for_all_cities", side_effect=_fake_collect_material_prices_for_all_cities),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "MAT-GUARD-VIYAR",
                            "name": "MAT-GUARD-VIYAR",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": "https://viyar.ua/catalog/materials/guard",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertFalse(payload["success"])
                self.assertIn("conflicts with the existing canonical material", payload["error"])
                self.assertEqual(payload["material_identity_validation"]["status"], "conflict")
                self.assertTrue(payload["material_identity_validation"]["conflicts"])
                self.assertEqual(
                    payload["material_identity_validation"]["conflicts"][0]["field"],
                    "structure",
                )

                with session_factory() as session:
                    material_after = self._material_snapshot(session, "MAT-GUARD-VIYAR")
                    prices_after = self._material_prices_snapshot(session, "MAT-GUARD-VIYAR")
                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-GUARD-VIYAR").one()

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material_after, material_before)
                self.assertEqual(prices_after, prices_before)
                self.assertEqual(offers, [])

    def test_material_import_viyar_needs_review_does_not_mutate_canonical(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
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
                        MaterialModel(
                            article="MAT-GUARD-REVIEW",
                            name="Kronospan 5994",
                            category="dsp",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    session.add(
                        material_price.MaterialPriceModel(
                            article="MAT-GUARD-REVIEW",
                            city="kyiv",
                            price=111.0,
                            currency="UAH",
                            availability="in stock",
                        )
                    )
                    session.commit()

                    material_before = self._material_snapshot(session, "MAT-GUARD-REVIEW")
                    prices_before = self._material_prices_snapshot(session, "MAT-GUARD-REVIEW")

                async def _fake_collect_material_prices_for_all_cities(**_kwargs):
                    return (
                        {
                            "article": "MAT-GUARD-REVIEW",
                            "name": "Kronospan 5994",
                            "source_url": "https://viyar.ua/catalog/materials/review",
                            "price": 140.0,
                            "currency": "uah",
                            "unit": "лист",
                            "stock": "8",
                        },
                        {
                            "kyiv": 140.0,
                        },
                    )

                with (
                    patch.object(catalog, "_collect_material_prices_for_all_cities", side_effect=_fake_collect_material_prices_for_all_cities),
                    patch.object(catalog, "_resolve_viyar_cookie_for_user", return_value=None),
                ):
                    response = client.post(
                        "/catalog/materials",
                        json={
                            "article": "MAT-GUARD-REVIEW",
                            "name": "Kronospan 5994",
                            "category": "dsp",
                            "city": "kyiv",
                            "source_url": "https://viyar.ua/catalog/materials/review",
                        },
                        headers=self._auth_headers("admin-token"),
                    )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertFalse(payload["success"])
                self.assertEqual(payload["material_identity_validation"]["status"], "needs_review")

                with session_factory() as session:
                    material_after = self._material_snapshot(session, "MAT-GUARD-REVIEW")
                    prices_after = self._material_prices_snapshot(session, "MAT-GUARD-REVIEW")
                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-GUARD-REVIEW").one()

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(material_after, material_before)
                self.assertEqual(prices_after, prices_before)
                self.assertEqual(offers, [])

    def test_material_import_job_with_existing_material_attaches_only_when_identity_matches(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, _client):
                with session_factory() as session:
                    session.add(
                        SupplierModel(
                            code="kronas",
                            name="KRONAS",
                            logo_url="https://example.test/kronas-logo.png",
                            owner_user_id=None,
                            is_system=True,
                            is_active=True,
                        )
                    )
                    session.add(
                        MaterialModel(
                            article="MAT-GUARD-KRONAS",
                            name="Kronospan 5994 PD Синій Альбі 2800x2070x18",
                            category="dsp",
                            dimensions="2800x2070",
                            thickness="18 мм",
                            owner_user_id=None,
                            is_default=True,
                        )
                    )
                    session.commit()

                job = material_import_job_repository.create_material_import_job(
                    article="MAT-GUARD-KRONAS",
                    category="dsp",
                    city="kyiv",
                    owner_user_id="admin-user",
                    preferred_url="https://kronas.ua/catalog/materials/guard",
                )

                async def _fake_fetch_material_by_source_live_traced(*_args, **_kwargs):
                    return (
                        {
                            "article": "MAT-GUARD-KRONAS",
                            "name": "KRONAS 5994 PD Синій Альбі 2800x2070x18",
                            "source_url": "https://kronas.ua/catalog/materials/guard",
                            "price": 132.0,
                            "currency": "UAH",
                            "unit": "лист",
                            "stock": "6",
                            "dimensions": "2800x2070",
                            "thickness": "18 мм",
                        },
                        {
                            "strategy": "test",
                            "source_url": "https://kronas.ua/catalog/materials/guard",
                            "trace": [],
                        },
                    )

                with patch.object(
                    material_import_queue_service,
                    "fetch_material_by_source_live_traced",
                    side_effect=_fake_fetch_material_by_source_live_traced,
                ):
                    result = asyncio.run(
                        material_import_queue_service.process_material_import_job(int(job["id"]))
                    )

                self.assertIsNotNone(result)
                with session_factory() as session:
                    material = session.query(MaterialModel).filter(MaterialModel.article == "MAT-GUARD-KRONAS").one()
                    supplier_id = session.query(SupplierModel.id).filter(SupplierModel.code == "kronas").one()[0]

                offers = inventory_repository.list_material_supplier_offers(material.id)
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0]["supplier_id"], supplier_id)
                self.assertEqual(offers[0]["price"], 132.0)
                self.assertEqual(offers[0]["article"], "MAT-GUARD-KRONAS")
                self.assertEqual(offers[0]["source_url"], "https://kronas.ua/catalog/materials/guard")

    def test_supplier_delete_is_blocked_by_material_and_fitting_offers(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (session_factory, client):
                with session_factory() as session:
                    material_supplier = SupplierModel(
                        code="mat-supplier",
                        name="Material Supplier",
                        logo_url="https://example.test/material-supplier.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    fitting_supplier = SupplierModel(
                        code="fit-supplier",
                        name="Fitting Supplier",
                        logo_url="https://example.test/fitting-supplier.png",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    fitting = FittingModel(
                        name="Fitting with offer",
                        article="FIT-OFFER-1",
                        fitting_type="drawer_slides",
                        fitting_group="fittings",
                        owner_user_id=None,
                        is_system=True,
                        is_active=True,
                    )
                    session.add_all(
                        [
                            material_supplier,
                            fitting_supplier,
                            MaterialModel(
                                article="SUPPLIER-BLOCK-MAT",
                                name="Supplier Block Material",
                                category="dsp",
                                owner_user_id=None,
                                is_default=True,
                            ),
                            fitting,
                        ],
                    )
                    session.commit()
                    material_supplier_id = session.query(SupplierModel.id).filter(SupplierModel.code == "mat-supplier").one()[0]
                    fitting_supplier_id = session.query(SupplierModel.id).filter(SupplierModel.code == "fit-supplier").one()[0]

                    material = session.query(MaterialModel).filter(MaterialModel.article == "SUPPLIER-BLOCK-MAT").one()
                    fitting_row = session.query(FittingModel).filter(FittingModel.article == "FIT-OFFER-1").one()

                    session.add(
                        MaterialSupplierOfferModel(
                            material_id=material.id,
                            supplier_id=material_supplier.id,
                            article="MAT-SUP-1",
                            source_url="https://example.test/material-offer",
                            price=10.0,
                            currency="UAH",
                            unit="шт",
                            is_active=True,
                            priority=10,
                        )
                    )
                    session.add(
                        FittingSupplierOfferModel(
                            fitting_id=fitting_row.id,
                            supplier_id=fitting_supplier.id,
                            article="FIT-SUP-1",
                            source_url="https://example.test/fitting-offer",
                            price=11.0,
                            currency="UAH",
                            unit="шт",
                            stock="in stock",
                            is_active=True,
                            priority=10,
                        )
                    )
                    session.commit()

                deactivate_material_supplier = client.patch(
                    f"/catalog/suppliers/{material_supplier_id}",
                    json={
                        "code": "mat-supplier",
                        "name": "Material Supplier",
                        "logo_url": "https://example.test/material-supplier.png",
                        "is_active": False,
                        "is_system": True,
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(deactivate_material_supplier.status_code, 200)
                self.assertTrue(deactivate_material_supplier.json()["success"])

                material_delete = client.delete(
                    f"/catalog/suppliers/{material_supplier_id}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(material_delete.status_code, 200)
                self.assertFalse(material_delete.json()["success"])
                self.assertIn("used by fitting offers", material_delete.json()["error"])

                deactivate_fitting_supplier = client.patch(
                    f"/catalog/suppliers/{fitting_supplier_id}",
                    json={
                        "code": "fit-supplier",
                        "name": "Fitting Supplier",
                        "logo_url": "https://example.test/fitting-supplier.png",
                        "is_active": False,
                        "is_system": True,
                    },
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(deactivate_fitting_supplier.status_code, 200)
                self.assertTrue(deactivate_fitting_supplier.json()["success"])

                fitting_delete = client.delete(
                    f"/catalog/suppliers/{fitting_supplier_id}",
                    headers=self._auth_headers("admin-token"),
                )
                self.assertEqual(fitting_delete.status_code, 200)
                self.assertFalse(fitting_delete.json()["success"])
                self.assertIn("used by fitting offers", fitting_delete.json()["error"])

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

                deleted = client.delete(
                    f"/catalog/suppliers/{created_supplier_id}",
                    headers=self._auth_headers("pro-token"),
                )
                self.assertEqual(deleted.status_code, 200)
                self.assertFalse(deleted.json()["success"])
                self.assertIn("деактив", deleted.json()["error"].lower())

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
                    supplier.is_active = False
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
