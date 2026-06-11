from fastapi import (
    APIRouter,
    Depends,
    Query,
)

from api.dependencies.auth import (
    require_current_user,
    require_roles
)

from schemas.catalog import (
    CatalogItemActiveSchema,
    CatalogItemCreateSchema,
    CatalogItemListResponseSchema,
    CatalogItemOperationResponseSchema,
    FittingCatalogListResponseSchema,
    CatalogItemUpdateSchema,
    ManualServiceCatalogItemCreateSchema,
    ManualServiceCatalogItemUpdateSchema,
    MaterialCatalogOperationResponseSchema,
    MaterialCatalogListResponseSchema,
    MaterialImportFromViyarSchema,
    ServiceCatalogItemUpdateSchema,
    ServiceCatalogOperationResponseSchema,
    ServiceCatalogPriceSyncResponseSchema,
    ServiceCatalogSyncResponseSchema,
    ServiceCatalogTreeResponseSchema,
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
from database.repositories.service_catalog_repository import (
    create_manual_service_catalog_item,
    list_service_catalog_tree,
    sync_viyar_service_catalog,
    sync_viyar_service_prices,
    update_manual_service_catalog_item,
    update_service_catalog_item,
)
from database.repositories.inventory_repository import (
    delete_material,
    list_fittings,
    list_inventory_cities,
    list_material_categories,
    list_materials,
)
from database.repositories.material_import_job_repository import (
    get_material_import_job,
)
from database.repositories.audit_log_repository import (
    create_audit_log
)
from database.repositories.user_repository import (
    update_user_viyar_session,
)
from services.credential_cipher import (
    decrypt_secret,
)
from services.viyar_auth_service import (
    login_viyar_and_get_cookie,
)
from services.material_import_queue_service import (
    enqueue_material_import_job,
    get_material_import_job_result,
)

router = APIRouter()

require_catalog_admin = require_roles(
    [
        "admin"
    ]
)

require_catalog_reader = require_roles(
    [
        "admin",
        "pro",
        "user",
        "guest",
    ]
)

require_manual_service_editor = require_roles(
    [
        "admin",
        "pro",
        "user",
    ]
)

require_material_editor = require_roles(
    [
        "admin",
        "pro",
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
    "/materials",
    response_model=MaterialCatalogListResponseSchema,
)
async def list_materials_route(

    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    city: str | None = Query(default=None),
    current_user = Depends(require_catalog_reader)
):

    selected_city = city or current_user.city

    return {
        "success": True,
        "categories": list_material_categories(),
        "city_options": list_inventory_cities(),
        "selected_city": selected_city,
        "items": list_materials(
            search=search,
            category=category,
            city=selected_city,
        ),
    }


@router.post(
    "/materials/import-viyar",
    response_model=MaterialCatalogOperationResponseSchema,
)
async def import_material_from_viyar_route(

    payload: MaterialImportFromViyarSchema,
    current_user = Depends(require_material_editor)
):

    selected_city = (current_user.city or "").strip()

    if not selected_city:
        return {
            "success": False,
            "error": "Select your city in profile settings first",
        }

    cookie_override = current_user.viyar_cookie

    if not cookie_override and current_user.viyar_email and current_user.viyar_password_secret:
        password = decrypt_secret(current_user.viyar_password_secret)

        if password:
            auth_result = await login_viyar_and_get_cookie(
                email=current_user.viyar_email,
                password=password,
            )

            if auth_result["success"]:
                cookie_override = auth_result["cookie"]
                update_user_viyar_session(
                    user_id=current_user.id,
                    viyar_cookie=cookie_override,
                    status="connected",
                    error=None,
                )
            else:
                update_user_viyar_session(
                    user_id=current_user.id,
                    viyar_cookie=None,
                    status="error",
                    error=auth_result["error"],
                )

    job = await enqueue_material_import_job(
        article=payload.article.strip(),
        category=payload.category,
        city=selected_city,
        owner_user_id=current_user.id,
        preferred_url=(payload.source_url or "").strip() or None,
    )

    existing_item = get_material_import_job_result(payload.article.strip(), selected_city)

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="catalog.material_import_queued",
        entity_type="material_import_job",
        entity_id=str(job["id"]),
        details={
            "article": payload.article.strip(),
            "category": payload.category,
            "city": selected_city,
            "preferred_url": (payload.source_url or "").strip() or None,
        }
    )

    return {
        "success": True,
        "job": job,
        "item": existing_item,
        "selected_city": selected_city,
        "error": "Material import queued. The system will retry automatically.",
    }


@router.get(
    "/materials/import-jobs/{job_id}",
    response_model=MaterialCatalogOperationResponseSchema,
)
async def get_material_import_job_route(

    job_id: int,
    current_user = Depends(require_catalog_reader)
):

    job = get_material_import_job(job_id)

    if not job:
        return {
            "success": False,
            "error": "Material import job not found",
        }

    item = None

    if job["status"] == "success":
        item = get_material_import_job_result(job["article"], job["city"])

    return {
        "success": True,
        "job": job,
        "item": item,
        "selected_city": job["city"],
    }


@router.delete(
    "/materials/{article}",
    response_model=MaterialCatalogOperationResponseSchema,
)
async def delete_material_route(
    article: str,
    current_user = Depends(require_material_editor)
):

    result = delete_material(article.strip())

    if not result:
        return {
            "success": False,
            "error": "Material not found",
        }

    if result["is_default"]:
        return {
            "success": False,
            "error": "Default material cannot be deleted",
        }

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="catalog.material_deleted",
        entity_type="material",
        entity_id=article.strip(),
        details={
            "article": article.strip(),
        }
    )

    return {
        "success": True,
        "selected_city": current_user.city,
    }


@router.get(
    "/fittings",
    response_model=FittingCatalogListResponseSchema,
)
async def list_fittings_route(

    search: str | None = Query(default=None),
    city: str | None = Query(default=None),
    current_user = Depends(require_catalog_reader)
):

    return {
        "success": True,
        "items": list_fittings(
            search=search,
            city=city,
        ),
    }


@router.get(
    "/items",
    response_model=CatalogItemListResponseSchema
)
async def list_catalog_items_route(

    include_inactive: bool = Query(
        default=True
    ),

    current_user = Depends(require_catalog_reader)
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


@router.get(
    "/viyar-services/tree",
    response_model=ServiceCatalogTreeResponseSchema,
)
async def list_viyar_services_tree_route(

    include_inactive: bool = Query(
        default=False
    ),

    current_user = Depends(require_catalog_admin)
):

    return {
        "success": True,
        "source": "viyar",
        "items": list_service_catalog_tree(
            source="viyar",
            include_inactive=include_inactive,
            user_id=current_user.id,
        ),
    }


@router.put(
    "/viyar-services/{item_id}",
    response_model=ServiceCatalogOperationResponseSchema,
)
async def update_viyar_service_route(

    item_id: str,

    payload: ServiceCatalogItemUpdateSchema,

    current_user = Depends(require_catalog_admin)
):

    item = update_service_catalog_item(
        item_id=item_id,
        unit=payload.unit,
        base_price=payload.base_price,
        is_calculable=payload.is_calculable,
        is_active=payload.is_active,
    )

    if not item:
        return {
            "success": False,
            "error": "Service catalog item not found"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="catalog.viyar_service_updated",

        entity_type="service_catalog_item",

        entity_id=item["id"],

        details=item
    )

    return {
        "success": True,
        "item": item,
    }


@router.post(
    "/viyar-services/import",
    response_model=ServiceCatalogSyncResponseSchema,
)
async def import_viyar_services_route(

    current_user = Depends(require_catalog_admin)
):
    cookie_override = current_user.viyar_cookie

    if not cookie_override and current_user.viyar_email and current_user.viyar_password_secret:
        password = decrypt_secret(current_user.viyar_password_secret)

        if password:
            auth_result = await login_viyar_and_get_cookie(
                email=current_user.viyar_email,
                password=password,
            )

            if auth_result["success"]:
                cookie_override = auth_result["cookie"]
                update_user_viyar_session(
                    user_id=current_user.id,
                    viyar_cookie=cookie_override,
                    status="connected",
                    error=None,
                )
            else:
                update_user_viyar_session(
                    user_id=current_user.id,
                    viyar_cookie=None,
                    status="error",
                    error=auth_result["error"],
                )

    result = sync_viyar_service_catalog(
        cookie_override=cookie_override,
    )

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="catalog.viyar_services_imported",

        entity_type="service_catalog",

        entity_id="viyar-services",

        details={
            "source": "viyar",
            "imported_count": result["imported_count"],
            "folder_count": result["folder_count"],
            "service_count": result["service_count"],
        }
    )

    return {
        "success": True,
        "source": "viyar",
        "imported_count": result["imported_count"],
        "folder_count": result["folder_count"],
        "service_count": result["service_count"],
        "fallback_only_import": result.get("fallback_only_import", False),
        "items": result["items"],
    }


@router.post(
    "/viyar-services/sync-prices",
    response_model=ServiceCatalogPriceSyncResponseSchema,
)
async def sync_viyar_service_prices_route(

    current_user = Depends(require_current_user)
):
    cookie_override = current_user.viyar_cookie

    if not cookie_override and current_user.viyar_email and current_user.viyar_password_secret:
        password = decrypt_secret(current_user.viyar_password_secret)

        if password:
            auth_result = await login_viyar_and_get_cookie(
                email=current_user.viyar_email,
                password=password,
            )

            if auth_result["success"]:
                cookie_override = auth_result["cookie"]
                update_user_viyar_session(
                    user_id=current_user.id,
                    viyar_cookie=cookie_override,
                    status="connected",
                    error=None,
                )
            else:
                update_user_viyar_session(
                    user_id=current_user.id,
                    viyar_cookie=None,
                    status="error",
                    error=auth_result["error"],
                )

    result = sync_viyar_service_prices(
        user_id=current_user.id,
        cookie_override=cookie_override,
    )

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="catalog.viyar_service_prices_synced",

        entity_type="service_catalog",

        entity_id="viyar-services",

        details={
            "source": result.get("source", "viyar"),
            "auth_required": result["auth_required"],
            "priced_count": result["priced_count"],
            "skipped_count": result["skipped_count"],
        }
    )

    return {
        "success": True,
        "source": result.get("source", "viyar"),
        "priced_count": result["priced_count"],
        "skipped_count": result["skipped_count"],
        "auth_required": result["auth_required"],
        "items": result["items"],
    }


@router.get(
    "/manual-services/tree",
    response_model=ServiceCatalogTreeResponseSchema,
)
async def list_manual_services_tree_route(
    include_inactive: bool = Query(default=True),
    current_user = Depends(require_current_user),
):

    return {
        "success": True,
        "source": "manual",
        "items": list_service_catalog_tree(
            source="manual",
            include_inactive=include_inactive,
            user_id=current_user.id,
            owner_user_id=current_user.id,
        ),
    }


@router.post(
    "/manual-services",
    response_model=ServiceCatalogOperationResponseSchema,
)
async def create_manual_service_route(
    payload: ManualServiceCatalogItemCreateSchema,
    current_user = Depends(require_manual_service_editor),
):

    if not payload.name.strip():
        return {
            "success": False,
            "error": "Manual service name is required",
        }

    item = create_manual_service_catalog_item(
        user_id=current_user.id,
        name=payload.name,
        article=payload.article,
        description=payload.description,
        unit=payload.unit,
        base_price=payload.base_price,
        is_calculable=payload.is_calculable,
        is_active=payload.is_active,
    )

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="catalog.manual_service_created",
        entity_type="service_catalog_item",
        entity_id=item["id"],
        details=item,
    )

    return {
        "success": True,
        "item": item,
    }


@router.put(
    "/manual-services/{item_id}",
    response_model=ServiceCatalogOperationResponseSchema,
)
async def update_manual_service_route(
    item_id: str,
    payload: ManualServiceCatalogItemUpdateSchema,
    current_user = Depends(require_manual_service_editor),
):

    if not payload.name.strip():
        return {
            "success": False,
            "error": "Manual service name is required",
        }

    item = update_manual_service_catalog_item(
        user_id=current_user.id,
        item_id=item_id,
        name=payload.name,
        article=payload.article,
        description=payload.description,
        unit=payload.unit,
        base_price=payload.base_price,
        is_calculable=payload.is_calculable,
        is_active=payload.is_active,
    )

    if not item:
        return {
            "success": False,
            "error": "Manual service catalog item not found",
        }

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="catalog.manual_service_updated",
        entity_type="service_catalog_item",
        entity_id=item["id"],
        details=item,
    )

    return {
        "success": True,
        "item": item,
    }
