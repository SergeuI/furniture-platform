from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies.auth import require_current_user
from database.repositories.project_repository import get_project
from schemas.processing_operation_types import ProcessingOperationTypeListResponseSchema
from schemas.processing_operations import ProcessingProjectPartOperationPreviewResponseSchema
from services.entitlement_service import EntitlementService
from services.project_part_detail_service import build_project_part_detail
from services.project_processing_operation_adapter import ProjectProcessingOperationAdapter
from services.processing_operation_registry import list_processing_operation_types
from services.user_roles import normalize_user_role


router = APIRouter()


def _ensure_project_feature_access(current_user, feature_key: str) -> None:
    with EntitlementService() as service:
        if service.has_feature(current_user, feature_key):
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "success": False,
            "error": "Insufficient permissions",
        },
    )


def _can_read_project(current_user, project) -> bool:
    current_role = normalize_user_role(current_user.role)

    if current_role == "admin":
        return True

    if current_role in ("free", "premium", "pro"):
        return (
            project.created_by_user_id == current_user.id
            or project.created_by_user_id is None
        )

    return False


def require_processing_project_view_access(
    current_user = Depends(require_current_user),
):
    _ensure_project_feature_access(current_user, "projects.view")
    return current_user


def require_processing_operation_types_use(current_user = Depends(require_current_user)):
    if getattr(current_user, "role", None) == "admin":
        return current_user

    with EntitlementService() as service:
        if service.has_feature(current_user, "fitting_holes.use"):
            return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "success": False,
            "error": "Insufficient permissions",
        },
    )


@router.get(
    "/operation-types",
    response_model=ProcessingOperationTypeListResponseSchema,
)
async def get_processing_operation_types_route(
    current_user = Depends(require_processing_operation_types_use),
):
    items = list_processing_operation_types()
    return {
        "success": True,
        "items": items,
        "count": len(items),
    }


@router.get(
    "/projects/{project_id}/parts/{part_identifier}/operations-preview",
    response_model=ProcessingProjectPartOperationPreviewResponseSchema,
)
async def get_processing_project_part_operations_preview_route(
    project_id: str,
    part_identifier: str,
    current_user = Depends(require_processing_project_view_access),
):
    project = get_project(project_id)

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not _can_read_project(current_user, project):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    part_detail = build_project_part_detail(project, part_identifier)

    if not part_detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Part not found",
        )

    operations = ProjectProcessingOperationAdapter().build_operations(
        project_id=project_id,
        part_identifier=part_identifier,
        part_detail=part_detail,
    )

    return {
        "success": True,
        "project": {
            "id": project_id,
        },
        "part": part_detail["part"],
        "operations": operations,
        "count": len(operations),
    }
