from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api.dependencies import auth as auth_dependencies
from api.routes import catalog
from database.base import Base
from database.models import audit_log  # noqa: F401
from database.models import catalog_item  # noqa: F401
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models import entitlement_feature  # noqa: F401
from database.models.fitting import FittingModel
from database.models import fitting_hole_service_rule  # noqa: F401
from database.models import fitting_image  # noqa: F401
from database.models.fitting_image import FittingImageModel
from database.models.material import MaterialModel
from database.models import material_edge  # noqa: F401
from database.models import material_edge_price  # noqa: F401
from database.models import material_import_job  # noqa: F401
from database.models import material_price  # noqa: F401
from database.models import material_user_link  # noqa: F401
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
import services.entitlement_service as entitlement_service


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

    def test_free_user_cannot_create_fitting(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            with self._catalog_context(Path(tmpdir) / "catalog.db") as (_session_factory, client):
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
            patch.object(catalog, "SessionLocal", side_effect=session_factory),
            patch.object(entitlement_service, "SessionLocal", side_effect=session_factory),
            patch.object(auth_dependencies, "get_user_from_token", side_effect=_resolve_user),
            patch.object(catalog, "get_user_from_token", side_effect=_resolve_user),
        ):
            with session_factory() as session:
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
                session.commit()
            with TestClient(app) as client:
                yield session_factory, client

    @staticmethod
    def _auth_headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
        }
