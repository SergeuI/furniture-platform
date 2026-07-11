from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from api.dependencies.auth import require_roles
from schemas.fitting_holes import (
    FittingHoleBundleCreateSchema,
    FittingHoleBundleMountingVariantUpdateSchema,
    FittingHoleBundleUpdateSchema,
    FittingHoleServiceRuleCreateSchema,
    FittingHoleServiceRuleListResponseSchema,
    FittingHoleServiceRuleOperationResponseSchema,
    FittingHoleServiceRuleUpdateSchema,
    FittingHolePointCreate,
    FittingHoleServicePreviewResponseSchema,
    FittingHolePointListResponseSchema,
    FittingHolePointOperationResponseSchema,
    FittingHolePointUpdate,
    FittingHoleBundleResponseSchema,
    FittingHoleBundleListResponseSchema,
    FittingHoleTemplateCreate,
    FittingHoleTemplateListResponseSchema,
    FittingHoleTemplateOperationResponseSchema,
    FittingHoleTemplateUpdate,
)
from database.repositories.fitting_hole_service_rule_repository import (
    create_fitting_hole_service_rule,
    deactivate_fitting_hole_service_rule,
    list_fitting_hole_service_rules,
    update_fitting_hole_service_rule,
)
from services.fitting_holes_service import FittingHolesService
from services.fitting_hole_service_preview import build_fitting_hole_service_preview


router = APIRouter()

require_fitting_holes_editor = require_roles(
    [
        "admin",
        "premium",
        "pro",
    ]
)


def _serialize_template(template) -> dict:
    fitting = getattr(template, "fitting", None)
    return {
        "id": template.id,
        "fitting_id": template.fitting_id,
        "name": template.name,
        "fitting_code": getattr(fitting, "code", None),
        "fitting_article": getattr(fitting, "article", None),
        "fitting_category_code": getattr(fitting, "fitting_type", None)
        or getattr(fitting, "fitting_group", None),
        "bundle_key": template.bundle_key,
        "bundle_name": template.bundle_name,
        "bundle_order_index": int(template.bundle_order_index or 0),
        "template_type": template.template_type,
        "side": template.side,
        "coordinate_system": template.coordinate_system,
        "mounting_variant_key": template.mounting_variant_key,
        "is_default": bool(template.is_default),
        "notes": template.notes,
        "is_active": bool(template.is_active),
    }


def _serialize_point(point) -> dict:
    return {
        "id": point.id,
        "template_id": point.template_id,
        "label": point.label,
        "x_mm": point.x_mm,
        "y_mm": point.y_mm,
        "z_mm": point.z_mm,
        "target_panel": getattr(point, "target_panel", None),
        "target_surface": getattr(point, "target_surface", None),
        "target_side": getattr(point, "target_side", None),
        "diameter_mm": point.diameter_mm,
        "service_drilling_rule_id": getattr(point, "service_drilling_rule_id", None),
        "depth_mm": point.depth_mm,
        "side": point.side,
        "operation": point.operation,
        "order_index": point.order_index,
        "quantity": point.quantity,
        "mirrored": bool(point.mirrored),
        "notes": point.notes,
    }


def _serialize_rule(rule) -> dict:
    return {
        "id": rule["id"],
        "operation": rule["operation"],
        "diameter_min_mm": rule.get("diameter_min_mm"),
        "diameter_max_mm": rule.get("diameter_max_mm"),
        "depth_min_mm": rule.get("depth_min_mm"),
        "depth_max_mm": rule.get("depth_max_mm"),
        "service_catalog_item_id": rule["service_catalog_item_id"],
        "source": rule.get("source"),
        "city": rule.get("city"),
        "is_active": bool(rule.get("is_active", True)),
        "priority": int(rule.get("priority", 0) or 0),
        "notes": rule.get("notes"),
        "created_at": rule.get("created_at"),
        "updated_at": rule.get("updated_at"),
        "service_catalog_item": rule.get("service_catalog_item"),
    }


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


@router.post(
    "/templates",
    response_model=FittingHoleTemplateOperationResponseSchema,
)
async def create_fitting_hole_template_route(
    payload: FittingHoleTemplateCreate,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        with FittingHolesService() as service:
            template = service.create_template(
                payload.model_dump(exclude_unset=True),
            )
            response = {
                "success": True,
                "template": _serialize_template(template),
            }
    except ValueError as error:
        _raise_service_error(error)

    return response


@router.get(
    "/fittings/{fitting_id}/templates",
    response_model=FittingHoleTemplateListResponseSchema,
)
async def list_fitting_hole_templates_route(
    fitting_id: int,
    current_user = Depends(require_fitting_holes_editor),
):
    with FittingHolesService() as service:
        fitting = service.get_fitting(fitting_id)
        if not fitting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fitting with id={fitting_id} does not exist",
            )

        templates = service.list_templates_for_fitting(fitting_id)
        serialized_templates = [
            _serialize_template(template)
            for template in templates
        ]

    return {
        "success": True,
        "fitting_id": fitting_id,
        "templates": serialized_templates,
    }


@router.get(
    "/bundles",
    response_model=FittingHoleBundleListResponseSchema,
)
async def list_fitting_hole_bundles_route(
    current_user = Depends(require_fitting_holes_editor),
):
    with FittingHolesService() as service:
        bundles = service.list_bundles()

    return {
        "success": True,
        "bundles": [
            {
                "bundle_key": bundle_key,
                "bundle_name": bundle_name,
                "category_code": category_code,
                "template_count": int(template_count or 0),
                "created_at": created_at,
                "updated_at": updated_at,
            }
            for bundle_key, bundle_name, category_code, template_count, created_at, updated_at in bundles
        ],
    }


@router.get(
    "/bundles/{bundle_key}",
    response_model=FittingHoleBundleResponseSchema,
)
async def list_fitting_hole_bundle_route(
    bundle_key: str,
    current_user = Depends(require_fitting_holes_editor),
):
    with FittingHolesService() as service:
        templates = service.list_templates_for_bundle(bundle_key)
        serialized_templates = [
            _serialize_template(template)
            for template in templates
        ]

    if not templates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bundle with key={bundle_key} does not exist",
        )

    first_template = templates[0]

    return {
        "success": True,
        "bundle_key": bundle_key,
        "bundle_name": first_template.bundle_name,
        "category_code": serialized_templates[0].get("fitting_category_code")
        if serialized_templates
        else None,
        "mounting_variant_key": serialized_templates[0].get("mounting_variant_key")
        if serialized_templates
        else None,
        "templates": serialized_templates,
    }


@router.post(
    "/bundles",
    response_model=FittingHoleBundleResponseSchema,
)
async def create_fitting_hole_bundle_route(
    payload: FittingHoleBundleCreateSchema,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        with FittingHolesService() as service:
            result = service.create_bundle(
                payload.model_dump(exclude_unset=True),
            )
            serialized_templates = [
                _serialize_template(template)
                for template in result["templates"]
            ]
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        "bundle_key": result["bundle_key"],
        "bundle_name": result["bundle_name"],
        "category_code": result.get("category_code"),
        "mounting_variant_key": result.get("mounting_variant_key"),
        "templates": serialized_templates,
    }


@router.patch(
    "/bundles/{bundle_key}",
    response_model=FittingHoleBundleResponseSchema,
)
async def update_fitting_hole_bundle_route(
    bundle_key: str,
    payload: FittingHoleBundleUpdateSchema,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        with FittingHolesService() as service:
            result = service.update_bundle_name(
                bundle_key,
                payload.bundle_name,
            )
            serialized_templates = [
                _serialize_template(template)
                for template in result["templates"]
            ]
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        "bundle_key": result["bundle_key"],
        "bundle_name": result["bundle_name"],
        "category_code": result.get("category_code"),
        "mounting_variant_key": result.get("mounting_variant_key"),
        "templates": serialized_templates,
    }


@router.delete(
    "/bundles/{bundle_key}",
    response_model=FittingHoleBundleResponseSchema,
)
async def delete_fitting_hole_bundle_route(
    bundle_key: str,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        with FittingHolesService() as service:
            service.delete_bundle(bundle_key)
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        "bundle_key": bundle_key,
        "bundle_name": None,
        "category_code": None,
        "mounting_variant_key": None,
        "templates": [],
    }


@router.patch(
    "/bundles/{bundle_key}/mounting-variant",
    response_model=FittingHoleBundleResponseSchema,
)
async def update_fitting_hole_bundle_mounting_variant_route(
    bundle_key: str,
    payload: FittingHoleBundleMountingVariantUpdateSchema,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        with FittingHolesService() as service:
            result = service.update_bundle_mounting_variant(
                bundle_key,
                payload.mounting_variant_key,
            )
            serialized_templates = [
                _serialize_template(template)
                for template in result["templates"]
            ]
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        "bundle_key": result["bundle_key"],
        "bundle_name": result["bundle_name"],
        "category_code": result.get("category_code"),
        "mounting_variant_key": result.get("mounting_variant_key"),
        "templates": serialized_templates,
    }


@router.get(
    "/templates/{template_id}",
    response_model=FittingHoleTemplateOperationResponseSchema,
)
async def get_fitting_hole_template_route(
    template_id: int,
    current_user = Depends(require_fitting_holes_editor),
):
    with FittingHolesService() as service:
        template = service.get_template(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id={template_id} does not exist",
        )

    return {
        "success": True,
        "template": _serialize_template(template),
    }


@router.patch(
    "/templates/{template_id}",
    response_model=FittingHoleTemplateOperationResponseSchema,
)
async def update_fitting_hole_template_route(
    template_id: int,
    payload: FittingHoleTemplateUpdate,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        with FittingHolesService() as service:
            template = service.update_template(
                template_id,
                payload.model_dump(exclude_unset=True),
            )
    except ValueError as error:
        _raise_service_error(error)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id={template_id} does not exist",
        )

    return {
        "success": True,
        "template": _serialize_template(template),
    }


@router.delete(
    "/templates/{template_id}",
    response_model=FittingHoleTemplateOperationResponseSchema,
)
async def delete_fitting_hole_template_route(
    template_id: int,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        with FittingHolesService() as service:
            template = service.deactivate_template(template_id)
    except ValueError as error:
        _raise_service_error(error)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id={template_id} does not exist",
        )

    return {
        "success": True,
        "template": _serialize_template(template),
    }


@router.post(
    "/templates/{template_id}/points",
    response_model=FittingHolePointOperationResponseSchema,
)
async def create_fitting_hole_point_route(
    template_id: int,
    payload: FittingHolePointCreate,
    current_user = Depends(require_fitting_holes_editor),
):
    body = payload.model_dump(exclude_unset=True)
    body["template_id"] = template_id

    try:
        with FittingHolesService() as service:
            point = service.add_hole_point(body)
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        "point": _serialize_point(point),
    }


@router.get(
    "/templates/{template_id}/points",
    response_model=FittingHolePointListResponseSchema,
)
async def list_fitting_hole_points_route(
    template_id: int,
    current_user = Depends(require_fitting_holes_editor),
):
    with FittingHolesService() as service:
        template = service.get_template(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with id={template_id} does not exist",
            )

        points = service.list_hole_points(template_id)

    return {
        "success": True,
        "template_id": template_id,
        "points": [
            _serialize_point(point)
            for point in points
        ],
    }


@router.get(
    "/templates/{template_id}/service-preview",
    response_model=FittingHoleServicePreviewResponseSchema,
)
async def get_fitting_hole_service_preview_route(
    template_id: int,
    current_user = Depends(require_fitting_holes_editor),
):
    with FittingHolesService() as service:
        template = service.get_template(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template with id={template_id} does not exist",
            )

        points = service.list_hole_points(template_id)

    preview = build_fitting_hole_service_preview(
        template,
        points,
        current_user_id=getattr(current_user, "id", None),
    )

    return {
        "success": True,
        **preview,
    }


@router.get(
    "/service-rules",
    response_model=FittingHoleServiceRuleListResponseSchema,
)
async def list_fitting_hole_service_rules_route(
    current_user = Depends(require_fitting_holes_editor),
):
    rules = list_fitting_hole_service_rules(user_id=getattr(current_user, "id", None))
    return {
        "success": True,
        "rules": [
            _serialize_rule(rule)
            for rule in rules
        ],
    }


@router.post(
    "/service-rules",
    response_model=FittingHoleServiceRuleOperationResponseSchema,
)
async def create_fitting_hole_service_rule_route(
    payload: FittingHoleServiceRuleCreateSchema,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        rule = create_fitting_hole_service_rule(
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        "rule": _serialize_rule(rule),
    }


@router.patch(
    "/service-rules/{rule_id}",
    response_model=FittingHoleServiceRuleOperationResponseSchema,
)
async def update_fitting_hole_service_rule_route(
    rule_id: int,
    payload: FittingHoleServiceRuleUpdateSchema,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        rule = update_fitting_hole_service_rule(
            rule_id,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as error:
        _raise_service_error(error)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service rule with id={rule_id} does not exist",
        )

    return {
        "success": True,
        "rule": _serialize_rule(rule),
    }


@router.delete(
    "/service-rules/{rule_id}",
    response_model=FittingHoleServiceRuleOperationResponseSchema,
)
async def delete_fitting_hole_service_rule_route(
    rule_id: int,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        rule = deactivate_fitting_hole_service_rule(rule_id)
    except ValueError as error:
        _raise_service_error(error)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service rule with id={rule_id} does not exist",
        )

    return {
        "success": True,
        "rule": _serialize_rule(rule),
    }


@router.patch(
    "/points/{point_id}",
    response_model=FittingHolePointOperationResponseSchema,
)
async def update_fitting_hole_point_route(
    point_id: int,
    payload: FittingHolePointUpdate,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        with FittingHolesService() as service:
            point = service.update_hole_point(
                point_id,
                payload.model_dump(exclude_unset=True),
            )
    except ValueError as error:
        _raise_service_error(error)

    if not point:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Point with id={point_id} does not exist",
        )

    return {
        "success": True,
        "point": _serialize_point(point),
    }


@router.delete(
    "/points/{point_id}",
    response_model=FittingHolePointOperationResponseSchema,
)
async def delete_fitting_hole_point_route(
    point_id: int,
    current_user = Depends(require_fitting_holes_editor),
):
    try:
        with FittingHolesService() as service:
            deleted = service.delete_hole_point(point_id)
    except ValueError as error:
        _raise_service_error(error)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Point with id={point_id} does not exist",
        )

    return {
        "success": True,
        "point": None,
    }
