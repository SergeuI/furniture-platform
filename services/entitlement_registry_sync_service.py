from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from database.models.audit_log import AuditLogModel
from database.models.entitlement_feature import EntitlementFeatureModel
from database.models.plan_entitlement import PlanEntitlementModel
from database.repositories.admin_entitlement_repository import (
    AdminEntitlementRepository,
    PLAN_CODE_ORDER,
)
from services.entitlement_registry import (
    EntitlementRegistryFeature,
    build_system_entitlement_registry_map,
    get_system_entitlement_registry,
)


PLAN_CODES = tuple(PLAN_CODE_ORDER.keys())


@dataclass(frozen=True, slots=True)
class EntitlementRegistryConflict:
    feature_key: str
    reason: str
    details: dict[str, Any]


class EntitlementRegistrySyncService:
    def __init__(
        self,
        session: Session,
        repository: AdminEntitlementRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or AdminEntitlementRepository(session)

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
        }

    @staticmethod
    def _serialize_plan_entitlement(
        entitlement: PlanEntitlementModel | None,
        *,
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
        }

    @staticmethod
    def _default_plan_row(feature_id: int, plan_code: str) -> PlanEntitlementModel:
        return PlanEntitlementModel(
            feature_id=feature_id,
            plan_code=plan_code,
            bool_value=None,
            integer_value=None,
            decimal_value=None,
            text_value=None,
            is_unlimited=False,
            is_not_applicable=False,
        )

    def _registry(self) -> tuple[EntitlementRegistryFeature, ...]:
        return get_system_entitlement_registry()

    def plan_sync(self) -> dict[str, Any]:
        registry = self._registry()
        registry_by_key = build_system_entitlement_registry_map()
        db_features_by_key = {
            feature.feature_key: feature
            for feature in self.repository.list_features(active_only=False)
        }

        plan: dict[str, Any] = {
            "new_features": [],
            "metadata_updates": [],
            "missing_plan_rows": [],
            "conflicts": [],
            "unchanged": [],
            "registry_features_missing_from_db": [],
            "db_system_features_missing_from_registry": [],
        }

        for registry_feature in registry:
            feature = db_features_by_key.get(registry_feature.feature_key)
            if feature is None:
                plan["new_features"].append(
                    {
                        "feature_key": registry_feature.feature_key,
                        "name_uk": registry_feature.name_uk,
                        "description_uk": registry_feature.description_uk,
                        "category": registry_feature.category,
                        "value_type": registry_feature.value_type,
                        "sort_order": registry_feature.sort_order,
                    }
                )
                plan["registry_features_missing_from_db"].append(registry_feature.feature_key)
                continue

            if not bool(feature.is_system):
                plan["conflicts"].append(
                    {
                        "feature_key": registry_feature.feature_key,
                        "reason": "custom_feature_collision",
                        "details": {
                            "db_feature": self._serialize_feature(feature),
                        },
                    }
                )
                continue

            if feature.value_type != registry_feature.value_type:
                plan["conflicts"].append(
                    {
                        "feature_key": registry_feature.feature_key,
                        "reason": "value_type_mismatch",
                        "details": {
                            "db_value_type": feature.value_type,
                            "registry_value_type": registry_feature.value_type,
                        },
                    }
                )
                continue

            registry_enum_options = list(registry_feature.enum_options_json)
            db_enum_options = list(feature.enum_options_json or [])
            if feature.value_type == "enum" and db_enum_options != registry_enum_options:
                plan["conflicts"].append(
                    {
                        "feature_key": registry_feature.feature_key,
                        "reason": "enum_options_mismatch",
                        "details": {
                            "db_enum_options_json": db_enum_options,
                            "registry_enum_options_json": registry_enum_options,
                        },
                    }
                )
                continue

            metadata_update: dict[str, Any] = {}
            for field_name in ("name_uk", "description_uk", "category", "sort_order"):
                registry_value = getattr(registry_feature, field_name)
                db_value = getattr(feature, field_name)
                if db_value != registry_value:
                    metadata_update[field_name] = {
                        "old": db_value,
                        "new": registry_value,
                    }

            entitlements = {
                entitlement.plan_code: entitlement
                for entitlement in self.repository.list_entitlements_for_feature(feature.id)
            }
            missing_plan_codes = [
                plan_code
                for plan_code in PLAN_CODES
                if plan_code not in entitlements
            ]

            if metadata_update:
                plan["metadata_updates"].append(
                    {
                        "feature_key": registry_feature.feature_key,
                        "changes": metadata_update,
                    }
                )

            if missing_plan_codes:
                plan["missing_plan_rows"].append(
                    {
                        "feature_key": registry_feature.feature_key,
                        "missing_plan_codes": missing_plan_codes,
                    }
                )

            if not metadata_update and not missing_plan_codes:
                plan["unchanged"].append(registry_feature.feature_key)

        for feature in self.repository.list_features(active_only=False):
            if bool(feature.is_system) and feature.feature_key not in registry_by_key:
                plan["db_system_features_missing_from_registry"].append(feature.feature_key)

        return plan

    def _record_audit_log(
        self,
        *,
        actor_user_id: str,
        actor_email: str,
        details: dict[str, Any],
    ) -> AuditLogModel:
        audit_log = AuditLogModel(
            actor_user_id=str(actor_user_id),
            actor_email=str(actor_email),
            action="entitlement.registry.synced",
            entity_type="entitlement_registry",
            entity_id="all",
            details=details,
        )
        self.session.add(audit_log)
        return audit_log

    def _commit(self) -> None:
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def apply_sync(
        self,
        *,
        actor_user_id: str = "cli",
        actor_email: str = "cli@example.com",
        source: str = "cli",
    ) -> dict[str, Any]:
        plan = self.plan_sync()
        if plan["conflicts"]:
            raise ValueError("Registry sync has conflicts")

        registry = self._registry()
        registry_by_key = build_system_entitlement_registry_map()
        if not plan["new_features"] and not plan["metadata_updates"] and not plan["missing_plan_rows"]:
            return {
                "applied": False,
                "created_features": [],
                "updated_features": [],
                "created_plan_rows": [],
                "orphaned_system_feature_keys": plan["db_system_features_missing_from_registry"],
                "summary": plan,
            }

        created_features: list[str] = []
        updated_features: list[str] = []
        created_plan_rows: list[dict[str, Any]] = []

        try:
            db_features_by_key = {
                feature.feature_key: feature
                for feature in self.repository.list_features(active_only=False)
            }

            for registry_feature in registry:
                feature = db_features_by_key.get(registry_feature.feature_key)
                if feature is None:
                    feature = EntitlementFeatureModel(
                        feature_key=registry_feature.feature_key,
                        name_uk=registry_feature.name_uk,
                        description_uk=registry_feature.description_uk,
                        category=registry_feature.category,
                        value_type=registry_feature.value_type,
                        enum_options_json=list(registry_feature.enum_options_json) or None,
                        is_system=True,
                        is_active=True,
                        sort_order=registry_feature.sort_order,
                    )
                    self.repository.add_feature(feature)
                    self.session.flush()
                    created_features.append(feature.feature_key)

                    entitlements = [
                        self._default_plan_row(feature.id, plan_code)
                        for plan_code in PLAN_CODES
                    ]
                    self.repository.add_entitlements(entitlements)
                    self.session.flush()
                    created_plan_rows.extend(
                        {
                            "feature_key": feature.feature_key,
                            "plan_code": plan_code,
                        }
                        for plan_code in PLAN_CODES
                    )
                    db_features_by_key[feature.feature_key] = feature
                    continue

                changed = False
                for field_name in ("name_uk", "description_uk", "category", "sort_order"):
                    registry_value = getattr(registry_feature, field_name)
                    if getattr(feature, field_name) != registry_value:
                        setattr(feature, field_name, registry_value)
                        changed = True

                if changed:
                    updated_features.append(feature.feature_key)

                existing_entitlements = {
                    entitlement.plan_code: entitlement
                    for entitlement in self.repository.list_entitlements_for_feature(feature.id)
                }
                for plan_code in PLAN_CODES:
                    if plan_code in existing_entitlements:
                        continue
                    entitlement = self._default_plan_row(feature.id, plan_code)
                    self.session.add(entitlement)
                    created_plan_rows.append(
                        {
                            "feature_key": feature.feature_key,
                            "plan_code": plan_code,
                        }
                    )

            audit_details = {
                "source": source,
                "created_features_count": len(created_features),
                "created_features": created_features,
                "updated_features_count": len(updated_features),
                "updated_features": updated_features,
                "created_plan_rows_count": len(created_plan_rows),
                "created_plan_rows": created_plan_rows,
                "orphaned_system_feature_keys": plan["db_system_features_missing_from_registry"],
                "summary": plan,
            }

            self._record_audit_log(
                actor_user_id=actor_user_id,
                actor_email=actor_email,
                details=audit_details,
            )
            self.session.flush()
            self._commit()
        except Exception:
            self.session.rollback()
            raise

        return {
            "applied": True,
            "created_features": created_features,
            "updated_features": updated_features,
            "created_plan_rows": created_plan_rows,
            "orphaned_system_feature_keys": plan["db_system_features_missing_from_registry"],
            "summary": plan,
        }


__all__ = [
    "EntitlementRegistryConflict",
    "EntitlementRegistrySyncService",
]
