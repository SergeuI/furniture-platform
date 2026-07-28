from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies.auth import require_current_user
from schemas.processing_operation_types import ProcessingOperationTypeListResponseSchema
from services.entitlement_service import EntitlementService
from services.processing_operation_registry import list_processing_operation_types


router = APIRouter()


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
