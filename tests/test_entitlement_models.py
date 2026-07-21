from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


class EntitlementModelTests(unittest.TestCase):
    def test_models_store_values_and_defaults(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session = self._create_session(Path(tmpdir) / "entitlements.db")

            with session() as db:
                feature = EntitlementFeatureModel(
                    feature_key="ai_scan_limit",
                    name_uk="Ліміт AI-сканів",
                    description_uk="Максимальна кількість AI-операцій на план",
                    category="ai",
                    value_type="integer",
                    enum_options_json=None,
                )
                db.add(feature)
                db.commit()
                db.refresh(feature)

                self.assertTrue(feature.is_active)
                self.assertEqual(feature.sort_order, 0)
                self.assertIsNotNone(feature.created_at)
                self.assertIsNotNone(feature.updated_at)

                db.add_all(
                    [
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="trial",
                            bool_value=None,
                            integer_value=20,
                            decimal_value=None,
                            text_value=None,
                            is_unlimited=False,
                            is_not_applicable=False,
                        ),
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="free",
                            integer_value=5,
                        ),
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="pro",
                            decimal_value=Decimal("12.5"),
                        ),
                        PlanEntitlementModel(
                            feature_id=feature.id,
                            plan_code="business",
                            text_value="unlimited",
                            is_unlimited=True,
                        ),
                    ]
                )
                db.commit()

                rows = db.query(PlanEntitlementModel).order_by(PlanEntitlementModel.plan_code).all()
                self.assertEqual(len(rows), 4)
                self.assertEqual(rows[0].plan_code, "business")
                self.assertEqual(rows[1].plan_code, "free")
                self.assertEqual(rows[2].plan_code, "pro")
                self.assertEqual(rows[3].plan_code, "trial")

                trial_row = next(row for row in rows if row.plan_code == "trial")
                self.assertEqual(trial_row.integer_value, 20)
                self.assertIsNone(trial_row.bool_value)

    def test_constraints_reject_duplicates_invalid_codes_and_conflicts(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session = self._create_session(Path(tmpdir) / "entitlements.db")

            with session() as db:
                feature = EntitlementFeatureModel(
                    feature_key="export_pdf",
                    name_uk="PDF-експорт",
                    category="export",
                    value_type="boolean",
                )
                db.add(feature)
                db.commit()
                db.refresh(feature)

                duplicate_feature = EntitlementFeatureModel(
                    feature_key="export_pdf",
                    name_uk="Повтор PDF-експорт",
                    category="export",
                    value_type="boolean",
                )
                db.add(duplicate_feature)
                with self.assertRaises(IntegrityError):
                    db.commit()
                db.rollback()

                db.add(
                    PlanEntitlementModel(
                        feature_id=feature.id,
                        plan_code="pro",
                        bool_value=True,
                    )
                )
                db.commit()

                duplicate_plan = PlanEntitlementModel(
                    feature_id=feature.id,
                    plan_code="pro",
                    bool_value=False,
                )
                db.add(duplicate_plan)
                with self.assertRaises(IntegrityError):
                    db.commit()
                db.rollback()

                bad_plan = PlanEntitlementModel(
                    feature_id=feature.id,
                    plan_code="starter",
                    bool_value=True,
                )
                db.add(bad_plan)
                with self.assertRaises(IntegrityError):
                    db.commit()
                db.rollback()

                bad_type = EntitlementFeatureModel(
                    feature_key="bad_type",
                    name_uk="Bad type",
                    category="export",
                    value_type="blob",
                )
                db.add(bad_type)
                with self.assertRaises(IntegrityError):
                    db.commit()
                db.rollback()

                bad_flags = PlanEntitlementModel(
                    feature_id=feature.id,
                    plan_code="business",
                    is_unlimited=True,
                    is_not_applicable=True,
                )
                db.add(bad_flags)
                with self.assertRaises(IntegrityError):
                    db.commit()
                db.rollback()

                missing_feature = PlanEntitlementModel(
                    feature_id=999999,
                    plan_code="free",
                    bool_value=True,
                )
                db.add(missing_feature)
                with self.assertRaises(IntegrityError):
                    db.commit()
                db.rollback()

    @staticmethod
    def _create_session(database_path: Path):
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", _enable_foreign_keys)
        Base.metadata.create_all(
            engine,
            tables=[
                EntitlementFeatureModel.__table__,
                PlanEntitlementModel.__table__,
            ],
        )
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)


if __name__ == "__main__":
    unittest.main()
