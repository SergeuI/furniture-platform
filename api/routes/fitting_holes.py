from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from api.dependencies.auth import require_roles
from schemas.fitting_holes import (
    FittingHolePointCreate,
    FittingHolePointListResponseSchema,
    FittingHolePointOperationResponseSchema,
    FittingHolePointUpdate,
    FittingHoleTemplateCreate,
    FittingHoleTemplateListResponseSchema,
    FittingHoleTemplateOperationResponseSchema,
    FittingHoleTemplateUpdate,
)
from services.fitting_holes_service import FittingHolesService


router = APIRouter()

require_fitting_holes_editor = require_roles(
    [
        "admin",
        "premium",
        "pro",
    ]
)


def _serialize_template(template) -> dict:
    return {
        "id": template.id,
        "fitting_id": template.fitting_id,
        "name": template.name,
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
        "diameter_mm": point.diameter_mm,
        "depth_mm": point.depth_mm,
        "side": point.side,
        "operation": point.operation,
        "order_index": point.order_index,
        "quantity": point.quantity,
        "mirrored": bool(point.mirrored),
        "notes": point.notes,
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
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        "template": _serialize_template(template),
    }


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

    return {
        "success": True,
        "fitting_id": fitting_id,
        "templates": [
            _serialize_template(template)
            for template in templates
        ],
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
