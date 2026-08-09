from __future__ import annotations

import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.fitting import FittingModel
from database.models.mounting_node import MountingNodeModel
from database.models.service_catalog_item import ServiceCatalogItemModel
from database.models.service_drilling_rule import ServiceDrillingRuleModel
from database.models.user import UserModel
from database.models.mounting_scheme import MountingSchemeModel
from services.mounting_scheme_service import MountingSchemeService


class MountingSchemeServiceTests(unittest.TestCase):
    def test_create_scheme_serializes_nested_nodes_and_rules(self) -> None:
        session, engine = self._build_session()
        try:
            confirmat = self._create_mounting_node(session, code="confirmat-node", name="Confirmat")
            dowel = self._create_mounting_node(session, code="dowel-node", name="Dowel")

            service = MountingSchemeService(session=session)
            scheme = service.create_mounting_scheme(
                {
                    "name": "Confirmat + Dowel",
                    "nodes": [
                        {
                            "node_id": confirmat.id,
                            "group_key": "primary",
                            "quantity_per_group": 1,
                            "order_index": 0,
                        },
                        {
                            "node_id": dowel.id,
                            "group_key": "joint",
                            "quantity_per_group": 1,
                            "order_index": 1,
                        },
                    ],
                    "placement_rules": [
                        {
                            "group_key": "primary",
                            "distribution_mode": "equal",
                            "min_group_count": 3,
                            "fixed_group_count": 3,
                            "start_offset_mm": 50,
                            "end_offset_mm": 50,
                            "max_spacing_mm": 400,
                        }
                    ],
                }
            )

            self.assertTrue(scheme["code"].startswith("mounting-scheme-confirmat-dowel-"))
            self.assertEqual(scheme["nodes_count"], 2)
            self.assertEqual(scheme["placement_rules_count"], 1)
            self.assertEqual([node["group_key"] for node in scheme["nodes"]], ["primary", "joint"])
            self.assertEqual(scheme["nodes"][0]["node_name"], "Confirmat")
            self.assertEqual(scheme["placement_rules"][0]["group_key"], "primary")
            self.assertEqual(scheme["placement_rules"][0]["distribution_mode"], "equal")
        finally:
            session.close()
            engine.dispose()

    def test_create_scheme_generates_unique_code_when_omitted(self) -> None:
        session, engine = self._build_session()
        try:
            node = self._create_mounting_node(session, code="confirmat-node", name="Confirmat")
            service = MountingSchemeService(session=session)

            scheme = service.create_mounting_scheme(
                {
                    "name": "Confirmat scheme",
                    "nodes": [
                        {
                            "node_id": node.id,
                            "group_key": "primary",
                            "quantity_per_group": 1,
                        }
                    ],
                }
            )

            self.assertTrue(scheme["code"].startswith("mounting-scheme-confirmat-scheme-"))
        finally:
            session.close()
            engine.dispose()

    def test_create_scheme_rejects_duplicate_code(self) -> None:
        session, engine = self._build_session()
        try:
            node = self._create_mounting_node(session, code="confirmat-node", name="Confirmat")
            service = MountingSchemeService(session=session)
            service.create_mounting_scheme(
                {
                    "code": "scheme-a",
                    "name": "Scheme A",
                    "nodes": [
                        {
                            "node_id": node.id,
                            "group_key": "primary",
                            "quantity_per_group": 1,
                        }
                    ],
                }
            )

            with self.assertRaisesRegex(ValueError, "already exists"):
                service.create_mounting_scheme(
                    {
                        "code": "scheme-a",
                        "name": "Scheme B",
                        "nodes": [
                            {
                                "node_id": node.id,
                                "group_key": "primary",
                                "quantity_per_group": 1,
                            }
                        ],
                    }
                )
        finally:
            session.close()
            engine.dispose()

    def test_update_scheme_rollback_keeps_existing_nodes_when_nested_payload_is_invalid(self) -> None:
        session, engine = self._build_session()
        try:
            node = self._create_mounting_node(session, code="confirmat-node", name="Confirmat")
            service = MountingSchemeService(session=session)
            created = service.create_mounting_scheme(
                {
                    "name": "Confirmat scheme",
                    "nodes": [
                        {
                            "node_id": node.id,
                            "group_key": "primary",
                            "quantity_per_group": 1,
                        }
                    ],
                }
            )

            with self.assertRaisesRegex(ValueError, "does not exist"):
                service.update_mounting_scheme(
                    created["id"],
                    {
                        "nodes": [
                            {
                                "node_id": 9999,
                                "group_key": "primary",
                                "quantity_per_group": 1,
                            }
                        ],
                    },
                )

            refreshed = service.get_mounting_scheme(created["id"])
            self.assertIsNotNone(refreshed)
            self.assertEqual(refreshed["nodes_count"], 1)
            self.assertEqual(refreshed["nodes"][0]["node_name"], "Confirmat")
        finally:
            session.close()
            engine.dispose()

    def test_update_scheme_rejects_rule_group_without_matching_nodes(self) -> None:
        session, engine = self._build_session()
        try:
            node = self._create_mounting_node(session, code="confirmat-node", name="Confirmat")
            service = MountingSchemeService(session=session)
            created = service.create_mounting_scheme(
                {
                    "name": "Confirmat scheme",
                    "nodes": [
                        {
                            "node_id": node.id,
                            "group_key": "primary",
                            "quantity_per_group": 1,
                        }
                    ],
                }
            )

            with self.assertRaisesRegex(ValueError, "must exist among scheme nodes"):
                service.update_mounting_scheme(
                    created["id"],
                    {
                        "placement_rules": [
                            {
                                "group_key": "missing",
                                "distribution_mode": "equal",
                                "min_group_count": 1,
                            }
                        ],
                    },
                )
        finally:
            session.close()
            engine.dispose()

    def test_list_mounting_schemes_filters_inactive_by_default(self) -> None:
        session, engine = self._build_session()
        try:
            node = self._create_mounting_node(session, code="confirmat-node", name="Confirmat")
            service = MountingSchemeService(session=session)
            active = service.create_mounting_scheme(
                {
                    "name": "Active scheme",
                    "nodes": [
                        {
                            "node_id": node.id,
                            "group_key": "primary",
                            "quantity_per_group": 1,
                        }
                    ],
                }
            )
            service.create_mounting_scheme(
                {
                    "name": "Inactive scheme",
                    "is_active": False,
                    "nodes": [
                        {
                            "node_id": node.id,
                            "group_key": "primary",
                            "quantity_per_group": 1,
                        }
                    ],
                }
            )

            active_list = service.list_mounting_schemes()
            all_list = service.list_mounting_schemes(include_inactive=True)

            self.assertEqual([scheme["id"] for scheme in active_list], [active["id"]])
            self.assertEqual(len(all_list), 2)
        finally:
            session.close()
            engine.dispose()

    @staticmethod
    def _build_session():
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
        return Session(), engine

    @staticmethod
    def _create_mounting_node(session, *, code: str, name: str) -> MountingNodeModel:
        node = MountingNodeModel(code=code, name=name)
        session.add(node)
        session.commit()
        session.refresh(node)
        return node


if __name__ == "__main__":
    unittest.main()
