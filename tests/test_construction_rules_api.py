from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import auth as auth_dependencies
from api.routes import construction_rules as construction_rules_route
from database.base import Base
from database.models.construction_rule import (
    ConstructionRuleModel,
    ConstructionRuleMountingOptionModel,
    ConstructionRuleVariantModel,
)
from database.models.fitting import FittingModel  # noqa: F401 - register mapper
from database.models.hole_library import HoleLibraryTypeModel  # noqa: F401 - register mapper
from database.models.mounting_node import MountingNodeModel
from database.models.mounting_scheme import MountingSchemeModel
from database.models.user import UserModel  # noqa: F401 - register mapper
from services import construction_rule_service as service_module


class ConstructionRulesApiTests(unittest.TestCase):
    def test_list_detail_and_not_found(self) -> None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = session_factory()
        try:
            node = MountingNodeModel(code="confirmat-node", name="Confirmat", fastening_type="confirmat")
            scheme = MountingSchemeModel(code="confirmat-scheme", name="Confirmat scheme", description="Even spacing")
            active = ConstructionRuleModel(
                code="side-bottom", name="Side bottom", description="Active rule",
                primary_part_role="side_panel", secondary_part_role="bottom_panel", connection_type="face_to_edge",
            )
            active.variants.extend([
                ConstructionRuleVariantModel(code="later", name="Later", order_index=2),
                ConstructionRuleVariantModel(
                    code="default", name="Default", order_index=1, is_default=True,
                    parameters_json={"offset_mm": 12},
                    mounting_options=[
                        ConstructionRuleMountingOptionModel(mounting_node=node, is_preferred=True, order_index=1),
                        ConstructionRuleMountingOptionModel(mounting_scheme=scheme, order_index=2),
                    ],
                ),
            ])
            inactive = ConstructionRuleModel(
                code="inactive", name="Inactive", primary_part_role="a",
                secondary_part_role="b", connection_type="x", is_active=False,
            )
            session.add_all([active, inactive, node, scheme])
            session.commit()
            session.refresh(active)
            rule_id = active.id
        finally:
            session.close()

        app = FastAPI()
        app.include_router(construction_rules_route.router, prefix="/construction-rules")
        app.dependency_overrides[auth_dependencies.require_current_user] = lambda: SimpleNamespace(id="user-1", role="admin")
        with patch.object(service_module, "SessionLocal", session_factory):
            with TestClient(app) as client:
                response = client.get("/construction-rules")
                self.assertEqual(response.status_code, 200)
                self.assertEqual([item["code"] for item in response.json()["rules"]], ["side-bottom"])

                detail = client.get(f"/construction-rules/{rule_id}")
                self.assertEqual(detail.status_code, 200)
                payload = detail.json()["rule"]
                self.assertEqual([item["code"] for item in payload["variants"]], ["default", "later"])
                option = payload["variants"][0]["mounting_options"]
                self.assertEqual(option[0]["mounting_node"]["code"], "confirmat-node")
                self.assertEqual(option[1]["mounting_scheme"]["code"], "confirmat-scheme")
                self.assertTrue(option[0]["is_preferred"])
                self.assertEqual(payload["variants"][0]["parameters"], {"offset_mm": 12})
                self.assertNotIn("diameter_mm", str(payload))
                self.assertEqual(client.get("/construction-rules/999999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
