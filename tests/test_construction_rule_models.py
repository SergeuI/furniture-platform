import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.fitting import FittingModel
from database.models.hole_library import HoleLibraryTypeModel
from database.models.construction_rule import (
    ConstructionRuleModel,
    ConstructionRuleMountingOptionModel,
    ConstructionRuleVariantModel,
)
from database.models.mounting_node import MountingNodeModel
from database.models.mounting_scheme import MountingSchemeModel
from database.models.user import UserModel


class ConstructionRuleModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = create_engine(f"sqlite:///{(Path(self.tmp.name) / 'construction.db').as_posix()}")
        self.addCleanup(self.engine.dispose)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine, tables=[
            UserModel.__table__, MountingNodeModel.__table__, MountingSchemeModel.__table__,
            ConstructionRuleModel.__table__, ConstructionRuleVariantModel.__table__,
            ConstructionRuleMountingOptionModel.__table__,
        ])
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def test_rule_variant_and_node_scheme_relationships(self):
        with self.sessions() as db:
            node = MountingNodeModel(code="confirmat-7x50", name="Confirmat 7x50")
            scheme = MountingSchemeModel(code="confirmat-even", name="Confirmat evenly spaced")
            rule = ConstructionRuleModel(code="side-bottom", name="Боковина - Дно",
                primary_part_role="side_panel", secondary_part_role="bottom_panel",
                connection_type="face_to_edge")
            variant = ConstructionRuleVariantModel(code="bottom_between_sides", name="Дно між боковинами",
                parameters_json={"offset_mm": 0}, is_default=True)
            variant.mounting_options.extend([
                ConstructionRuleMountingOptionModel(mounting_node=node, is_preferred=True),
                ConstructionRuleMountingOptionModel(mounting_scheme=scheme, order_index=1),
            ])
            rule.variants.append(variant)
            db.add_all([node, scheme, rule])
            db.commit()
            db.refresh(rule)
            self.assertEqual(rule.variants[0].mounting_options[0].mounting_node.name, "Confirmat 7x50")
            self.assertEqual(rule.variants[0].mounting_options[1].mounting_scheme.code, "confirmat-even")
            self.assertTrue(rule.variants[0].mounting_options[0].is_preferred)

    def test_active_inactive_fields_and_duplicate_rule_code(self):
        with self.sessions() as db:
            db.add(ConstructionRuleModel(code="side-bottom", name="Rule", primary_part_role="a",
                secondary_part_role="b", connection_type="face_to_edge", is_active=False))
            db.commit()
            db.add(ConstructionRuleModel(code="side-bottom", name="Duplicate", primary_part_role="a",
                secondary_part_role="b", connection_type="face_to_edge"))
            with self.assertRaises(IntegrityError):
                db.commit()

    def test_option_requires_solution_and_foreign_keys(self):
        with self.sessions() as db:
            rule = ConstructionRuleModel(code="side-bottom", name="Rule", primary_part_role="a",
                secondary_part_role="b", connection_type="face_to_edge")
            variant = ConstructionRuleVariantModel(code="v1", name="Variant", rule=rule)
            db.add(ConstructionRuleMountingOptionModel(variant=variant))
            with self.assertRaises(IntegrityError):
                db.commit()

        with self.sessions() as db:
            db.add(ConstructionRuleMountingOptionModel(variant_id=999999, mounting_node_id=999999))
            with self.assertRaises(IntegrityError):
                db.commit()

    def test_options_do_not_duplicate_mounting_engineering_fields(self):
        columns = set(ConstructionRuleMountingOptionModel.__table__.columns.keys())
        for field in ("diameter_mm", "depth_mm", "fitting_id", "hole_template_id", "hole_point_id"):
            self.assertNotIn(field, columns)

    def test_node_only_mounting_option_is_unique_per_variant(self):
        with self.sessions() as db:
            node = MountingNodeModel(code="confirmat-7x50", name="Confirmat 7x50")
            variant = ConstructionRuleVariantModel(
                code="v1",
                name="Variant",
                rule=ConstructionRuleModel(
                    code="side-bottom",
                    name="Rule",
                    primary_part_role="a",
                    secondary_part_role="b",
                    connection_type="face_to_edge",
                ),
            )
            variant.mounting_options.extend([
                ConstructionRuleMountingOptionModel(mounting_node=node),
                ConstructionRuleMountingOptionModel(mounting_node=node),
            ])
            db.add(variant)
            with self.assertRaises(IntegrityError):
                db.commit()

    def test_scheme_only_mounting_option_is_unique_per_variant(self):
        with self.sessions() as db:
            scheme = MountingSchemeModel(code="confirmat-even", name="Confirmat evenly spaced")
            variant = ConstructionRuleVariantModel(
                code="v1",
                name="Variant",
                rule=ConstructionRuleModel(
                    code="side-bottom",
                    name="Rule",
                    primary_part_role="a",
                    secondary_part_role="b",
                    connection_type="face_to_edge",
                ),
            )
            variant.mounting_options.extend([
                ConstructionRuleMountingOptionModel(mounting_scheme=scheme),
                ConstructionRuleMountingOptionModel(mounting_scheme=scheme),
            ])
            db.add(variant)
            with self.assertRaises(IntegrityError):
                db.commit()

    def test_mounting_option_with_both_scheme_and_node_is_allowed(self):
        with self.sessions() as db:
            node = MountingNodeModel(code="confirmat-7x50", name="Confirmat 7x50")
            scheme = MountingSchemeModel(code="confirmat-even", name="Confirmat evenly spaced")
            variant = ConstructionRuleVariantModel(
                code="v1",
                name="Variant",
                rule=ConstructionRuleModel(
                    code="side-bottom",
                    name="Rule",
                    primary_part_role="a",
                    secondary_part_role="b",
                    connection_type="face_to_edge",
                ),
                mounting_options=[ConstructionRuleMountingOptionModel(mounting_node=node, mounting_scheme=scheme)],
            )
            db.add(variant)
            db.commit()


if __name__ == "__main__":
    unittest.main()
