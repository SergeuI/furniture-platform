from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.auth import (
    require_current_user,
    require_roles,
)
from schemas.mounting_nodes import (
    MountingNodeCreateSchema,
    MountingNodeDetailResponseSchema,
    MountingNodeListResponseSchema,
    MountingNodeOperationResponseSchema,
    MountingNodeUpdateSchema,
)
from services.entitlement_service import EntitlementService
from services.mounting_node_service import MountingNodeService


router = APIRouter()

require_mounting_nodes_admin = require_roles(["admin"])


def require_mounting_nodes_use(current_user = Depends(require_current_user)):
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


def _raise_service_permission_error(error: PermissionError) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "success": False,
            "error": "Insufficient permissions",
        },
    ) from error


@router.get(
    "",
    response_model=MountingNodeListResponseSchema,
)
async def list_mounting_nodes_route(
    include_inactive: bool = Query(default=False),
    fitting_id: int | None = Query(default=None),
    mounting_variant_key: str | None = Query(default=None),
    search: str | None = Query(default=None),
    current_user = Depends(require_mounting_nodes_use),
):
    with MountingNodeService() as service:
        nodes = service.list_mounting_nodes(
            include_inactive=include_inactive,
            fitting_id=fitting_id,
            mounting_variant_key=mounting_variant_key,
            search=search,
            viewer_user_id=getattr(current_user, "id", None),
            viewer_role=getattr(current_user, "role", None),
        )

    return {
        "success": True,
        "nodes": nodes,
    }


@router.get(
    "/{node_id}",
    response_model=MountingNodeDetailResponseSchema,
)
async def get_mounting_node_route(
    node_id: int,
    current_user = Depends(require_mounting_nodes_use),
):
    with MountingNodeService() as service:
        node = service.get_mounting_node(
            node_id,
            viewer_user_id=getattr(current_user, "id", None),
            viewer_role=getattr(current_user, "role", None),
        )

    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mounting node with id={node_id} does not exist",
        )

    return {
        "success": True,
        "node": node,
    }


@router.post(
    "",
    response_model=MountingNodeOperationResponseSchema,
)
async def create_mounting_node_route(
    payload: MountingNodeCreateSchema,
    current_user = Depends(require_mounting_nodes_use),
):
    try:
        with MountingNodeService() as service:
            node = service.create_mounting_node(
                payload.model_dump(exclude_unset=True),
                viewer_user_id=getattr(current_user, "id", None),
                viewer_role=getattr(current_user, "role", None),
            )
    except ValueError as error:
        _raise_service_error(error)
    except PermissionError as error:
        _raise_service_permission_error(error)

    return {
        "success": True,
        "node": node,
    }


@router.patch(
    "/{node_id}",
    response_model=MountingNodeOperationResponseSchema,
)
async def update_mounting_node_route(
    node_id: int,
    payload: MountingNodeUpdateSchema,
    current_user = Depends(require_mounting_nodes_use),
):
    try:
        with MountingNodeService() as service:
            node = service.update_mounting_node(
                node_id,
                payload.model_dump(exclude_unset=True),
                viewer_user_id=getattr(current_user, "id", None),
                viewer_role=getattr(current_user, "role", None),
            )
    except ValueError as error:
        _raise_service_error(error)
    except PermissionError as error:
        _raise_service_permission_error(error)

    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mounting node with id={node_id} does not exist",
        )

    return {
        "success": True,
        "node": node,
    }


@router.delete(
    "/{node_id}",
    response_model=MountingNodeOperationResponseSchema,
)
async def delete_mounting_node_route(
    node_id: int,
    current_user = Depends(require_mounting_nodes_use),
):
    try:
        with MountingNodeService() as service:
            deleted = service.delete_mounting_node(
                node_id,
                viewer_user_id=getattr(current_user, "id", None),
                viewer_role=getattr(current_user, "role", None),
            )
    except ValueError as error:
        _raise_service_error(error)
    except PermissionError as error:
        _raise_service_permission_error(error)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mounting node with id={node_id} does not exist",
        )

    return {
        "success": True,
        "node": None,
    }
