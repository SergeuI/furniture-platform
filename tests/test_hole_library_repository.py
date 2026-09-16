from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.base import Base
from database.models.audit_log import AuditLogModel
from database.models.hole_library import HoleLibraryTypeModel
from database.models.hole_library import HoleLibraryServiceMappingModel
from database.models.service_catalog_item import ServiceCatalogItemModel
from database.models.service_drilling_rule import ServiceDrillingRuleModel
from database.models.user import UserModel
from database.repositories import hole_library_repository as repository_module
from database.repositories.hole_library_repository import seed_default_hole_library


class HoleLibraryRepositoryTests(unittest.TestCase):
    def test_custom_hole_code_is_generated_and_unique(self) -> None:
        session_factory, engine = self._build_session_factory()
        try:
            from database.repositories.hole_library_repository import HoleLibraryRepository

            with session_factory() as session:
                repository = HoleLibraryRepository(session)
                first, created = repository.upsert_hole_type(
                    {
                        "name": "Глухий отвір Ø3 × 8",
                        "operation_type": "blind",
                        "surface_type": "plane",
                        "diameter_mm": 3,
                        "depth_mode": "fixed",
                        "fixed_depth_mm": 8,
                        "is_system": False,
                    }
                )
                second, second_created = repository.upsert_hole_type(
                    {
                        "name": "Глухий отвір Ø3 × 8 другий",
                        "operation_type": "blind",
                        "surface_type": "plane",
                        "diameter_mm": 3,
                        "depth_mode": "fixed",
                        "fixed_depth_mm": 8,
                        "is_system": False,
                    }
                )
                self.assertTrue(created)
                self.assertTrue(second_created)
                self.assertNotEqual(first.code, second.code)
                self.assertTrue(first.code.startswith("CUSTOM_BLIND_PLANE_D3"))
        finally:
            engine.dispose()

    def test_seed_is_idempotent_and_keeps_service_mappings(self) -> None:
        session_factory, engine = self._build_session_factory()
        try:
            self._seed_service_catalog(session_factory)
            with patch.object(repository_module, "SessionLocal", session_factory):
                seed_default_hole_library()
                seed_default_hole_library()

            with session_factory() as session:
                items = session.query(HoleLibraryTypeModel).order_by(HoleLibraryTypeModel.code.asc()).all()
                self.assertEqual(len(items), 28)
                self.assertEqual(len({item.code for item in items}), 28)

                by_code = {item.code: item for item in items}
                self.assertEqual(by_code["PLANE_BLIND_D5"].service_mappings[0].service_article, "00011")
                self.assertEqual(by_code["EDGE_DEEP_D10"].service_mappings[0].service_article, "98175")
                self.assertEqual(by_code["HINGE_CUP_D35"].service_mappings[0].service_article, "51203")
                self.assertEqual(by_code["PLANE_BLIND_D5"].service_mappings[0].mapping_status, "resolved")
                self.assertEqual(by_code["EDGE_DEEP_D10"].service_mappings[0].mapping_status, "service_only")
                self.assertEqual(by_code["HINGE_CUP_D35"].service_mappings[0].mapping_status, "service_only")
        finally:
            engine.dispose()

    def test_deactivated_type_does_not_reactivate_type_or_mapping_on_seed(self) -> None:
        session_factory, engine = self._build_session_factory()
        try:
            self._seed_service_catalog(session_factory)
            with patch.object(repository_module, "SessionLocal", session_factory):
                seed_default_hole_library()

            with session_factory() as session:
                hole_type = (
                    session.query(HoleLibraryTypeModel)
                    .filter(HoleLibraryTypeModel.code == "PLANE_BLIND_D5")
                    .one()
                )
                mapping = (
                    session.query(HoleLibraryServiceMappingModel)
                    .filter(HoleLibraryServiceMappingModel.hole_type_id == hole_type.id)
                    .one()
                )
                hole_type.is_active = False
                mapping.is_active = False
                session.add(
                    AuditLogModel(
                        actor_user_id="admin",
                        actor_email="admin@example.com",
                        action="admin.entity_deactivated",
                        entity_type="hole_library_type",
                        entity_id=hole_type.code,
                        details={"code": hole_type.code},
                    )
                )
                session.commit()

            with patch.object(repository_module, "SessionLocal", session_factory):
                seed_default_hole_library()

            with session_factory() as session:
                hole_type = (
                    session.query(HoleLibraryTypeModel)
                    .filter(HoleLibraryTypeModel.code == "PLANE_BLIND_D5")
                    .one()
                )
                mapping = (
                    session.query(HoleLibraryServiceMappingModel)
                    .filter(HoleLibraryServiceMappingModel.hole_type_id == hole_type.id)
                    .one()
                )
                self.assertFalse(hole_type.is_active)
                self.assertFalse(mapping.is_active)
        finally:
            engine.dispose()

    @staticmethod
    def _build_session_factory():
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
        return Session, engine

    @staticmethod
    def _seed_service_catalog(session_factory) -> None:
        with session_factory() as session:
            user = UserModel(id="user-1", email="user@example.com", role="admin", password_hash="hashed-password")
            session.add(user)
            session.add_all(
                [
                    ServiceCatalogItemModel(
                        id="svc-00011",
                        source="viyar",
                        external_code="viyar-service-drilling-main-00011",
                        name="Стандартне свердління",
                        slug="standard-drilling",
                        item_type="service",
                        folder_path="viyar-services/prisadka",
                        article="00011",
                        is_active=True,
                    ),
                    ServiceCatalogItemModel(
                        id="svc-98175",
                        source="viyar",
                        external_code="viyar-service-drilling-main-98175",
                        name="Глибоке торцеве свердління",
                        slug="deep-edge-drilling",
                        item_type="service",
                        folder_path="viyar-services/prisadka",
                        article="98175",
                        is_active=True,
                    ),
                    ServiceCatalogItemModel(
                        id="svc-51203",
                        source="viyar",
                        external_code="viyar-service-drilling-main-51203",
                        name="Чашка завіси D35",
                        slug="hinge-cup-d35",
                        item_type="service",
                        folder_path="viyar-services/prisadka",
                        article="51203",
                        is_active=True,
                    ),
                ]
            )
            session.add(
                ServiceDrillingRuleModel(
                    service_catalog_item_id="svc-00011",
                    rule_name="Standard drilling",
                    operation_type="drilling",
                    hole_type="blind",
                    allowed_diameters=[8],
                    allowed_depths=[10, 12, 15],
                    max_blind_depth_mm=13.0,
                    min_edge_offset_mm=7.0,
                    is_active=True,
                )
            )
            session.commit()
