from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel


ALLOWED_PLAN_CODES = (
    "trial",
    "free",
    "pro",
    "business",
)


@dataclass(frozen=True, slots=True)
class PlanEntitlementRecord:
    feature: EntitlementFeatureModel
    entitlement: PlanEntitlementModel | None


class PlanEntitlementRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _normalize_feature_key(feature_key: str) -> str:
        normalized = str(feature_key or "").strip()
        if not normalized:
            raise ValueError("feature_key is required")
        return normalized

    @staticmethod
    def _normalize_plan_code(plan_code: str) -> str:
        normalized = str(plan_code or "").strip().lower()
        if normalized not in ALLOWED_PLAN_CODES:
            raise ValueError(f"Unsupported plan_code: {plan_code}")
        return normalized

    def get_feature_by_key(
        self,
        feature_key: str,
        active_only: bool = True,
    ) -> Optional[EntitlementFeatureModel]:
        normalized_feature_key = self._normalize_feature_key(feature_key)
        query = (
            self.session.query(EntitlementFeatureModel)
            .filter(EntitlementFeatureModel.feature_key == normalized_feature_key)
        )
        if active_only:
            query = query.filter(EntitlementFeatureModel.is_active.is_(True))
        return query.first()

    def list_features(
        self,
        active_only: bool = True,
    ) -> list[EntitlementFeatureModel]:
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

    def get_plan_entitlement(
        self,
        feature_id: int,
        plan_code: str,
    ) -> Optional[PlanEntitlementModel]:
        normalized_plan_code = self._normalize_plan_code(plan_code)
        return (
            self.session.query(PlanEntitlementModel)
            .filter(PlanEntitlementModel.feature_id == feature_id)
            .filter(PlanEntitlementModel.plan_code == normalized_plan_code)
            .first()
        )

    def get_entitlement_by_feature_key(
        self,
        feature_key: str,
        plan_code: str,
        *,
        active_only: bool = True,
    ) -> Optional[PlanEntitlementRecord]:
        normalized_plan_code = self._normalize_plan_code(plan_code)
        feature = self.get_feature_by_key(feature_key, active_only=active_only)
        if feature is None:
            return None

        entitlement = self.get_plan_entitlement(feature.id, normalized_plan_code)
        return PlanEntitlementRecord(
            feature=feature,
            entitlement=entitlement,
        )

    def list_plan_entitlements(
        self,
        plan_code: str,
        *,
        active_only: bool = True,
    ) -> list[PlanEntitlementRecord]:
        normalized_plan_code = self._normalize_plan_code(plan_code)
        features = self.list_features(active_only=active_only)
        entitlements = {
            entitlement.feature_id: entitlement
            for entitlement in (
                self.session.query(PlanEntitlementModel)
                .filter(PlanEntitlementModel.plan_code == normalized_plan_code)
                .all()
            )
        }
        return [
            PlanEntitlementRecord(
                feature=feature,
                entitlement=entitlements.get(feature.id),
            )
            for feature in features
        ]


__all__ = [
    "ALLOWED_PLAN_CODES",
    "PlanEntitlementRecord",
    "PlanEntitlementRepository",
]
