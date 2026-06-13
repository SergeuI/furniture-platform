from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
)
from fastapi.responses import Response

from api.dependencies.auth import (
    optional_current_user,
    require_current_user,
    require_roles
)

from schemas.catalog import (
    CatalogAutoRefreshStatusResponseSchema,
    CatalogItemActiveSchema,
    CatalogItemCreateSchema,
    CatalogItemListResponseSchema,
    CatalogItemOperationResponseSchema,
    FittingCatalogCreateSchema,
    FittingCatalogListResponseSchema,
    FittingCatalogOperationResponseSchema,
    FittingCatalogUpdateSchema,
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
    create_fitting,
    delete_fitting,
    delete_material,
    get_fitting_by_id,
    get_material_by_article,
    list_fittings,
    list_fitting_categories,
    list_inventory_cities,
    list_material_categories,
    list_materials,
    update_fitting,
    update_material_image_cache,
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
from services.fitting_source_parser import (
    parse_fitting_source_metadata,
)
from services.auth_service import (
    get_user_from_token,
)
from services.material_import_queue_service import (
    enqueue_material_import_job,
    get_material_import_job_result,
)
from services.material_catalog_service import (
    warm_material_image_cache_for_item,
    resolve_material_image_payload,
)
from services.catalog_auto_refresh_service import (
    get_catalog_auto_refresh_status,
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

require_fitting_editor = require_roles(
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


def _warm_material_image_cache_task(
    material: dict,
    city: str | None,
    cookie_override: str | None,
) -> None:

    try:
        image_payload = warm_material_image_cache_for_item(
            material,
            city=city,
            cookie_override=cookie_override,
        )

        if image_payload:
            update_material_image_cache(
                article=material["article"],
                image_bytes=image_payload["bytes"],
                content_type=image_payload["content_type"],
            )
    except Exception:
        pass


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
    "/auto-refresh/status",
    response_model=CatalogAutoRefreshStatusResponseSchema,
)
async def get_catalog_auto_refresh_status_route(
    current_user = Depends(require_catalog_reader),
):

    return {
        "success": True,
        "status": get_catalog_auto_refresh_status(),
    }


@router.get(
    "/materials",
    response_model=MaterialCatalogListResponseSchema,
)
async def list_materials_route(

    background_tasks: BackgroundTasks,
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    city: str | None = Query(default=None),
    current_user = Depends(require_catalog_reader)
):

    selected_city = city or current_user.city
    items = list_materials(
        search=search,
        category=category,
        city=selected_city,
    )

    for item in items:
        if not item.get("has_cached_image"):
            background_tasks.add_task(
                _warm_material_image_cache_task,
                item,
                selected_city,
                current_user.viyar_cookie,
            )

    if selected_city:
        pending_material_items = [
            item
            for item in items
            if item.get("article") and (
                item.get("current_price") is None
                or not item.get("source_url")
            )
        ][:6]

        for item in pending_material_items:
            try:
                await enqueue_material_import_job(
                    article=item["article"],
                    category=item.get("category") or "dsp",
                    city=selected_city,
                    owner_user_id=str(current_user.id),
                    preferred_url=item.get("source_url"),
                )
            except Exception:
                pass

    return {
        "success": True,
        "categories": list_material_categories(),
        "city_options": list_inventory_cities(),
        "selected_city": selected_city,
        "items": items,
    }


@router.get("/materials/{article}/image")
async def get_material_image_route(
    article: str,
    access_token: str | None = Query(default=None),
    current_user = Depends(optional_current_user)
):

    authorized_user = current_user

    if not authorized_user and access_token:
        authorized_user = get_user_from_token(access_token)

    material = get_material_by_article(article.strip())

    if not material:
        return Response(status_code=404)

    if material.get("image_cached_bytes"):
        return Response(
            content=material["image_cached_bytes"],
            media_type=material.get("image_cached_content_type") or "image/jpeg",
            headers={
                "Cache-Control": "public, max-age=86400",
            },
        )

    image_payload = resolve_material_image_payload(
        article=material["article"],
        stored_image=material.get("image"),
        source_url=material.get("source_url"),
        city=getattr(authorized_user, "city", None),
        cookie_override=getattr(authorized_user, "viyar_cookie", None),
    )

    if not image_payload:
        return Response(status_code=404)

    if not material.get("has_cached_image"):
        update_material_image_cache(
            article=material["article"],
            image_bytes=image_payload["bytes"],
            content_type=image_payload["content_type"],
        )

    return Response(
        content=image_payload["bytes"],
        media_type=image_payload["content_type"],
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.post(
    "/materials/import-viyar",
    response_model=MaterialCatalogOperationResponseSchema,
)
async def import_material_from_viyar_route(

    payload: MaterialImportFromViyarSchema,
    current_user = Depends(require_material_editor)
):

    normalized_article = payload.article.strip()
    selected_city = (current_user.city or "").strip()

    if not selected_city:
        return {
            "success": False,
            "error": "Select your city in profile settings first",
        }

    existing_item = get_material_import_job_result(
        normalized_article,
        selected_city,
    )

    if (
        not payload.force_refresh and
        existing_item and
        existing_item.get("name") and
        existing_item.get("current_price") is not None
    ):
        create_audit_log(
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            action="catalog.material_cache_hit",
            entity_type="material",
            entity_id=normalized_article,
            details={
                "article": normalized_article,
                "city": selected_city,
                "source": "database",
            }
        )
        return {
            "success": True,
            "item": existing_item,
            "selected_city": selected_city,
            "error": None,
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
        article=normalized_article,
        category=payload.category,
        city=selected_city,
        owner_user_id=current_user.id,
        preferred_url=(payload.source_url or "").strip() or None,
    )

    existing_item = get_material_import_job_result(normalized_article, selected_city)

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="catalog.material_import_queued",
        entity_type="material_import_job",
        entity_id=str(job["id"]),
        details={
            "article": normalized_article,
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
    fitting_group: str | None = Query(default=None),
    fitting_type: str | None = Query(default=None),
    current_user = Depends(require_catalog_reader)
):
    selected_city = city or current_user.city

    items = list_fittings(
        search=search,
        city=selected_city,
        viewer_user_id=current_user.id,
        viewer_role=current_user.role,
        fitting_group=fitting_group,
        fitting_type=fitting_type,
    )

    return {
        "success": True,
        "city_options": list_inventory_cities(),
        "selected_city": selected_city,
        "categories": list_fitting_categories(items, group=fitting_group),
        "items": items,
    }


def _can_manage_fitting_item(current_user, item: dict | None) -> bool:

    if not item:
        return False

    if current_user.role == "admin":
        return True

    return (
        current_user.role == "pro" and
        not item.get("is_system") and
        item.get("owner_user_id") == str(current_user.id)
    )


@router.post(
    "/fittings",
    response_model=FittingCatalogOperationResponseSchema,
)
async def create_fitting_route(
    payload: FittingCatalogCreateSchema,
    current_user = Depends(require_fitting_editor),
):

    if payload.is_system and current_user.role != "admin":
        return {
            "success": False,
            "error": "Only admin can create default fittings",
        }

    if payload.is_system and not (payload.source_url or "").strip():
        return {
            "success": False,
            "error": "Source URL is required for default fittings",
        }

    effective_name = (payload.name or "").strip()
    effective_image_url = payload.image_url
    effective_source_url = (payload.source_url or "").strip() or None
    effective_article = (payload.article or "").strip() or None
    effective_price = payload.price
    effective_stock = payload.stock

    if payload.is_system and effective_source_url:
        metadata = await parse_fitting_source_metadata(effective_source_url)
        if metadata.get("success"):
            effective_name = metadata.get("name") or effective_name
            effective_image_url = metadata.get("image_url") or effective_image_url
            effective_source_url = metadata.get("final_url") or effective_source_url
            effective_article = effective_article or metadata.get("article")
            effective_price = metadata.get("price") if metadata.get("price") is not None else effective_price

    if not effective_name:
        effective_name = effective_article or ""

    if not effective_name.strip():
        return {
            "success": False,
            "error": "Fitting name is required",
        }

    owner_user_id = None if payload.is_system else str(current_user.id)
    selected_city = (payload.city or current_user.city or "").strip() or None

    item = create_fitting(
        city=selected_city,
        code=payload.code,
        article=effective_article,
        name=effective_name,
        price=effective_price,
        stock=effective_stock,
        fitting_type=payload.fitting_type,
        fitting_group=payload.fitting_group,
        image_url=effective_image_url,
        source_url=effective_source_url,
        owner_user_id=owner_user_id,
        is_system=payload.is_system,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="catalog.fitting_created",
        entity_type="fitting",
        entity_id=item["id"],
        details=item,
    )

    return {
        "success": True,
        "item": item,
    }


@router.put(
    "/fittings/{item_id}",
    response_model=FittingCatalogOperationResponseSchema,
)
async def update_fitting_route(
    item_id: str,
    payload: FittingCatalogUpdateSchema,
    current_user = Depends(require_fitting_editor),
):

    existing_item = get_fitting_by_id(item_id)

    if not existing_item:
        return {
            "success": False,
            "error": "Fitting not found",
        }

    if not _can_manage_fitting_item(current_user, existing_item):
        return {
            "success": False,
            "error": "You do not have permission to edit this fitting",
        }

    if payload.is_system and current_user.role != "admin":
        return {
            "success": False,
            "error": "Only admin can manage default fittings",
        }

    if payload.is_system and not (payload.source_url or "").strip():
        return {
            "success": False,
            "error": "Source URL is required for default fittings",
        }

    owner_user_id = None if payload.is_system else existing_item.get("owner_user_id") or str(current_user.id)
    selected_city = (payload.city or current_user.city or "").strip() or None

    effective_name = (payload.name or "").strip()
    effective_image_url = payload.image_url
    effective_source_url = (payload.source_url or "").strip() or None
    effective_article = (payload.article or "").strip() or None
    effective_price = payload.price
    effective_stock = payload.stock

    if payload.is_system and effective_source_url:
        metadata = await parse_fitting_source_metadata(effective_source_url)
        if metadata.get("success"):
            effective_name = metadata.get("name") or effective_name
            effective_image_url = metadata.get("image_url") or effective_image_url
            effective_source_url = metadata.get("final_url") or effective_source_url
            effective_article = effective_article or metadata.get("article")
            effective_price = metadata.get("price") if metadata.get("price") is not None else effective_price

    if not effective_name:
        effective_name = effective_article or ""

    item = update_fitting(
        item_id=item_id,
        city=selected_city,
        code=payload.code,
        article=effective_article,
        name=effective_name,
        price=effective_price,
        stock=effective_stock,
        fitting_type=payload.fitting_type,
        fitting_group=payload.fitting_group,
        image_url=effective_image_url,
        source_url=effective_source_url,
        owner_user_id=owner_user_id,
        is_system=payload.is_system,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="catalog.fitting_updated",
        entity_type="fitting",
        entity_id=item_id,
        details=item,
    )

    return {
        "success": True,
        "item": item,
    }


@router.delete(
    "/fittings/{item_id}",
    response_model=FittingCatalogOperationResponseSchema,
)
async def delete_fitting_route(
    item_id: str,
    current_user = Depends(require_fitting_editor),
):

    existing_item = get_fitting_by_id(item_id)

    if not existing_item:
        return {
            "success": False,
            "error": "Fitting not found",
        }

    if not _can_manage_fitting_item(current_user, existing_item):
        return {
            "success": False,
            "error": "You do not have permission to delete this fitting",
        }

    item = delete_fitting(item_id)

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="catalog.fitting_deleted",
        entity_type="fitting",
        entity_id=item_id,
        details=item or existing_item,
    )

    return {
        "success": True,
        "item": item or existing_item,
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
