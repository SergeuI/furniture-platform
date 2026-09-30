from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from database.models.construction_rule import (
    ConstructionRuleModel,
    ConstructionRuleMountingOptionModel,
    ConstructionRuleVariantModel,
)
from database.session import SessionLocal
from database.repositories.construction_rule_repository import ConstructionRuleRepository


class ConstructionRuleService:
    def __init__(self, session: Optional[Session] = None, repository: Optional[ConstructionRuleRepository] = None) -> None:
        if repository is not None and session is None:
            session = repository.session
        self.session = session or SessionLocal()
        self._owns_session = session is None and repository is None
        self.repository = repository or ConstructionRuleRepository(self.session)

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def __enter__(self) -> "ConstructionRuleService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def _serialize_node(node) -> dict:
        return {
            "id": node.id,
            "code": node.code,
            "name": node.name,
            "fastening_type": node.fastening_type,
            "is_active": bool(node.is_active),
        }

    @staticmethod
    def _serialize_scheme(scheme) -> dict:
        return {
            "id": scheme.id,
            "code": scheme.code,
            "name": scheme.name,
            "description": scheme.description,
            "is_active": bool(scheme.is_active),
        }

    def _serialize_option(self, option: ConstructionRuleMountingOptionModel) -> dict:
        return {
            "id": option.id,
            "is_preferred": bool(option.is_preferred),
            "is_active": bool(option.is_active),
            "order_index": int(option.order_index or 0),
            "mounting_scheme": self._serialize_scheme(option.mounting_scheme) if option.mounting_scheme else None,
            "mounting_node": self._serialize_node(option.mounting_node) if option.mounting_node else None,
        }

    def _serialize_variant(self, variant: ConstructionRuleVariantModel) -> dict:
        options = sorted(
            variant.mounting_options,
            key=lambda option: (int(option.order_index or 0), int(option.id or 0)),
        )
        return {
            "id": variant.id,
            "code": variant.code,
            "name": variant.name,
            "parameters": variant.parameters_json,
            "is_default": bool(variant.is_default),
            "is_active": bool(variant.is_active),
            "order_index": int(variant.order_index or 0),
            "mounting_options": [self._serialize_option(option) for option in options],
        }

    @staticmethod
    def _serialize_rule_summary(rule: ConstructionRuleModel) -> dict:
        return {
            "id": rule.id,
            "code": rule.code,
            "name": rule.name,
            "description": rule.description,
            "primary_part_role": rule.primary_part_role,
            "secondary_part_role": rule.secondary_part_role,
            "connection_type": rule.connection_type,
            "is_active": bool(rule.is_active),
            "created_at": rule.created_at,
            "updated_at": rule.updated_at,
        }

    def list_construction_rules(self, *, include_inactive: bool = False) -> list[dict]:
        return [self._serialize_rule_summary(rule) for rule in self.repository.list_rules(include_inactive=include_inactive)]

    def get_construction_rule(self, rule_id: int) -> dict | None:
        rule = self.repository.get_rule_by_id(int(rule_id))
        if rule is None:
            return None
        payload = self._serialize_rule_summary(rule)
        payload["variants"] = [
            self._serialize_variant(variant)
            for variant in sorted(rule.variants, key=lambda item: (int(item.order_index or 0), int(item.id or 0)))
        ]
        return payload
