from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel


PLAN_CODE_ORDER = {
    "trial": 0,
    "free": 1,
    "pro": 2,
    "business": 3,
}


class AdminEntitlementRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_features(self, active_only: bool = False) -> list[EntitlementFeatureModel]:
        query = self.session.query(EntitlementFeatureModel)
        if active_only:
            query = query.filter(EntitlementFeatureModel.is_active.is_(True))
        return (
            query.order_by(
                EntitlementFeatureModel.category.asc(),
                EntitlementFeatureModel.sort_order.asc(),
                EntitlementFeatureModel.feature_key.asc(),
                EntitlementFeatureModel.id.asc(),
            )
            .all()
        )

    def get_feature_by_id(self, feature_id: int) -> Optional[EntitlementFeatureModel]:
        return self.session.get(EntitlementFeatureModel, feature_id)

    def get_feature_by_key(self, feature_key: str) -> Optional[EntitlementFeatureModel]:
        normalized_feature_key = str(feature_key or "").strip()
        if not normalized_feature_key:
            return None
        return (
            self.session.query(EntitlementFeatureModel)
            .filter(EntitlementFeatureModel.feature_key == normalized_feature_key)
            .first()
        )

    def list_entitlements(self) -> list[PlanEntitlementModel]:
        entitlements = self.session.query(PlanEntitlementModel).all()
        return sorted(
            entitlements,
            key=lambda entitlement: (
                entitlement.feature_id,
                PLAN_CODE_ORDER.get(entitlement.plan_code, 99),
                entitlement.id,
            ),
        )

    def list_entitlements_for_feature(self, feature_id: int) -> list[PlanEntitlementModel]:
        entitlements = (
            self.session.query(PlanEntitlementModel)
            .filter(PlanEntitlementModel.feature_id == feature_id)
            .all()
        )
        return sorted(
            entitlements,
            key=lambda entitlement: (
                PLAN_CODE_ORDER.get(entitlement.plan_code, 99),
                entitlement.id,
            ),
        )

    def get_entitlement(
        self,
        feature_id: int,
        plan_code: str,
    ) -> Optional[PlanEntitlementModel]:
        normalized_plan_code = str(plan_code or "").strip().lower()
        if not normalized_plan_code:
            return None
        return (
            self.session.query(PlanEntitlementModel)
            .filter(PlanEntitlementModel.feature_id == feature_id)
            .filter(PlanEntitlementModel.plan_code == normalized_plan_code)
            .first()
        )

    def add_feature(self, feature: EntitlementFeatureModel) -> EntitlementFeatureModel:
        self.session.add(feature)
        return feature

    def add_entitlements(
        self,
        entitlements: list[PlanEntitlementModel],
    ) -> list[PlanEntitlementModel]:
        self.session.add_all(entitlements)
        return entitlements


__all__ = [
    "AdminEntitlementRepository",
    "PLAN_CODE_ORDER",
]
