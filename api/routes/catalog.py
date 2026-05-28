from fastapi import (
    APIRouter,
    Depends,
    Query
)

from api.dependencies.auth import (
    require_roles
)

from schemas.catalog import (
    CatalogItemActiveSchema,
    CatalogItemCreateSchema,
    CatalogItemListResponseSchema,
    CatalogItemOperationResponseSchema,
    CatalogItemUpdateSchema,
    SpecificationCatalogResponseSchema
)
from database.repositories.catalog_repository import (
    ALLOWED_CATALOG_CATEGORIES,
    create_catalog_item,
    get_specification_catalog,
    list_catalog_items,
    set_catalog_item_active,
    update_catalog_item
)
from database.repositories.audit_log_repository import (
    create_audit_log
)

router = APIRouter()

require_catalog_admin = require_roles(
    [
        "admin"
    ]
)


def _serialize_catalog_item(

    item
) -> dict:

    return {
        "id": item.id,
        "category": item.category,
        "value": item.value,
        "sort_order": item.sort_order,
        "is_active": item.is_active
    }


@router.get(
    "/specification",
    response_model=SpecificationCatalogResponseSchema
)
async def get_specification_catalog_route():
    catalog = get_specification_catalog()

    return {
        "success": True,
        **catalog
    }


@router.get(
    "/items",
    response_model=CatalogItemListResponseSchema
)
async def list_catalog_items_route(

    include_inactive: bool = Query(
        default=True
    ),

    current_user = Depends(require_catalog_admin)
):

    items = list_catalog_items(
        include_inactive=include_inactive
    )

    return {
        "success": True,
        "items": [
            _serialize_catalog_item(item)
            for item in items
        ]
    }


@router.post(
    "/items",
    response_model=CatalogItemOperationResponseSchema
)
async def create_catalog_item_route(

    payload: CatalogItemCreateSchema,

    current_user = Depends(require_catalog_admin)
):

    category = payload.category.strip().lower()

    value = payload.value.strip()

    if category not in ALLOWED_CATALOG_CATEGORIES:

        return {
            "success": False,
            "error": "Invalid catalog category"
        }

    item = create_catalog_item(
        category=category,
        value=value,
        sort_order=payload.sort_order
    )

    if not item:

        return {
            "success": False,
            "error": "Catalog item already exists"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="catalog.item_created",

        entity_type="catalog_item",

        entity_id=item.id,

        details=_serialize_catalog_item(item)
    )

    return {
        "success": True,
        "item": _serialize_catalog_item(item)
    }


@router.put(
    "/items/{item_id}",
    response_model=CatalogItemOperationResponseSchema
)
async def update_catalog_item_route(

    item_id: str,

    payload: CatalogItemUpdateSchema,

    current_user = Depends(require_catalog_admin)
):

    item = update_catalog_item(
        item_id=item_id,
        value=payload.value.strip(),
        sort_order=payload.sort_order
    )

    if not item:

        return {
            "success": False,
            "error": "Catalog item not found"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="catalog.item_updated",

        entity_type="catalog_item",

        entity_id=item.id,

        details=_serialize_catalog_item(item)
    )

    return {
        "success": True,
        "item": _serialize_catalog_item(item)
    }


@router.put(
    "/items/{item_id}/active",
    response_model=CatalogItemOperationResponseSchema
)
async def update_catalog_item_active_route(

    item_id: str,

    payload: CatalogItemActiveSchema,

    current_user = Depends(require_catalog_admin)
):

    item = set_catalog_item_active(
        item_id=item_id,
        is_active=payload.is_active
    )

    if not item:

        return {
            "success": False,
            "error": "Catalog item not found"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="catalog.item_active_updated",

        entity_type="catalog_item",

        entity_id=item.id,

        details=_serialize_catalog_item(item)
    )

    return {
        "success": True,
        "item": _serialize_catalog_item(item)
    }
