from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from database.repositories.plan_entitlement_repository import (
    ALLOWED_PLAN_CODES,
    PlanEntitlementRecord,
    PlanEntitlementRepository,
)
from database.session import SessionLocal
import services.subscription_service as subscription_service
from services.user_roles import ROLE_ADMIN, normalize_user_role


ADMIN_EFFECTIVE_PLAN = ROLE_ADMIN
LEGACY_PLAN_ALIASES = {
    "premium": "business",
}


class EntitlementAccessDeniedError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class EntitlementResolution:
    feature_key: str
    value_type: str | None
    effective_plan: str
    exists: bool
    entitlement_exists: bool
    allowed: bool
    bool_value: bool | None
    integer_value: int | None
    decimal_value: Decimal | None
    text_value: str | None
    is_unlimited: bool
    is_not_applicable: bool


@dataclass(frozen=True, slots=True)
class LimitResolution:
    feature_key: str
    value_type: str | None
    effective_plan: str
    exists: bool
    entitlement_exists: bool
    allowed: bool
    status: str
    limit_value: int | Decimal | None
    is_unlimited: bool
    is_not_applicable: bool


class EntitlementService:
    def __init__(
        self,
        session: Optional[Session] = None,
        repository: Optional[PlanEntitlementRepository] = None,
    ) -> None:
        if repository is not None and session is None:
            session = getattr(repository, "session", None)

        self.session = session or SessionLocal()
        self._owns_session = session is None and repository is None
        self.repository = repository or PlanEntitlementRepository(self.session)

    def close(self) -> None:
        if self._owns_session and self.session is not None:
            self.session.close()

    def __enter__(self) -> "EntitlementService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def _normalize_feature_key(feature_key: str) -> str:
        normalized = str(feature_key or "").strip()
        if not normalized:
            raise ValueError("feature_key is required")
        return normalized

    @staticmethod
    def _normalize_usage_value(current_usage) -> Decimal:
        if isinstance(current_usage, bool):
            raise ValueError("current_usage must be a non-negative number")
        if current_usage is None:
            raise ValueError("current_usage must be a non-negative number")

        if isinstance(current_usage, Decimal):
            usage = current_usage
        elif isinstance(current_usage, int):
            usage = Decimal(current_usage)
        elif isinstance(current_usage, float):
            usage = Decimal(str(current_usage))
        elif isinstance(current_usage, str):
            text = current_usage.strip()
            if not text:
                raise ValueError("current_usage must be a non-negative number")
            try:
                usage = Decimal(text)
            except InvalidOperation as exc:
                raise ValueError("current_usage must be a non-negative number") from exc
        else:
            raise ValueError("current_usage must be a non-negative number")

        if usage < 0:
            raise ValueError("current_usage cannot be negative")

        return usage

    @staticmethod
    def _normalize_decimal_value(value) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    @staticmethod
    def _serialize_resolved_entitlement(
        feature,
        entitlement,
        *,
        admin_bypass: bool,
    ) -> dict[str, object]:
        value_type = feature.value_type

        if admin_bypass:
            if value_type == "boolean":
                return {
                    "allowed": True,
                    "value_type": value_type,
                    "value": True,
                    "is_unlimited": False,
                    "is_not_applicable": False,
                }

            if value_type in {"integer", "decimal"}:
                return {
                    "allowed": True,
                    "value_type": value_type,
                    "value": None,
                    "is_unlimited": True,
                    "is_not_applicable": False,
                }

            return {
                "allowed": True,
                "value_type": value_type,
                "value": None,
                "is_unlimited": False,
                "is_not_applicable": False,
            }

        if entitlement is None:
            return {
                "allowed": False,
                "value_type": value_type,
                "value": None,
                "is_unlimited": False,
                "is_not_applicable": False,
            }

        is_unlimited = bool(getattr(entitlement, "is_unlimited", False))
        is_not_applicable = bool(getattr(entitlement, "is_not_applicable", False))

        if value_type == "boolean":
            value = entitlement.bool_value if entitlement.bool_value is not None else None
            allowed = bool(entitlement.bool_value) and not is_not_applicable
        elif value_type == "integer":
            value = None if entitlement.integer_value is None else int(entitlement.integer_value)
            allowed = (is_unlimited or entitlement.integer_value is not None) and not is_not_applicable
        elif value_type == "decimal":
            decimal_value = EntitlementService._normalize_decimal_value(entitlement.decimal_value)
            value = None if decimal_value is None else float(decimal_value)
            allowed = (is_unlimited or decimal_value is not None) and not is_not_applicable
        elif value_type in {"text", "enum"}:
            value = entitlement.text_value
            allowed = bool(str(value or "").strip()) and not is_not_applicable
        else:
            value = None
            allowed = False

        return {
            "allowed": allowed,
            "value_type": value_type,
            "value": value,
            "is_unlimited": is_unlimited,
            "is_not_applicable": is_not_applicable,
        }

    def build_resolved_entitlement_snapshot(self, user) -> dict[str, dict[str, object]]:
        effective_plan = self.get_effective_plan(user)
        features = self.repository.list_features(active_only=True)
        admin_bypass = effective_plan == ADMIN_EFFECTIVE_PLAN

        if admin_bypass:
            return {
                feature.feature_key: self._serialize_resolved_entitlement(
                    feature,
                    entitlement=None,
                    admin_bypass=True,
                )
                for feature in features
            }

        records = self.repository.list_plan_entitlements(
            effective_plan,
            active_only=True,
        )
        entitlements_by_feature_id = {
            record.feature.id: record.entitlement
            for record in records
        }

        return {
            feature.feature_key: self._serialize_resolved_entitlement(
                feature,
                entitlements_by_feature_id.get(feature.id),
                admin_bypass=False,
            )
            for feature in features
        }

    def get_effective_plan(
        self,
        user,
    ) -> str:
        current_role = normalize_user_role(getattr(user, "role", None))
        if current_role == ROLE_ADMIN:
            return ADMIN_EFFECTIVE_PLAN

        effective_plan = subscription_service.get_effective_plan(user)
        normalized_plan = normalize_user_role(effective_plan)
        return LEGACY_PLAN_ALIASES.get(normalized_plan, normalized_plan)

    def _resolve_entitlement(
        self,
        user,
        feature_key: str,
    ) -> tuple[str, PlanEntitlementRecord | None]:
        normalized_feature_key = self._normalize_feature_key(feature_key)
        effective_plan = self.get_effective_plan(user)

        feature = self.repository.get_feature_by_key(
            normalized_feature_key,
            active_only=True,
        )
        if feature is None:
            return effective_plan, None

        if effective_plan == ADMIN_EFFECTIVE_PLAN:
            return effective_plan, PlanEntitlementRecord(feature=feature, entitlement=None)

        record = self.repository.get_entitlement_by_feature_key(
            normalized_feature_key,
            effective_plan,
            active_only=True,
        )
        return effective_plan, record

    def get_entitlement(
        self,
        user,
        feature_key: str,
    ) -> EntitlementResolution:
        effective_plan, record = self._resolve_entitlement(user, feature_key)
        normalized_feature_key = self._normalize_feature_key(feature_key)

        if record is None:
            return EntitlementResolution(
                feature_key=normalized_feature_key,
                value_type=None,
                effective_plan=effective_plan,
                exists=False,
                entitlement_exists=False,
                allowed=False,
                bool_value=None,
                integer_value=None,
                decimal_value=None,
                text_value=None,
                is_unlimited=False,
                is_not_applicable=False,
            )

        feature = record.feature
        entitlement = record.entitlement
        if entitlement is None:
            is_numeric = feature.value_type in {"integer", "decimal"}
            return EntitlementResolution(
                feature_key=feature.feature_key,
                value_type=feature.value_type,
                effective_plan=effective_plan,
                exists=True,
                entitlement_exists=False,
                allowed=effective_plan == ADMIN_EFFECTIVE_PLAN,
                bool_value=None,
                integer_value=None,
                decimal_value=None,
                text_value=None,
                is_unlimited=is_numeric and effective_plan == ADMIN_EFFECTIVE_PLAN,
                is_not_applicable=False,
            )

        value_type = feature.value_type
        is_unlimited = bool(getattr(entitlement, "is_unlimited", False))
        is_not_applicable = bool(getattr(entitlement, "is_not_applicable", False))

        bool_value = entitlement.bool_value if value_type == "boolean" else None
        integer_value = entitlement.integer_value if value_type == "integer" else None
        decimal_value = (
            self._normalize_decimal_value(entitlement.decimal_value)
            if value_type == "decimal"
            else None
        )
        text_value = entitlement.text_value if value_type in {"text", "enum"} else None

        if value_type == "boolean":
            allowed = bool_value is True and not is_not_applicable
        elif value_type == "integer":
            allowed = (is_unlimited or integer_value is not None) and not is_not_applicable
        elif value_type == "decimal":
            allowed = (is_unlimited or decimal_value is not None) and not is_not_applicable
        elif value_type in {"text", "enum"}:
            allowed = bool(str(text_value or "").strip()) and not is_not_applicable
        else:
            allowed = False

        return EntitlementResolution(
            feature_key=feature.feature_key,
            value_type=value_type,
            effective_plan=effective_plan,
            exists=True,
            entitlement_exists=True,
            allowed=allowed,
            bool_value=bool_value,
            integer_value=integer_value,
            decimal_value=decimal_value,
            text_value=text_value,
            is_unlimited=is_unlimited,
            is_not_applicable=is_not_applicable,
        )

    def has_feature(
        self,
        user,
        feature_key: str,
    ) -> bool:
        return self.get_entitlement(user, feature_key).allowed

    def get_limit(
        self,
        user,
        feature_key: str,
    ) -> LimitResolution:
        effective_plan, record = self._resolve_entitlement(user, feature_key)
        normalized_feature_key = self._normalize_feature_key(feature_key)

        if record is None:
            return LimitResolution(
                feature_key=normalized_feature_key,
                value_type=None,
                effective_plan=effective_plan,
                exists=False,
                entitlement_exists=False,
                allowed=False,
                status="access_denied",
                limit_value=None,
                is_unlimited=False,
                is_not_applicable=False,
            )

        feature = record.feature
        if feature.value_type not in {"integer", "decimal"}:
            return LimitResolution(
                feature_key=feature.feature_key,
                value_type=feature.value_type,
                effective_plan=effective_plan,
                exists=True,
                entitlement_exists=record.entitlement is not None,
                allowed=False,
                status="wrong_value_type",
                limit_value=None,
                is_unlimited=False,
                is_not_applicable=False,
            )

        if effective_plan == ADMIN_EFFECTIVE_PLAN and record.entitlement is None:
            return LimitResolution(
                feature_key=feature.feature_key,
                value_type=feature.value_type,
                effective_plan=effective_plan,
                exists=True,
                entitlement_exists=False,
                allowed=True,
                status="unlimited",
                limit_value=None,
                is_unlimited=True,
                is_not_applicable=False,
            )

        entitlement = record.entitlement
        if entitlement is None:
            return LimitResolution(
                feature_key=feature.feature_key,
                value_type=feature.value_type,
                effective_plan=effective_plan,
                exists=True,
                entitlement_exists=False,
                allowed=False,
                status="access_denied",
                limit_value=None,
                is_unlimited=False,
                is_not_applicable=False,
            )

        if bool(entitlement.is_not_applicable):
            return LimitResolution(
                feature_key=feature.feature_key,
                value_type=feature.value_type,
                effective_plan=effective_plan,
                exists=True,
                entitlement_exists=True,
                allowed=False,
                status="not_applicable",
                limit_value=None,
                is_unlimited=False,
                is_not_applicable=True,
            )

        if bool(entitlement.is_unlimited):
            return LimitResolution(
                feature_key=feature.feature_key,
                value_type=feature.value_type,
                effective_plan=effective_plan,
                exists=True,
                entitlement_exists=True,
                allowed=True,
                status="unlimited",
                limit_value=None,
                is_unlimited=True,
                is_not_applicable=False,
            )

        if feature.value_type == "integer":
            if entitlement.integer_value is None:
                return LimitResolution(
                    feature_key=feature.feature_key,
                    value_type=feature.value_type,
                    effective_plan=effective_plan,
                    exists=True,
                    entitlement_exists=True,
                    allowed=False,
                    status="access_denied",
                    limit_value=None,
                    is_unlimited=False,
                    is_not_applicable=False,
                )
            return LimitResolution(
                feature_key=feature.feature_key,
                value_type=feature.value_type,
                effective_plan=effective_plan,
                exists=True,
                entitlement_exists=True,
                allowed=True,
                status="limited",
                limit_value=int(entitlement.integer_value),
                is_unlimited=False,
                is_not_applicable=False,
            )

        decimal_value = self._normalize_decimal_value(entitlement.decimal_value)
        if decimal_value is None:
            return LimitResolution(
                feature_key=feature.feature_key,
                value_type=feature.value_type,
                effective_plan=effective_plan,
                exists=True,
                entitlement_exists=True,
                allowed=False,
                status="access_denied",
                limit_value=None,
                is_unlimited=False,
                is_not_applicable=False,
            )

        return LimitResolution(
            feature_key=feature.feature_key,
            value_type=feature.value_type,
            effective_plan=effective_plan,
            exists=True,
            entitlement_exists=True,
            allowed=True,
            status="limited",
            limit_value=decimal_value,
            is_unlimited=False,
            is_not_applicable=False,
        )

    def check_limit(
        self,
        user,
        feature_key: str,
        current_usage,
    ) -> bool:
        usage = self._normalize_usage_value(current_usage)
        limit = self.get_limit(user, feature_key)

        if limit.status in {"access_denied", "not_applicable", "wrong_value_type"}:
            return False

        if limit.status == "unlimited":
            return True

        limit_value = limit.limit_value
        if limit_value is None:
            return False

        limit_decimal = (
            limit_value
            if isinstance(limit_value, Decimal)
            else Decimal(str(limit_value))
        )
        return usage < limit_decimal

    def require_feature(
        self,
        user,
        feature_key: str,
    ) -> EntitlementResolution:
        resolution = self.get_entitlement(user, feature_key)
        if not resolution.allowed:
            raise EntitlementAccessDeniedError(
                f"Access denied for feature_key={resolution.feature_key}"
            )
        return resolution


__all__ = [
    "ADMIN_EFFECTIVE_PLAN",
    "EntitlementAccessDeniedError",
    "EntitlementResolution",
    "EntitlementService",
    "LimitResolution",
]
