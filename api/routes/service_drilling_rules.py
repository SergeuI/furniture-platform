from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.auth import require_roles
from database.repositories.service_drilling_rule_repository import (
    create_service_drilling_rule,
    deactivate_service_drilling_rule,
    get_service_drilling_rule,
    list_available_viyar_drilling_services,
    list_service_drilling_rules,
    update_service_drilling_rule,
)
from schemas.service_drilling_rules import (
    ServiceDrillingAvailableServicesResponseSchema,
    ServiceDrillingRuleCreateSchema,
    ServiceDrillingRuleListResponseSchema,
    ServiceDrillingRuleOperationResponseSchema,
    ServiceDrillingRuleUpdateSchema,
)


router = APIRouter()

require_service_drilling_rules_editor = require_roles(["admin"])


def _raise_service_error(error: ValueError) -> None:
    detail = str(error)
    lowered = detail.lower()

    if "does not exist" in lowered or "not found" in lowered:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        ) from error

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    ) from error


@router.get(
    "",
    response_model=ServiceDrillingRuleListResponseSchema,
)
async def list_service_drilling_rules_route(
    include_inactive: bool = Query(default=False),
    service_catalog_item_id: str | None = Query(default=None),
    current_user = Depends(require_service_drilling_rules_editor),
):
    return {
        "success": True,
        "rules": list_service_drilling_rules(
            include_inactive=include_inactive,
            service_catalog_item_id=service_catalog_item_id,
        ),
    }


@router.get(
    "/available-services",
    response_model=ServiceDrillingAvailableServicesResponseSchema,
)
async def list_available_viyar_drilling_services_route(
    category: str = Query(default="drilling"),
    search: str | None = Query(default=None),
    current_user = Depends(require_service_drilling_rules_editor),
):
    return {
        "success": True,
        "category": category,
        "items": list_available_viyar_drilling_services(
            category=category,
            search=search,
        ),
    }


@router.get(
    "/{rule_id}",
    response_model=ServiceDrillingRuleOperationResponseSchema,
)
async def get_service_drilling_rule_route(
    rule_id: int,
    current_user = Depends(require_service_drilling_rules_editor),
):
    rule = get_service_drilling_rule(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service drilling rule with id={rule_id} does not exist",
        )
    return {
        "success": True,
        "rule": rule,
    }


@router.post(
    "",
    response_model=ServiceDrillingRuleOperationResponseSchema,
)
async def create_service_drilling_rule_route(
    payload: ServiceDrillingRuleCreateSchema,
    current_user = Depends(require_service_drilling_rules_editor),
):
    try:
        rule = create_service_drilling_rule(
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        "rule": rule,
    }


@router.patch(
    "/{rule_id}",
    response_model=ServiceDrillingRuleOperationResponseSchema,
)
async def update_service_drilling_rule_route(
    rule_id: int,
    payload: ServiceDrillingRuleUpdateSchema,
    current_user = Depends(require_service_drilling_rules_editor),
):
    try:
        rule = update_service_drilling_rule(
            rule_id,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as error:
        _raise_service_error(error)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service drilling rule with id={rule_id} does not exist",
        )

    return {
        "success": True,
        "rule": rule,
    }


@router.delete(
    "/{rule_id}",
    response_model=ServiceDrillingRuleOperationResponseSchema,
)
async def delete_service_drilling_rule_route(
    rule_id: int,
    current_user = Depends(require_service_drilling_rules_editor),
):
    try:
        rule = deactivate_service_drilling_rule(rule_id)
    except ValueError as error:
        _raise_service_error(error)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service drilling rule with id={rule_id} does not exist",
        )

    return {
        "success": True,
        "rule": rule,
    }
