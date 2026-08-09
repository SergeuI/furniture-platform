from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.auth import require_current_user
from schemas.mounting_schemes import (
    MountingSchemeCreateSchema,
    MountingSchemeDetailResponseSchema,
    MountingSchemeListResponseSchema,
    MountingSchemeOperationResponseSchema,
    MountingSchemeUpdateSchema,
)
from services.mounting_scheme_service import MountingSchemeService


router = APIRouter()


def _raise_service_error(error: ValueError) -> None:
    detail = str(error)
    lowered = detail.lower()
    if "does not exist" in lowered or "not found" in lowered:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from error
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from error


@router.get("", response_model=MountingSchemeListResponseSchema)
async def list_mounting_schemes_route(
    include_inactive: bool = Query(default=False),
    current_user = Depends(require_current_user),
):
    del current_user
    with MountingSchemeService() as service:
        schemes = service.list_mounting_schemes(include_inactive=include_inactive)

    return {
        "success": True,
        "schemes": schemes,
    }


@router.get("/{scheme_id}", response_model=MountingSchemeDetailResponseSchema)
async def get_mounting_scheme_route(
    scheme_id: int,
    current_user = Depends(require_current_user),
):
    del current_user
    with MountingSchemeService() as service:
        scheme = service.get_mounting_scheme(scheme_id)

    if scheme is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mounting scheme with id={scheme_id} does not exist",
        )

    return {
        "success": True,
        "scheme": scheme,
    }


@router.post("", response_model=MountingSchemeOperationResponseSchema)
async def create_mounting_scheme_route(
    payload: MountingSchemeCreateSchema,
    current_user = Depends(require_current_user),
):
    del current_user
    try:
        with MountingSchemeService() as service:
            scheme = service.create_mounting_scheme(payload.model_dump(exclude_unset=True))
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        "scheme": scheme,
    }


@router.patch("/{scheme_id}", response_model=MountingSchemeOperationResponseSchema)
async def update_mounting_scheme_route(
    scheme_id: int,
    payload: MountingSchemeUpdateSchema,
    current_user = Depends(require_current_user),
):
    del current_user
    try:
        with MountingSchemeService() as service:
            scheme = service.update_mounting_scheme(scheme_id, payload.model_dump(exclude_unset=True))
    except ValueError as error:
        _raise_service_error(error)

    if scheme is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mounting scheme with id={scheme_id} does not exist",
        )

    return {
        "success": True,
        "scheme": scheme,
    }
