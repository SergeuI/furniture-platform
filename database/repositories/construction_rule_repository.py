from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session, selectinload

from database.models.construction_rule import (
    ConstructionRuleModel,
    ConstructionRuleMountingOptionModel,
    ConstructionRuleVariantModel,
)


class ConstructionRuleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_rules(self, *, include_inactive: bool = False) -> list[ConstructionRuleModel]:
        query = self.session.query(ConstructionRuleModel)
        if not include_inactive:
            query = query.filter(ConstructionRuleModel.is_active.is_(True))
        return query.order_by(
            ConstructionRuleModel.name.asc(),
            ConstructionRuleModel.code.asc(),
            ConstructionRuleModel.id.asc(),
        ).all()

    def get_rule_by_id(self, rule_id: int) -> Optional[ConstructionRuleModel]:
        return (
            self.session.query(ConstructionRuleModel)
            .options(
                selectinload(ConstructionRuleModel.variants)
                .selectinload(ConstructionRuleVariantModel.mounting_options)
                .selectinload(ConstructionRuleMountingOptionModel.mounting_scheme),
                selectinload(ConstructionRuleModel.variants)
                .selectinload(ConstructionRuleVariantModel.mounting_options)
                .selectinload(ConstructionRuleMountingOptionModel.mounting_node),
            )
            .filter(ConstructionRuleModel.id == rule_id)
            .one_or_none()
        )
