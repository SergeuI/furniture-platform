from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLogModel
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel
from database.repositories.admin_entitlement_repository import (
    AdminEntitlementRepository,
    PLAN_CODE_ORDER,
)
from database.session import SessionLocal


FEATURE_VALUE_TYPES = {
    "boolean",
    "integer",
    "decimal",
    "text",
    "enum",
}

PLAN_CODES = tuple(PLAN_CODE_ORDER.keys())
FEATURE_KEY_PATTERN = re.compile(r"^[a-z0-9._]+$")


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _audit_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _audit_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_audit_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_audit_safe(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class AdminEntitlementMatrixCell:
    feature_id: int
    plan_code: str
    old_value: dict[str, Any]
    new_value: dict[str, Any]


class AdminEntitlementService:
    def __init__(
        self,
        session: Session | None = None,
        repository: AdminEntitlementRepository | None = None,
    ) -> None:
        if repository is not None and session is None:
            session = getattr(repository, "session", None)

        self.session = session or SessionLocal()
        self._owns_session = session is None and repository is None
        self.repository = repository or AdminEntitlementRepository(self.session)

    def close(self) -> None:
        if self._owns_session and self.session is not None:
            self.session.close()

    def __enter__(self) -> "AdminEntitlementService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def _normalize_feature_key(feature_key: str) -> str:
        normalized = _safe_text(feature_key)
        if not normalized:
            raise ValueError("feature_key є обов'язковим")
        if not FEATURE_KEY_PATTERN.match(normalized):
            raise ValueError(
                "feature_key може містити лише малі латинські літери, цифри, крапки та підкреслення"
            )
        return normalized

    @staticmethod
    def _normalize_required_text(value: Any, field_name: str, max_length: int | None = None) -> str:
        text = _safe_text(value)
        if not text:
            raise ValueError(f"{field_name} є обов'язковим")
        if max_length is not None and len(text) > max_length:
            raise ValueError(f"{field_name} завелике")
        return text

    @staticmethod
    def _normalize_optional_text(value: Any, max_length: int | None = None) -> str | None:
        text = _safe_text(value)
        if text is None:
            return None
        if max_length is not None and len(text) > max_length:
            raise ValueError("Значення завелике")
        return text

    @staticmethod
    def _normalize_value_type(value_type: Any) -> str:
        normalized = _safe_text(value_type)
        if not normalized:
            raise ValueError("value_type є обов'язковим")
        normalized = normalized.lower()
        if normalized not in FEATURE_VALUE_TYPES:
            raise ValueError("Непідтримуваний value_type")
        return normalized

    @staticmethod
    def _normalize_plan_code(plan_code: Any) -> str:
        normalized = _safe_text(plan_code)
        if not normalized:
            raise ValueError("plan_code є обов'язковим")
        normalized = normalized.lower()
        if normalized not in PLAN_CODES:
            raise ValueError("Непідтримуваний plan_code")
        return normalized

    @staticmethod
    def _normalize_decimal_value(value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, float):
            raise ValueError("decimal_value має бути Decimal або рядком, а не float")
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("decimal_value має бути Decimal або рядком") from exc

    @staticmethod
    def _normalize_enum_options(value: Any, *, value_type: str) -> list[str] | None:
        if value_type != "enum":
            if value in (None, [], ()):
                return None
            raise ValueError("enum_options_json дозволено лише для value_type=enum")

        if value in (None, [], ()):
            raise ValueError("Для enum потрібно вказати перелік enum_options_json")

        if not isinstance(value, (list, tuple)):
            raise ValueError("enum_options_json має бути списком")

        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = _safe_text(item)
            if not text:
                raise ValueError("enum_options_json не може містити порожні значення")
            if text in seen:
                raise ValueError("enum_options_json не може містити дублікати")
            seen.add(text)
            normalized.append(text)
        return normalized

    @staticmethod
    def _serialize_feature(feature: EntitlementFeatureModel) -> dict[str, Any]:
        return {
            "id": feature.id,
            "feature_key": feature.feature_key,
            "name_uk": feature.name_uk,
            "description_uk": feature.description_uk,
            "category": feature.category,
            "value_type": feature.value_type,
            "enum_options_json": feature.enum_options_json,
            "is_system": bool(feature.is_system),
            "is_active": bool(feature.is_active),
            "sort_order": int(feature.sort_order or 0),
            "created_at": feature.created_at,
            "updated_at": feature.updated_at,
        }

    @staticmethod
    def _serialize_plan_entitlement(
        entitlement: PlanEntitlementModel | None,
        feature_id: int,
        plan_code: str,
    ) -> dict[str, Any]:
        if entitlement is None:
            return {
                "id": None,
                "feature_id": feature_id,
                "plan_code": plan_code,
                "bool_value": None,
                "integer_value": None,
                "decimal_value": None,
                "text_value": None,
                "is_unlimited": False,
                "is_not_applicable": False,
                "created_at": None,
                "updated_at": None,
            }

        return {
            "id": entitlement.id,
            "feature_id": entitlement.feature_id,
            "plan_code": entitlement.plan_code,
            "bool_value": entitlement.bool_value,
            "integer_value": entitlement.integer_value,
            "decimal_value": entitlement.decimal_value,
            "text_value": entitlement.text_value,
            "is_unlimited": bool(entitlement.is_unlimited),
            "is_not_applicable": bool(entitlement.is_not_applicable),
            "created_at": entitlement.created_at,
            "updated_at": entitlement.updated_at,
        }

    def _serialize_matrix_row(self, feature: EntitlementFeatureModel) -> dict[str, Any]:
        entitlements = {
            entitlement.plan_code: entitlement
            for entitlement in self.repository.list_entitlements_for_feature(feature.id)
        }
        return {
            "feature": self._serialize_feature(feature),
            "trial": self._serialize_plan_entitlement(entitlements.get("trial"), feature.id, "trial"),
            "free": self._serialize_plan_entitlement(entitlements.get("free"), feature.id, "free"),
            "pro": self._serialize_plan_entitlement(entitlements.get("pro"), feature.id, "pro"),
            "business": self._serialize_plan_entitlement(entitlements.get("business"), feature.id, "business"),
        }

    def _record_audit_log(
        self,
        *,
        actor_user_id: str,
        actor_email: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any] | None = None,
    ) -> AuditLogModel:
        audit_log = AuditLogModel(
            actor_user_id=str(actor_user_id),
            actor_email=str(actor_email),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=_audit_safe(details or {}),
        )
        self.session.add(audit_log)
        return audit_log

    def _commit(self) -> None:
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def list_features(self, active_only: bool = False) -> list[dict[str, Any]]:
        return [
            self._serialize_feature(feature)
            for feature in self.repository.list_features(active_only=active_only)
        ]

    def create_feature(
        self,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = dict(data or {})
        payload.update(kwargs)

        feature_key = self._normalize_feature_key(payload.get("feature_key"))
        if self.repository.get_feature_by_key(feature_key) is not None:
            raise ValueError("Фіча з таким feature_key вже існує")

        name_uk = self._normalize_required_text(payload.get("name_uk"), "name_uk", 255)
        description_uk = self._normalize_optional_text(payload.get("description_uk"), 5000)
        category = self._normalize_required_text(payload.get("category"), "category", 128)
        value_type = self._normalize_value_type(payload.get("value_type"))
        enum_options_json = self._normalize_enum_options(
            payload.get("enum_options_json"),
            value_type=value_type,
        )
        is_active = bool(payload.get("is_active", True))
        sort_order = int(payload.get("sort_order", 0) or 0)

        feature = EntitlementFeatureModel(
            feature_key=feature_key,
            name_uk=name_uk,
            description_uk=description_uk,
            category=category,
            value_type=value_type,
            enum_options_json=enum_options_json,
            is_system=False,
            is_active=is_active,
            sort_order=sort_order,
        )

        try:
            self.repository.add_feature(feature)
            self.session.flush()

            entitlements = [
                PlanEntitlementModel(
                    feature_id=feature.id,
                    plan_code=plan_code,
                    bool_value=None,
                    integer_value=None,
                    decimal_value=None,
                    text_value=None,
                    is_unlimited=False,
                    is_not_applicable=False,
                )
                for plan_code in PLAN_CODES
            ]
            self.repository.add_entitlements(entitlements)
            self.session.flush()

            self._record_audit_log(
                actor_user_id=str(payload.get("actor_user_id") or "admin"),
                actor_email=str(payload.get("actor_email") or "admin@example.com"),
                action="entitlement.feature.created",
                entity_type="entitlement_feature",
                entity_id=str(feature.id),
                details={
                    "feature_key": feature.feature_key,
                    "name_uk": feature.name_uk,
                    "value_type": feature.value_type,
                    "category": feature.category,
                },
            )

            self._commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ValueError("Фіча з таким feature_key вже існує") from exc
        except Exception:
            self.session.rollback()
            raise

        self.session.refresh(feature)
        return {
            "feature": self._serialize_feature(feature),
            "matrix_row": self._serialize_matrix_row(feature),
        }

    def update_feature(
        self,
        feature_id: int,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = dict(data or {})
        payload.update(kwargs)

        if "feature_key" in payload:
            raise ValueError("feature_key змінювати не можна")

        feature = self.repository.get_feature_by_id(int(feature_id))
        if feature is None:
            raise ValueError("Фіча не знайдена")

        old_feature = self._serialize_feature(feature)
        old_value_type = feature.value_type

        try:
            changed_fields: dict[str, dict[str, Any]] = {}

            if "name_uk" in payload:
                new_value = self._normalize_required_text(payload.get("name_uk"), "name_uk", 255)
                if new_value != feature.name_uk:
                    changed_fields["name_uk"] = {"old": feature.name_uk, "new": new_value}
                feature.name_uk = new_value

            if "description_uk" in payload:
                new_value = self._normalize_optional_text(payload.get("description_uk"), 5000)
                if new_value != feature.description_uk:
                    changed_fields["description_uk"] = {"old": feature.description_uk, "new": new_value}
                feature.description_uk = new_value

            if "category" in payload:
                new_value = self._normalize_required_text(payload.get("category"), "category", 128)
                if new_value != feature.category:
                    changed_fields["category"] = {"old": feature.category, "new": new_value}
                feature.category = new_value

            if "value_type" in payload:
                new_value_type = self._normalize_value_type(payload.get("value_type"))
                if new_value_type != feature.value_type:
                    changed_fields["value_type"] = {"old": feature.value_type, "new": new_value_type}
                feature.value_type = new_value_type
                if new_value_type != "enum":
                    if payload.get("enum_options_json") not in (None, [], ()):
                        raise ValueError("enum_options_json дозволено лише для value_type=enum")
                    feature.enum_options_json = None
                else:
                    feature.enum_options_json = self._normalize_enum_options(
                        payload.get("enum_options_json", feature.enum_options_json),
                        value_type="enum",
                    )
            elif "enum_options_json" in payload:
                feature.enum_options_json = self._normalize_enum_options(
                    payload.get("enum_options_json"),
                    value_type=feature.value_type,
                )

            if "is_active" in payload:
                new_value = bool(payload.get("is_active"))
                if new_value != bool(feature.is_active):
                    changed_fields["is_active"] = {"old": bool(feature.is_active), "new": new_value}
                feature.is_active = new_value

            if "sort_order" in payload:
                new_value = int(payload.get("sort_order") or 0)
                if new_value != int(feature.sort_order or 0):
                    changed_fields["sort_order"] = {"old": int(feature.sort_order or 0), "new": new_value}
                feature.sort_order = new_value

            reset_plan_codes: list[str] = []
            if feature.value_type != old_value_type:
                reset_plan_codes = list(PLAN_CODES)
                for entitlement in self.repository.list_entitlements_for_feature(feature.id):
                    entitlement.bool_value = None
                    entitlement.integer_value = None
                    entitlement.decimal_value = None
                    entitlement.text_value = None
                    entitlement.is_unlimited = False
                    entitlement.is_not_applicable = False

            self._record_audit_log(
                actor_user_id=str(payload.get("actor_user_id") or "admin"),
                actor_email=str(payload.get("actor_email") or "admin@example.com"),
                action="entitlement.feature.updated",
                entity_type="entitlement_feature",
                entity_id=str(feature.id),
                details={
                    "feature_id": feature.id,
                    "feature_key": feature.feature_key,
                    "changed_fields": changed_fields,
                    "old": old_feature,
                    "new": self._serialize_feature(feature),
                    "matrix_reset_plan_codes": reset_plan_codes,
                },
            )

            self._commit()
        except Exception:
            self.session.rollback()
            raise

        self.session.refresh(feature)
        return {
            "feature": self._serialize_feature(feature),
            "matrix_row": self._serialize_matrix_row(feature),
        }

    def get_matrix(self) -> dict[str, Any]:
        features = self.repository.list_features(active_only=False)
        return {
            "matrix": [
                self._serialize_matrix_row(feature)
                for feature in features
            ]
        }

    def update_matrix(
        self,
        rows: Iterable[dict[str, Any]],
        *,
        actor_user_id: str = "admin",
        actor_email: str = "admin@example.com",
    ) -> dict[str, Any]:
        normalized_rows = [dict(row) for row in rows]
        if not normalized_rows:
            return {
                "matrix": self.get_matrix()["matrix"],
                "updated_count": 0,
            }

        duplicate_keys: set[tuple[int, str]] = set()
        validated_rows: list[dict[str, Any]] = []
        features_by_id = {
            feature.id: feature
            for feature in self.repository.list_features(active_only=False)
        }

        for row in normalized_rows:
            feature_id = int(row.get("feature_id") or 0)
            if feature_id <= 0:
                raise ValueError("feature_id є обов'язковим")

            plan_code = self._normalize_plan_code(row.get("plan_code"))
            key = (feature_id, plan_code)
            if key in duplicate_keys:
                raise ValueError("У payload є дубльовані значення feature_id + plan_code")
            duplicate_keys.add(key)

            feature = features_by_id.get(feature_id)
            if feature is None:
                raise ValueError(f"Фіча з id={feature_id} не знайдена")

            bool_value = row.get("bool_value")
            integer_value = row.get("integer_value")
            decimal_value = self._normalize_decimal_value(row.get("decimal_value"))
            text_value = _safe_text(row.get("text_value"))
            is_unlimited = bool(row.get("is_unlimited", False))
            is_not_applicable = bool(row.get("is_not_applicable", False))

            if is_unlimited and is_not_applicable:
                raise ValueError("is_unlimited та is_not_applicable не можуть бути true одночасно")
            if is_not_applicable and any(
                value is not None
                for value in (bool_value, integer_value, decimal_value, text_value)
            ):
                raise ValueError("is_not_applicable вимагає порожнє значення")

            normalized_row = {
                "feature_id": feature_id,
                "plan_code": plan_code,
                "bool_value": None,
                "integer_value": None,
                "decimal_value": None,
                "text_value": None,
                "is_unlimited": False,
                "is_not_applicable": False,
            }

            if feature.value_type == "boolean":
                if is_unlimited:
                    raise ValueError("is_unlimited дозволено лише для integer та decimal")
                if integer_value is not None or decimal_value is not None or text_value is not None:
                    raise ValueError("boolean використовує лише bool_value")
                normalized_row["bool_value"] = bool_value
                normalized_row["is_not_applicable"] = is_not_applicable
            elif feature.value_type == "integer":
                if text_value is not None or bool_value is not None or decimal_value is not None:
                    raise ValueError("integer використовує лише integer_value або is_unlimited")
                if is_unlimited:
                    if integer_value is not None:
                        raise ValueError("integer використовує лише integer_value або is_unlimited")
                    normalized_row["is_unlimited"] = True
                else:
                    normalized_row["integer_value"] = integer_value
                    normalized_row["is_not_applicable"] = is_not_applicable
            elif feature.value_type == "decimal":
                if text_value is not None or bool_value is not None or integer_value is not None:
                    raise ValueError("decimal використовує лише decimal_value або is_unlimited")
                if is_unlimited:
                    normalized_row["is_unlimited"] = True
                else:
                    normalized_row["decimal_value"] = decimal_value
                    normalized_row["is_not_applicable"] = is_not_applicable
            elif feature.value_type in {"text", "enum"}:
                if is_unlimited:
                    raise ValueError("is_unlimited дозволено лише для integer та decimal")
                if bool_value is not None or integer_value is not None or decimal_value is not None:
                    raise ValueError("text/enum використовують лише text_value")
                if feature.value_type == "enum" and text_value is not None:
                    allowed_options = [
                        _safe_text(option)
                        for option in (feature.enum_options_json or [])
                    ]
                    if text_value not in allowed_options:
                        raise ValueError("text_value не входить до enum_options_json")
                normalized_row["text_value"] = text_value
                normalized_row["is_not_applicable"] = is_not_applicable
            else:
                raise ValueError("Непідтримуваний value_type")

            if normalized_row["is_not_applicable"]:
                normalized_row["bool_value"] = None
                normalized_row["integer_value"] = None
                normalized_row["decimal_value"] = None
                normalized_row["text_value"] = None
                normalized_row["is_unlimited"] = False

            validated_rows.append(
                {
                    "feature": feature,
                    "normalized": normalized_row,
                }
            )

        try:
            changed_cells: list[dict[str, Any]] = []
            changed_count = 0
            matrix_features = {
                feature.id: feature
                for feature in features_by_id.values()
            }

            existing_rows = {
                (entitlement.feature_id, entitlement.plan_code): entitlement
                for entitlement in self.repository.list_entitlements()
            }

            for item in validated_rows:
                feature = item["feature"]
                normalized = item["normalized"]
                key = (normalized["feature_id"], normalized["plan_code"])
                entitlement = existing_rows.get(key)
                if entitlement is None:
                    entitlement = PlanEntitlementModel(
                        feature_id=normalized["feature_id"],
                        plan_code=normalized["plan_code"],
                    )
                    self.session.add(entitlement)
                    existing_rows[key] = entitlement

                old_value = self._serialize_plan_entitlement(
                    entitlement if entitlement.id is not None else None,
                    normalized["feature_id"],
                    normalized["plan_code"],
                )
                new_value = dict(old_value)
                new_value.update(
                    {
                        "feature_id": normalized["feature_id"],
                        "plan_code": normalized["plan_code"],
                        "bool_value": normalized["bool_value"],
                        "integer_value": normalized["integer_value"],
                        "decimal_value": normalized["decimal_value"],
                        "text_value": normalized["text_value"],
                        "is_unlimited": normalized["is_unlimited"],
                        "is_not_applicable": normalized["is_not_applicable"],
                    }
                )

                if entitlement.bool_value != normalized["bool_value"]:
                    entitlement.bool_value = normalized["bool_value"]
                if entitlement.integer_value != normalized["integer_value"]:
                    entitlement.integer_value = normalized["integer_value"]
                if entitlement.decimal_value != normalized["decimal_value"]:
                    entitlement.decimal_value = normalized["decimal_value"]
                if entitlement.text_value != normalized["text_value"]:
                    entitlement.text_value = normalized["text_value"]
                if bool(entitlement.is_unlimited) != normalized["is_unlimited"]:
                    entitlement.is_unlimited = normalized["is_unlimited"]
                if bool(entitlement.is_not_applicable) != normalized["is_not_applicable"]:
                    entitlement.is_not_applicable = normalized["is_not_applicable"]

                if old_value != new_value:
                    changed_count += 1
                    changed_cells.append(
                        {
                            "feature_id": normalized["feature_id"],
                            "feature_key": feature.feature_key,
                            "plan_code": normalized["plan_code"],
                            "old_value": old_value,
                            "new_value": new_value,
                        }
                    )

            self.session.flush()

            self._record_audit_log(
                actor_user_id=actor_user_id,
                actor_email=actor_email,
                action="entitlement.matrix.updated",
                entity_type="entitlement_matrix",
                entity_id="all",
                details={
                    "feature_ids": sorted({item["normalized"]["feature_id"] for item in validated_rows}),
                    "plan_codes": sorted({item["normalized"]["plan_code"] for item in validated_rows}),
                    "changed_cells_count": changed_count,
                    "changes": changed_cells,
                },
            )

            self._commit()
        except Exception:
            self.session.rollback()
            raise

        return {
            "updated_count": changed_count,
            "matrix": self.get_matrix()["matrix"],
            "changes": changed_cells,
        }


__all__ = [
    "AdminEntitlementService",
]
