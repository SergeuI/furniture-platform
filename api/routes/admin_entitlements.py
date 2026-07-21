from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from api.dependencies.auth import require_roles
from database.session import SessionLocal
from schemas.entitlements import (
    EntitlementRegistrySyncApplyResponse,
    EntitlementRegistrySyncPreviewResponse,
    FeatureCreateRequest,
    FeatureListResponse,
    FeatureOperationResponse,
    FeatureUpdateRequest,
    MatrixResponse,
    MatrixUpdateRequest,
    MatrixUpdateResponse,
)
from services.admin_entitlement_service import AdminEntitlementService
from services.entitlement_registry_sync_service import EntitlementRegistrySyncService


router = APIRouter()

require_admin_entitlements = require_roles(["admin"])


def get_admin_entitlement_service() -> Iterator[AdminEntitlementService]:
    session = SessionLocal()
    service = AdminEntitlementService(session=session)
    try:
        yield service
    finally:
        service.close()
        session.close()


def _raise_service_error(error: ValueError) -> None:
    detail = str(error)
    lowered = detail.lower()

    if "не знайден" in lowered or "not found" in lowered:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "error": detail},
        ) from error

    if "вже існує" in lowered or "дублікат" in lowered or "duplicate" in lowered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"success": False, "error": detail},
        ) from error

    if "registry sync has conflicts" in lowered or ("registry sync" in lowered and "conflict" in lowered):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"success": False, "error": detail},
        ) from error

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"success": False, "error": detail},
    ) from error


@router.get(
    "/features",
    response_model=FeatureListResponse,
)
async def list_features_route(
    active_only: bool = False,
    current_user = Depends(require_admin_entitlements),
    service: AdminEntitlementService = Depends(get_admin_entitlement_service),
):
    return {
        "success": True,
        "features": service.list_features(active_only=active_only),
    }


@router.post(
    "/features",
    response_model=FeatureOperationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_feature_route(
    payload: FeatureCreateRequest,
    current_user = Depends(require_admin_entitlements),
    service: AdminEntitlementService = Depends(get_admin_entitlement_service),
):
    try:
        result = service.create_feature(
            payload.model_dump(),
            actor_user_id=str(current_user.id),
            actor_email=current_user.email,
        )
    except ValueError as error:
        _raise_service_error(error)
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"success": False, "error": "Фіча з таким feature_key вже існує"},
        ) from error

    return {
        "success": True,
        **result,
    }


@router.patch(
    "/features/{feature_id}",
    response_model=FeatureOperationResponse,
)
async def update_feature_route(
    feature_id: int,
    payload: FeatureUpdateRequest,
    current_user = Depends(require_admin_entitlements),
    service: AdminEntitlementService = Depends(get_admin_entitlement_service),
):
    try:
        result = service.update_feature(
            feature_id,
            payload.model_dump(exclude_unset=True),
            actor_user_id=str(current_user.id),
            actor_email=current_user.email,
        )
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        **result,
    }


@router.get(
    "/matrix",
    response_model=MatrixResponse,
)
async def get_matrix_route(
    current_user = Depends(require_admin_entitlements),
    service: AdminEntitlementService = Depends(get_admin_entitlement_service),
):
    return {
        "success": True,
        **service.get_matrix(),
    }


@router.put(
    "/matrix",
    response_model=MatrixUpdateResponse,
)
async def update_matrix_route(
    payload: MatrixUpdateRequest,
    current_user = Depends(require_admin_entitlements),
    service: AdminEntitlementService = Depends(get_admin_entitlement_service),
):
    try:
        result = service.update_matrix(
            payload.rows,
            actor_user_id=str(current_user.id),
            actor_email=current_user.email,
        )
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        **result,
    }


@router.get(
    "/registry-sync/preview",
    response_model=EntitlementRegistrySyncPreviewResponse,
)
async def preview_registry_sync_route(
    current_user = Depends(require_admin_entitlements),
    service: AdminEntitlementService = Depends(get_admin_entitlement_service),
):
    sync_service = EntitlementRegistrySyncService(session=service.session)
    plan = sync_service.plan_sync()
    return {
        "success": True,
        "can_apply": not bool(plan["conflicts"]),
        **plan,
        "summary": plan,
    }


@router.post(
    "/registry-sync/apply",
    response_model=EntitlementRegistrySyncApplyResponse,
)
async def apply_registry_sync_route(
    current_user = Depends(require_admin_entitlements),
    service: AdminEntitlementService = Depends(get_admin_entitlement_service),
):
    sync_service = EntitlementRegistrySyncService(session=service.session)
    try:
        result = sync_service.apply_sync(
            actor_user_id=str(current_user.id),
            actor_email=current_user.email,
            source="admin-api",
        )
    except ValueError as error:
        _raise_service_error(error)

    return {
        "success": True,
        **result,
    }
