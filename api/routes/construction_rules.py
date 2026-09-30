from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.auth import require_current_user
from schemas.construction_rules import (
    ConstructionRuleDetailResponseSchema,
    ConstructionRuleListResponseSchema,
)
from services.construction_rule_service import ConstructionRuleService


router = APIRouter()


@router.get("", response_model=ConstructionRuleListResponseSchema)
async def list_construction_rules_route(
    include_inactive: bool = Query(default=False),
    current_user=Depends(require_current_user),
):
    del current_user
    with ConstructionRuleService() as service:
        rules = service.list_construction_rules(include_inactive=include_inactive)
    return {"success": True, "rules": rules}


@router.get("/{rule_id}", response_model=ConstructionRuleDetailResponseSchema)
async def get_construction_rule_route(
    rule_id: int,
    current_user=Depends(require_current_user),
):
    del current_user
    with ConstructionRuleService() as service:
        rule = service.get_construction_rule(rule_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Construction rule with id={rule_id} does not exist",
        )
    return {"success": True, "rule": rule}
