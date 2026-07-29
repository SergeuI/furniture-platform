from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.fitting import (
    FittingHolePointModel,
    FittingHoleTemplateModel,
    FittingModel,
)
from database.models.mounting_node import (
    MountingNodeItemModel,
    MountingNodeModel,
    MountingNodeTemplateModel,
)
from database.models.service_catalog_item import ServiceCatalogItemModel
from database.models.service_drilling_rule import ServiceDrillingRuleModel
from database.models.user import UserModel
from services.mounting_node_service import MountingNodeService


class MountingNodeServiceTests(unittest.TestCase):
    def test_create_node_serializes_items_and_templates(self) -> None:
        session, engine = self._build_session()
        try:
            fitting = self._create_fitting(session, name="Confirmat 7x50", code="confirmat-7x50", article="190106")
            template = self._create_template(session, fitting.id, name="Main template")
            self._create_point(session, template.id, x_mm=0, y_mm=0, z_mm=0)

            service = MountingNodeService(session=session)
            node = service.create_mounting_node(
                {
                    "name": "Confirmat node",
                    "items": [
                        {
                            "fitting_id": fitting.id,
                            "quantity": 2,
                            "role": "primary",
                            "is_required": True,
                            "affects_processing": True,
                            "order_index": 1,
                        }
                    ],
                    "templates": [
                        {
                            "template_id": template.id,
                            "is_default": True,
                            "order_index": 3,
                        }
                    ],
                }
            )

            self.assertTrue(node["code"].startswith("mounting-node-confirmat-node-"))
            self.assertEqual(node["items_count"], 1)
            self.assertEqual(node["templates_count"], 1)
            self.assertEqual(node["items"][0]["fitting_id"], fitting.id)
            self.assertEqual(node["items"][0]["fitting_code"], "confirmat-7x50")
            self.assertEqual(node["items"][0]["quantity"], 2)
            self.assertEqual(node["templates"][0]["template_id"], template.id)
            self.assertEqual(node["templates"][0]["points_count"], 1)
            self.assertTrue(node["templates"][0]["is_default"])
        finally:
            session.close()
            engine.dispose()

    def test_create_node_rejects_missing_or_duplicate_items(self) -> None:
        session, engine = self._build_session()
        try:
            fitting = self._create_fitting(session, name="Confirmat 7x50", code="confirmat-7x50", article="190106")
            service = MountingNodeService(session=session)

            with self.assertRaisesRegex(ValueError, "items is required"):
                service.create_mounting_node({"name": "Empty node", "items": []})

            with self.assertRaisesRegex(ValueError, "Duplicate fitting_id"):
                service.create_mounting_node(
                    {
                        "name": "Duplicate node",
                        "items": [
                            {"fitting_id": fitting.id, "quantity": 1},
                            {"fitting_id": fitting.id, "quantity": 2},
                        ],
                    }
                )

            with self.assertRaisesRegex(ValueError, "quantity must be greater than 0"):
                service.create_mounting_node(
                    {
                        "name": "Bad quantity",
                        "items": [
                            {"fitting_id": fitting.id, "quantity": 0},
                        ],
                    }
                )
        finally:
            session.close()
            engine.dispose()

    def test_create_node_rejects_template_validation_conflicts(self) -> None:
        session, engine = self._build_session()
        try:
            fitting_a = self._create_fitting(session, name="Fit A", code="fit-a", article="A")
            fitting_b = self._create_fitting(session, name="Fit B", code="fit-b", article="B")
            fitting_c = self._create_fitting(session, name="Fit C", code="fit-c", article="C")
            fitting_d = self._create_fitting(session, name="Fit D", code="fit-d", article="D")
            template_a = self._create_template(session, fitting_a.id, name="Template A", mounting_variant_key="surface_mount")
            template_b = self._create_template(session, fitting_b.id, name="Template B", mounting_variant_key="surface_mount")
            template_c = self._create_template(session, fitting_c.id, name="Template C", mounting_variant_key="surface_mount")
            template_d = self._create_template(session, fitting_d.id, name="Template D", mounting_variant_key="surface_mount")

            service = MountingNodeService(session=session)

            with self.assertRaisesRegex(ValueError, "does not belong to the selected fittings"):
                service.create_mounting_node(
                    {
                        "name": "Wrong template",
                        "items": [{"fitting_id": fitting_a.id, "quantity": 1}],
                        "templates": [{"template_id": template_b.id, "is_default": True}],
                    }
                )

            node = service.create_mounting_node(
                {
                    "name": "Node A",
                    "items": [{"fitting_id": fitting_a.id, "quantity": 1}],
                    "templates": [{"template_id": template_a.id, "is_default": True}],
                }
            )
            self.assertEqual(node["templates_count"], 1)

            with self.assertRaisesRegex(ValueError, "already belongs to another mounting node"):
                service.create_mounting_node(
                    {
                        "name": "Node B",
                        "items": [{"fitting_id": fitting_a.id, "quantity": 1}],
                        "templates": [{"template_id": template_a.id, "is_default": True}],
                    }
                )

            with self.assertRaisesRegex(ValueError, "More than one default template"):
                service.create_mounting_node(
                    {
                        "name": "Node C",
                        "items": [
                            {"fitting_id": fitting_c.id, "quantity": 1},
                            {"fitting_id": fitting_d.id, "quantity": 1},
                        ],
                        "templates": [
                            {"template_id": template_c.id, "is_default": True},
                            {"template_id": template_d.id, "is_default": True},
                        ],
                    }
                )
        finally:
            session.close()
            engine.dispose()

    def test_update_node_keeps_items_when_omitted_and_rolls_back_on_error(self) -> None:
        session, engine = self._build_session()
        try:
            fitting_a = self._create_fitting(session, name="Fit A", code="fit-a", article="A")
            fitting_b = self._create_fitting(session, name="Fit B", code="fit-b", article="B")
            template_a = self._create_template(session, fitting_a.id, name="Template A", mounting_variant_key="surface_mount")
            template_b = self._create_template(session, fitting_b.id, name="Template B", mounting_variant_key="angled_two_planes")

            service = MountingNodeService(session=session)
            node = service.create_mounting_node(
                {
                    "name": "Node A",
                    "items": [{"fitting_id": fitting_a.id, "quantity": 1}],
                    "templates": [{"template_id": template_a.id, "is_default": True}],
                }
            )

            updated = service.update_mounting_node(
                node["id"],
                {
                    "description": "Updated description",
                },
            )
            self.assertEqual(updated["description"], "Updated description")
            self.assertEqual(updated["items_count"], 1)
            self.assertEqual(updated["templates_count"], 1)

            with self.assertRaisesRegex(ValueError, "does not belong to the selected fittings"):
                service.update_mounting_node(
                    node["id"],
                    {
                        "templates": [{"template_id": template_b.id, "is_default": True}],
                    },
                )

            reloaded = service.get_mounting_node(node["id"])
            self.assertEqual(reloaded["description"], "Updated description")
            self.assertEqual(reloaded["items_count"], 1)
            self.assertEqual(reloaded["templates_count"], 1)
            self.assertEqual(reloaded["items"][0]["fitting_id"], fitting_a.id)
        finally:
            session.close()
            engine.dispose()

    def test_list_filters_by_fitting_and_variant(self) -> None:
        session, engine = self._build_session()
        try:
            fitting_a = self._create_fitting(session, name="Fit A", code="fit-a", article="A")
            fitting_b = self._create_fitting(session, name="Fit B", code="fit-b", article="B")
            template_a = self._create_template(session, fitting_a.id, name="Template A", mounting_variant_key="surface_mount")
            template_b = self._create_template(session, fitting_b.id, name="Template B", mounting_variant_key="angled_two_planes")

            service = MountingNodeService(session=session)
            service.create_mounting_node(
                {
                    "name": "Node A",
                    "items": [{"fitting_id": fitting_a.id, "quantity": 1}],
                    "templates": [{"template_id": template_a.id, "is_default": True}],
                }
            )
            service.create_mounting_node(
                {
                    "name": "Node B",
                    "items": [{"fitting_id": fitting_b.id, "quantity": 1}],
                    "templates": [{"template_id": template_b.id, "is_default": True}],
                }
            )

            by_fitting = service.list_mounting_nodes(fitting_id=fitting_a.id)
            by_variant = service.list_mounting_nodes(mounting_variant_key="angled_two_planes")

            self.assertEqual(len(by_fitting), 1)
            self.assertEqual(by_fitting[0]["name"], "Node A")
            self.assertEqual(len(by_variant), 1)
            self.assertEqual(by_variant[0]["name"], "Node B")
        finally:
            session.close()
            engine.dispose()

    def _build_session(self):
        tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tempdir.cleanup)
        database_path = Path(tempdir.name) / "test.db"
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        session = Session()
        return session, engine

    @staticmethod
    def _create_fitting(session, name: str, code: str, article: str) -> FittingModel:
        fitting = FittingModel(
            name=name,
            code=code,
            article=article,
            is_system=True,
            is_active=True,
            sort_order=0,
        )
        session.add(fitting)
        session.commit()
        session.refresh(fitting)
        return fitting

    @staticmethod
    def _create_template(
        session,
        fitting_id: int,
        name: str,
        mounting_variant_key: str = "surface_mount",
    ) -> FittingHoleTemplateModel:
        template = FittingHoleTemplateModel(
            fitting_id=fitting_id,
            name=name,
            template_type="manual",
            side="left",
            coordinate_system="2d",
            mounting_variant_key=mounting_variant_key,
            is_default=True,
            is_active=True,
        )
        session.add(template)
        session.commit()
        session.refresh(template)
        return template

    @staticmethod
    def _create_point(
        session,
        template_id: int,
        x_mm: float,
        y_mm: float,
        z_mm: float,
    ) -> FittingHolePointModel:
        point = FittingHolePointModel(
            template_id=template_id,
            label="Point",
            x_mm=x_mm,
            y_mm=y_mm,
            z_mm=z_mm,
            diameter_mm=7.0,
            depth_mm=None,
            side="left",
            operation="drill",
            order_index=0,
            quantity=1,
            mirrored=False,
        )
        session.add(point)
        session.commit()
        session.refresh(point)
        return point


if __name__ == "__main__":
    unittest.main()
