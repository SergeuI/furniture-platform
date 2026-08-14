import asyncio

import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Header,
    Query,
)
from fastapi.responses import Response
from hashlib import sha256
from datetime import datetime
import json
from threading import Lock
from uuid import uuid4
from urllib.parse import urlparse

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
    FittingCatalogDetailResponseSchema,
    FittingCatalogListResponseSchema,
    FittingCatalogOperationResponseSchema,
    FittingCatalogUpdateSchema,
    FittingSourcePreviewRequestSchema,
    FittingSourcePreviewResponseSchema,
    FittingSupplierOfferInputSchema,
    FittingSupplierListResponseSchema,
    FittingSupplierOfferListResponseSchema,
    FittingSupplierOfferOperationResponseSchema,
    CatalogItemUpdateSchema,
    ManualServiceCatalogItemCreateSchema,
    ManualServiceCatalogItemUpdateSchema,
    FittingCategoryListResponseSchema,
    FittingManufacturerCreateSchema,
    FittingManufacturerListResponseSchema,
    FittingManufacturerOperationResponseSchema,
    FittingManufacturerUpdateSchema,
    FittingProductDetailResponseSchema,
    FittingProductListResponseSchema,
    FittingProductTaxonomyOperationResponseSchema,
    FittingProductTaxonomyUpdateSchema,
    FittingSeriesCreateSchema,
    FittingSeriesListResponseSchema,
    FittingSeriesOperationResponseSchema,
    FittingSeriesUpdateSchema,
    FittingTaxonomyCategoryCreateSchema,
    FittingTaxonomyCategoryOperationResponseSchema,
    FittingTaxonomyCategoryUpdateSchema,
    MaterialCatalogCreateSchema,
    MaterialCatalogUpdateSchema,
    MaterialEdgeAttachSchema,
    MaterialEdgeOperationResponseSchema,
    MaterialCatalogOperationResponseSchema,
    MaterialCatalogListResponseSchema,
    MaterialImportFromViyarSchema,
    MaterialOwnersResponseSchema,
    ServiceCatalogItemUpdateSchema,
    ServiceCatalogOperationResponseSchema,
    ServiceCatalogPriceSyncResponseSchema,
    ServiceCatalogSyncResponseSchema,
    ServiceCatalogTreeResponseSchema,
    SpecificationCatalogResponseSchema
)
from database.models.fitting import (
    FittingCategoryModel,
    FittingModel,
    FittingManufacturerModel,
    FittingProductModel,
    FittingSeriesModel,
    SupplierModel,
)
from database.repositories.catalog_repository import (
    ALLOWED_CATALOG_CATEGORIES,
    create_catalog_item,
    get_specification_catalog,
    list_catalog_items,
    set_catalog_item_active,
    update_catalog_item
)
from database.repositories.fitting_taxonomy_repository import (
    create_fitting_category,
    create_fitting_manufacturer,
    create_fitting_series,
    delete_fitting_category,
    delete_fitting_manufacturer,
    delete_fitting_series,
    get_fitting_category_by_id,
    get_fitting_manufacturer_by_id,
    get_fitting_series_by_id,
    get_fitting_product_by_id,
    list_fitting_categories as list_taxonomy_categories,
    list_fitting_manufacturers,
    list_fitting_products,
    list_fitting_series,
    update_fitting_category,
    update_fitting_manufacturer,
    update_fitting_product_taxonomy,
    update_fitting_series,
)
from database.repositories.service_catalog_repository import (
    create_manual_service_catalog_item,
    get_viyar_service_description_audit,
    list_service_catalog_tree,
    sync_viyar_service_catalog,
    sync_viyar_service_prices,
    update_manual_service_catalog_item,
    update_service_catalog_item,
)
from database.repositories.inventory_repository import (
    MATERIAL_EDGE_LABELS,
    ensure_material_user_link,
    count_owned_private_materials,
    create_fitting,
    delete_fitting,
    delete_material,
    get_fitting_image,
    get_fitting_by_id,
    get_fitting_image_by_id,
    list_fitting_delete_dependencies,
    get_material_by_import_identity,
    get_material_edge_image,
    get_material_by_article,
    get_material_owners,
    list_fitting_images,
    list_fitting_supplier_offers,
    list_fittings,
    list_fitting_categories,
    list_inventory_cities,
    list_suppliers,
    list_material_categories,
    list_materials,
    _serialize_fitting,
    _serialize_fitting_supplier_offer,
    upsert_material,
    upsert_material_edge_option,
    upsert_material_edge_price,
    upsert_material_price,
    material_needs_full_sync,
    update_fitting,
    update_fitting_image_cache,
    update_material,
    update_material_edge_image_cache,
    update_material_image_cache,
)
from database.repositories.fitting_foundation_repository import (
    FittingFoundationRepository,
)
from database.session import (
    SessionLocal,
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
from services.fitting_image_gallery_service import (
    FittingGalleryPreparationError,
    normalize_fitting_gallery_image_urls,
    prepare_fitting_gallery_images,
)
from services.auth_service import (
    get_user_from_token,
)
from services.entitlement_service import (
    EntitlementService,
)
from services.material_import_queue_service import (
    enqueue_material_import_job,
    get_material_import_job_result,
)
from services.material_catalog_service import (
    CITY_COOKIES as MATERIAL_CITY_COOKIES,
    detect_material_source_site,
    fetch_material_by_source_live_traced,
    fetch_viyar_product_details_by_url_traced,
    fetch_remote_image_payload,
    prefetch_material_image_cache,
    warm_material_image_cache_for_item,
    resolve_material_image_payload,
)
from services.catalog_auto_refresh_service import (
    get_catalog_auto_refresh_status,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_material_image_warm_lock = Lock()
_material_images_being_warmed: set[str] = set()
_fitting_images_being_warmed: set[str] = set()


def _claim_material_image_warm(article: str | None) -> bool:
    normalized_article = str(article or "").strip()

    if not normalized_article:
        return False

    with _material_image_warm_lock:
        if normalized_article in _material_images_being_warmed:
            return False

        _material_images_being_warmed.add(normalized_article)
        return True


def _release_material_image_warm(article: str | None) -> None:
    normalized_article = str(article or "").strip()

    if not normalized_article:
        return

    with _material_image_warm_lock:
        _material_images_being_warmed.discard(normalized_article)


def _normalize_import_source_url(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if "://" not in normalized:
        normalized = f"https://{normalized}"
    parsed = urlparse(normalized)
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""
    query = f"?{parsed.query}" if parsed.query else ""
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
    rebuilt = f"{scheme}://{host}{path}{query}{fragment}"
    return rebuilt.rstrip("/") if rebuilt.endswith("/") and path not in ("", "/") else rebuilt


def _find_material_import_match(
    *,
    source_url: str | None,
    article: str | None,
    category: str | None,
) -> dict | None:
    normalized_article = (article or "").strip() or None
    normalized_source_url = _normalize_import_source_url(source_url)
    source_site = detect_material_source_site(source_url)

    return get_material_by_import_identity(
        source=source_site,
        product_type=(category or "").strip() or None,
        article=normalized_article,
        source_url=normalized_source_url,
    )


def _link_material_for_user(
    *,
    material: dict,
    current_user,
    source_url: str | None = None,
) -> dict:
    ensure_material_user_link(
        article=material["article"],
        user_id=str(current_user.id),
        source=material.get("source") or detect_material_source_site(material.get("source_url") or source_url),
        product_type=material.get("product_type") or material.get("category"),
        source_url=material.get("source_url") or source_url,
    )
    return get_material_by_article(
        material["article"],
        viewer_user_id=str(current_user.id),
        viewer_role=current_user.role,
    ) or material


def _claim_fitting_image_warm(item_id: str | None) -> bool:
    normalized_id = str(item_id or "").strip()

    if not normalized_id:
        return False

    with _material_image_warm_lock:
        if normalized_id in _fitting_images_being_warmed:
            return False

        _fitting_images_being_warmed.add(normalized_id)
        return True


def _release_fitting_image_warm(item_id: str | None) -> None:
    with _material_image_warm_lock:
        _fitting_images_being_warmed.discard(str(item_id or "").strip())


def _looks_like_url(value: str | None) -> bool:
    normalized = str(value or "").strip()
    if not normalized:
        return False

    if normalized.lower().startswith(("http://", "https://", "www.")):
        return True

    try:
        parsed = urlparse(normalized if "://" in normalized else f"https://{normalized}")
        return bool(parsed.netloc or parsed.path) and "." in normalized
    except Exception:
        return False


async def _parse_fitting_source_or_error(source_url: str) -> tuple[dict | None, dict | None]:
    metadata = await parse_fitting_source_metadata(source_url)
    if metadata.get("success"):
        return metadata, None

    logger.warning(
        "Fitting source import failed",
        extra={
            "source_url": source_url,
            "source_site": metadata.get("source_site"),
            "error": metadata.get("error"),
        },
    )
    error_message = str(metadata.get("error") or "").strip() or "?? ??????? ???????? ???? ?? ??????????. ????????? ????????? ??? ????????? ???????."
    return None, {
        "success": False,
        "error": error_message,
    }

def _normalize_fitting_detail_text(value: object | None) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def _resolve_fitting_source_supplier(source_site: str | None) -> dict | None:
    normalized_source_site = _normalize_fitting_detail_text(source_site)
    if not normalized_source_site:
        return None

    db = SessionLocal()
    try:
        repository = FittingFoundationRepository(db)
        supplier = repository.get_supplier_by_code(normalized_source_site)
        if not supplier:
            return None

        return {
            "id": int(supplier.id),
            "code": supplier.code,
            "name": supplier.name,
            "is_active": bool(supplier.is_active),
        }
    finally:
        db.close()


def _build_fitting_source_preview_payload(
    metadata: dict,
    *,
    source_url: str,
    city: str | None = None,
) -> dict:
    normalized_source_url = _normalize_fitting_detail_text(metadata.get("final_url")) or _normalize_fitting_detail_text(source_url)
    source_site = _normalize_fitting_detail_text(metadata.get("source_site")) or detect_material_source_site(normalized_source_url)
    raw_image_urls = metadata.get("image_urls") if isinstance(metadata.get("image_urls"), list) else []
    normalized_image_urls = [
        normalized
        for normalized in (_normalize_fitting_detail_text(item) for item in raw_image_urls)
        if normalized
    ]
    normalized_image_url = _normalize_fitting_detail_text(metadata.get("image_url"))
    if not normalized_image_url and normalized_image_urls:
        normalized_image_url = normalized_image_urls[0]

    return {
        "source": source_site,
        "source_site": source_site,
        "source_url": normalized_source_url,
        "city": _normalize_fitting_detail_text(city),
        "name": _normalize_fitting_detail_text(metadata.get("name")),
        "article": _normalize_fitting_detail_text(metadata.get("article")),
        "brand": _normalize_fitting_detail_text(metadata.get("brand")),
        "image_url": normalized_image_url,
        "image_urls": normalized_image_urls,
        "price": metadata.get("price") if metadata.get("price") is not None else None,
        "availability": _normalize_fitting_detail_text(metadata.get("availability")),
        "currency": _normalize_fitting_detail_text(metadata.get("currency")),
        "unit": _normalize_fitting_detail_text(metadata.get("unit") or metadata.get("normalized_unit")),
        "supplier": _resolve_fitting_source_supplier(source_site),
    }


@router.post(
    "/fittings/source-preview",
    response_model=FittingSourcePreviewResponseSchema,
)
async def preview_fitting_source_route(
    payload: FittingSourcePreviewRequestSchema,
    current_user = Depends(require_roles([
        "admin",
        "trial",
        "premium",
        "pro",
        "free",
    ])),
):
    _ensure_fitting_feature_access(current_user, "fittings.create")

    source_url = (payload.source_url or "").strip()
    if not source_url:
        return {
            "success": False,
            "error": "Source URL is required",
        }

    metadata, error_response = await _parse_fitting_source_or_error(source_url)
    if error_response or not metadata:
        return error_response or {
            "success": False,
            "error": "Не вдалося отримати дані за посиланням. Перевірте посилання або спробуйте пізніше.",
        }

    return {
        "success": True,
        **_build_fitting_source_preview_payload(
            metadata,
            source_url=source_url,
            city=payload.city,
        ),
    }


def _safe_parse_source_payload_json(value: object | None) -> dict[str, object]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    raw_text = _normalize_fitting_detail_text(value)
    if not raw_text:
        return {}

    try:
        parsed = json.loads(raw_text)
    except Exception:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _normalize_fitting_characteristics(value: object | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = _normalize_fitting_detail_text(raw_key)
        if not key:
            continue

        if raw_value is None:
            continue

        if isinstance(raw_value, (str, int, float, bool)):
            normalized_value = _normalize_fitting_detail_text(raw_value)
        else:
            continue

        if not normalized_value:
            continue

        if key in normalized and normalized[key]:
            continue

        normalized[key] = normalized_value

    return normalized


def _serialize_fitting_detail(item: FittingModel) -> dict:
    serialized = dict(_serialize_fitting(item))
    serialized["id"] = int(item.id)
    serialized["supplier_offers"] = list_fitting_supplier_offers(item.id)
    source_payload = _safe_parse_source_payload_json(item.source_payload_json)
    parsed_item = source_payload.get("parsed_item") if isinstance(source_payload, dict) else {}
    if not isinstance(parsed_item, dict):
        parsed_item = source_payload if isinstance(source_payload, dict) else {}
    preview_payload = source_payload.get("preview") if isinstance(source_payload, dict) else {}
    parsed_item_dict = parsed_item if isinstance(parsed_item, dict) else {}
    preview_dict = preview_payload if isinstance(preview_payload, dict) else {}
    source_site = _normalize_fitting_detail_text(item.source) or detect_material_source_site(item.source_url)
    parsed_characteristics = _normalize_fitting_characteristics(parsed_item_dict.get("characteristics"))
    parsed_description = _normalize_fitting_detail_text(parsed_item_dict.get("description"))
    parsed_brand = _normalize_fitting_detail_text(parsed_item_dict.get("brand"))
    parsed_currency = _normalize_fitting_detail_text(parsed_item_dict.get("currency"))
    parsed_unit = _normalize_fitting_detail_text(parsed_item_dict.get("normalized_unit") or parsed_item_dict.get("unit"))
    parsed_availability = _normalize_fitting_detail_text(parsed_item_dict.get("availability"))
    parsed_at = item.parsed_at or _normalize_fitting_detail_text(preview_dict.get("parsed_at"))
    price_updated_at = item.price_updated_at or _normalize_fitting_detail_text(preview_dict.get("price_updated_at"))

    serialized.update(
        {
            "brand": _normalize_fitting_detail_text(item.brand) or parsed_brand,
            "currency": _normalize_fitting_detail_text(item.currency) or parsed_currency,
            "unit": _normalize_fitting_detail_text(item.unit) or parsed_unit,
            "availability": parsed_availability or _normalize_fitting_detail_text(item.stock),
            "characteristics": parsed_characteristics,
            "parsed_at": parsed_at,
            "price_updated_at": price_updated_at,
            "source_site": source_site,
            "description": _normalize_fitting_detail_text(item.description) or parsed_description,
            "has_cached_image": bool(item.image_cached_bytes),
            "image_cached_content_type": item.image_cached_content_type,
        }
    )

    return serialized


def _load_fitting_detail_item(item_id: str | int, current_user=None) -> dict | None:
    db = SessionLocal()
    try:
        fitting_model = (
            db.query(FittingModel)
            .filter(FittingModel.id == int(item_id))
            .first()
        )
        if not fitting_model:
            return None

        item = _serialize_fitting_detail(fitting_model)
        item["images"] = list_fitting_images(item_id)

        if current_user is not None:
            fitting = get_fitting_by_id(
                item_id,
                viewer_user_id=current_user.id,
                viewer_role=current_user.role,
            )
            if fitting:
                item["owner_user_id"] = fitting.get("owner_user_id")
                item["owner_display_name"] = fitting.get("owner_display_name")
                item["owner_login"] = fitting.get("owner_login")
                item["owner_email"] = fitting.get("owner_email")

        return item
    finally:
        db.close()


def _image_response(
    image_bytes: bytes,
    content_type: str | None,
    if_none_match: str | None = None,
) -> Response:
    etag = f'"{sha256(image_bytes).hexdigest()[:24]}"'
    headers = {
        "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
        "ETag": etag,
        "X-Content-Type-Options": "nosniff",
    }

    if if_none_match and etag in {part.strip() for part in if_none_match.split(",")}:
        return Response(status_code=304, headers=headers)

    return Response(
        content=image_bytes,
        media_type=content_type or "image/jpeg",
        headers=headers,
    )

require_catalog_admin = require_roles(
    [
        "admin"
    ]
)

require_catalog_reader = require_roles(
    [
        "admin",
        "trial",
        "premium",
        "pro",
        "free",
    ]
)

require_manual_service_editor = require_roles(
    [
        "admin",
        "premium",
        "pro",
        "free",
    ]
)

require_material_editor = require_roles(
    [
        "admin",
        "trial",
        "premium",
        "pro",
        "free",
    ]
)

require_fitting_editor = require_roles(
    [
        "admin",
        "premium",
        "pro",
    ]
)


async def _resolve_viyar_cookie_for_user(current_user) -> str | None:

    cookie_override = getattr(current_user, "viyar_cookie", None)

    if cookie_override:
        return cookie_override

    if not current_user.viyar_email or not current_user.viyar_password_secret:
        return None

    password = decrypt_secret(current_user.viyar_password_secret)

    if not password:
        return None

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
        return cookie_override

    update_user_viyar_session(
        user_id=current_user.id,
        viyar_cookie=None,
        status="error",
        error=auth_result["error"],
    )
    return None


def _can_manage_material_item(current_user, item: dict | None) -> bool:

    if not item:
        return False

    if current_user.role == "admin":
        return True

    if item.get("is_default"):
        return False

    return item.get("owner_user_id") == str(current_user.id)


def _get_material_ownership_quota(current_user) -> dict:

    owned_count = count_owned_private_materials(str(current_user.id))

    if current_user.role == "admin":
        return {
            "owned_count": owned_count,
            "limit": None,
            "is_unlimited": True,
            "can_create": True,
        }

    with EntitlementService() as service:
        limit_resolution = service.get_limit(current_user, "materials.max_owned")

    limit_value = limit_resolution.limit_value
    normalized_limit = int(limit_value) if limit_value is not None else None
    is_unlimited = limit_resolution.status == "unlimited"
    can_create = bool(
        is_unlimited
        or (
            normalized_limit is not None
            and owned_count < normalized_limit
        )
    )

    return {
        "owned_count": owned_count,
        "limit": normalized_limit,
        "is_unlimited": is_unlimited,
        "can_create": can_create,
    }


def _ensure_material_ownership_capacity(current_user) -> dict:

    quota = _get_material_ownership_quota(current_user)

    if not quota["can_create"]:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Material ownership limit reached",
            },
        )

    return quota


def _ensure_material_feature_access(current_user, feature_key: str) -> None:

    with EntitlementService() as service:
        if service.has_feature(current_user, feature_key):
            return

    raise HTTPException(
        status_code=403,
        detail={
            "success": False,
            "error": "Insufficient permissions",
        },
    )


def _ensure_fitting_feature_access(current_user, feature_key: str) -> None:

    with EntitlementService() as service:
        if service.has_feature(current_user, feature_key):
            return

    raise HTTPException(
        status_code=403,
        detail={
            "success": False,
            "error": "Insufficient permissions",
        },
    )


def _resolve_material_with_city_context(
    article: str,
    city: str | None,
    current_user,
    category: str | None = None,
) -> dict | None:

    normalized_article = (article or "").strip()

    if not normalized_article:
        return None

    items = list_materials(
        search=normalized_article,
        category=category,
        city=city,
        viewer_user_id=str(current_user.id),
        viewer_role=current_user.role,
    )

    return next(
        (
            item
            for item in items
            if str(item.get("article") or "").strip() == normalized_article
        ),
        get_material_by_article(
            normalized_article,
            viewer_user_id=str(current_user.id),
            viewer_role=current_user.role,
        ),
    )


async def _collect_material_prices_for_all_cities(
    *,
    article: str,
    preferred_url: str,
    cookie_override: str | None,
    selected_city: str | None = None,
) -> tuple[dict | None, dict[str, float | None]]:

    normalized_article = (article or "").strip()
    ordered_cities = []

    if selected_city:
        ordered_cities.append(selected_city)

    for city_code in MATERIAL_CITY_COOKIES.keys():
        if city_code not in ordered_cities:
            ordered_cities.append(city_code)

    prices_by_city: dict[str, float | None] = {}
    primary_material = None

    if detect_material_source_site(preferred_url) != "viyar":
        material, _debug_payload = await fetch_material_by_source_live_traced(
            normalized_article,
            city=selected_city,
            cookie_override=cookie_override,
            preferred_url=preferred_url,
        )
        return material, {
            city_code: material.get("price")
            for city_code in ordered_cities
        }

    for city_code in ordered_cities:
        try:
            material, _debug_payload = await fetch_material_by_source_live_traced(
                normalized_article,
                city=city_code,
                cookie_override=cookie_override,
                preferred_url=preferred_url,
            )
        except Exception:
            continue

        if not primary_material:
            primary_material = material

        prices_by_city[city_code] = material.get("price")

    return primary_material, prices_by_city


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
    finally:
        _release_material_image_warm(material.get("article"))


def _warm_material_edge_image_cache_task(
    material_article: str,
    edge_item: dict,
    city: str | None,
    cookie_override: str | None,
) -> None:
    cache_key = f"edge:{material_article}:{edge_item.get('edge_key')}"

    try:
        image_payload = resolve_material_image_payload(
            article=str(edge_item.get("article") or material_article),
            stored_image=edge_item.get("image"),
            source_url=edge_item.get("source_url"),
            city=city,
            cookie_override=cookie_override,
        )

        if image_payload:
            update_material_edge_image_cache(
                material_article=material_article,
                edge_key=edge_item["edge_key"],
                image_bytes=image_payload["bytes"],
                content_type=image_payload["content_type"],
            )
    except Exception:
        pass
    finally:
        _release_material_image_warm(cache_key)


def _warm_fitting_image_cache_task(fitting: dict) -> None:
    try:
        image_payload = fetch_remote_image_payload(
            fitting.get("image_url"),
            city=fitting.get("city"),
        )

        if image_payload:
            update_fitting_image_cache(
                item_id=fitting["id"],
                image_bytes=image_payload["bytes"],
                content_type=image_payload["content_type"],
            )
    except Exception:
        pass
    finally:
        _release_fitting_image_warm(fitting.get("id"))


@router.get(
    "/specification",
    response_model=SpecificationCatalogResponseSchema
)
async def get_specification_catalog_route():
    catalog = await asyncio.to_thread(
        get_specification_catalog
    )

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
    ownership_scope: str | None = Query(default=None),
    current_user = Depends(require_catalog_reader)
):

    _ensure_material_feature_access(current_user, "materials.view")

    selected_city = city or current_user.city
    items = list_materials(
        search=search,
        category=category,
        city=selected_city,
        viewer_user_id=str(current_user.id),
        viewer_role=current_user.role,
        ownership_scope=ownership_scope if current_user.role == "admin" else None,
    )

    # Прогрів картинок тимчасово вимкнено для діагностики швидкодії.

    return {
        "success": True,
        "categories": list_material_categories(),
        "city_options": list_inventory_cities(),
        "selected_city": selected_city,
        "material_quota": _get_material_ownership_quota(current_user),
        "items": items,
    }


@router.get(
    "/materials/{article}/owners",
    response_model=MaterialOwnersResponseSchema,
)
async def get_material_owners_route(
    article: str,
    current_user = Depends(require_roles(["admin"])),
):

    owners_payload = get_material_owners(article.strip())

    if owners_payload is None:
        return {
            "success": False,
            "error": "Material not found",
            "owners_count": 0,
            "owners": [],
        }

    return {
        "success": True,
        **owners_payload,
    }


@router.get("/materials/{article}/image")
async def get_material_image_route(
    article: str,
    access_token: str | None = Query(default=None),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    current_user = Depends(optional_current_user)
):

    authorized_user = current_user

    if not authorized_user and access_token:
        authorized_user = get_user_from_token(access_token)

    material = get_material_by_article(
        article.strip(),
        viewer_user_id=getattr(authorized_user, "id", None),
        viewer_role=getattr(authorized_user, "role", "free") if authorized_user else "free",
    )

    if not material:
        return Response(status_code=404)

    if material.get("image_cached_bytes"):
        return _image_response(
            material["image_cached_bytes"],
            material.get("image_cached_content_type"),
            if_none_match,
        )
    return Response(status_code=404)


@router.get("/materials/{article}/edges/{edge_key}/image")
async def get_material_edge_image_route(
    article: str,
    edge_key: str,
    access_token: str | None = Query(default=None),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    current_user = Depends(optional_current_user),
):

    authorized_user = current_user

    if not authorized_user and access_token:
        authorized_user = get_user_from_token(access_token)

    edge_item = get_material_edge_image(article.strip(), edge_key.strip())

    material = get_material_by_article(
        article.strip(),
        viewer_user_id=getattr(authorized_user, "id", None),
        viewer_role=getattr(authorized_user, "role", "free") if authorized_user else "free",
    )

    if not edge_item or not material:
        return Response(status_code=404)

    if edge_item.get("image_cached_bytes"):
        return _image_response(
            edge_item["image_cached_bytes"],
            edge_item.get("image_cached_content_type"),
            if_none_match,
        )
    return Response(status_code=404)


@router.post(
    "/materials",
    response_model=MaterialCatalogOperationResponseSchema,
)
async def create_material_route(

    payload: MaterialCatalogCreateSchema,
    current_user = Depends(require_material_editor)
):

    selected_city = (payload.city or current_user.city or "").strip()

    if not selected_city:
        return {
            "success": False,
            "error": "Select your city in profile settings first",
        }

    if payload.is_default and current_user.role != "admin":
        return {
            "success": False,
            "error": "Only admin can create system materials",
        }

    is_default = current_user.role == "admin"

    effective_category = (payload.category or "dsp").strip() or "dsp"
    effective_source_url = (payload.source_url or "").strip() or None
    effective_article = (payload.article or "").strip() or None
    effective_name = (payload.name or "").strip() or None
    effective_owner_user_id = None if is_default else str(current_user.id)

    existing_item = _find_material_import_match(
        source_url=effective_source_url,
        article=effective_article,
        category=effective_category,
    ) if effective_source_url and effective_article else (
        get_material_by_article(effective_article) if effective_article else None
    )

    if existing_item and not _can_manage_material_item(current_user, existing_item):
        if existing_item.get("is_default"):
            _ensure_material_feature_access(current_user, "materials.view")
            resolved_existing_item = _resolve_material_with_city_context(
                effective_article,
                selected_city,
                current_user,
                effective_category,
            ) or existing_item
            return {
                "success": True,
                "item": resolved_existing_item,
                "selected_city": selected_city,
                "error": "Material already exists in the shared catalog",
            }
        return {
            "success": False,
            "error": "Material with this article already exists",
        }

    if existing_item:
        _ensure_material_feature_access(current_user, "materials.edit")
    else:
        _ensure_material_feature_access(current_user, "materials.create")

    if effective_source_url:
        if not effective_article:
            return {
                "success": False,
                "error": "Article is required when adding material from a link",
            }

        if not existing_item and not is_default:
            _ensure_material_ownership_capacity(current_user)

        source_site = detect_material_source_site(effective_source_url)

        if existing_item and not material_needs_full_sync(existing_item):
            item = _link_material_for_user(
                material=existing_item,
                current_user=current_user,
                source_url=effective_source_url,
            )
            return {
                "success": True,
                "item": item,
                "selected_city": selected_city,
                "error": None,
            }

        if source_site != "viyar":
            item = upsert_material(
                article=effective_article,
                name=effective_name or effective_article,
                category=effective_category,
                image=payload.image_url,
                source_url=effective_source_url,
                owner_user_id=effective_owner_user_id,
                is_default=is_default,
                source=source_site,
                product_type=effective_category,
                image_source_url=payload.image_url,
            )
            primary_job = await enqueue_material_import_job(
                article=effective_article,
                category=effective_category,
                city=selected_city,
                owner_user_id=str(current_user.id),
                preferred_url=effective_source_url,
            )

            create_audit_log(
                actor_user_id=current_user.id,
                actor_email=current_user.email,
                action="catalog.material_import_queued",
                entity_type="material_import_job",
                entity_id=primary_job["id"],
                details={
                    "article": effective_article,
                    "category": effective_category,
                    "city": selected_city,
                    "source_site": source_site,
                    "source_url": effective_source_url,
                    "is_default": is_default,
                },
            )

            return {
                "success": True,
                "item": item,
                "job": primary_job,
                "selected_city": selected_city,
                "error": "Material import queued. The system will update it in the background.",
            }

        cookie_override = await _resolve_viyar_cookie_for_user(current_user)

        try:
            material, prices_by_city = await _collect_material_prices_for_all_cities(
                article=effective_article,
                preferred_url=effective_source_url,
                cookie_override=cookie_override,
                selected_city=selected_city,
            )

            if not material:
                raise RuntimeError("Material details were not resolved")

            image_payload = prefetch_material_image_cache(
                article=material["article"],
                stored_image=material.get("image"),
                source_url=material.get("source_url") or effective_source_url,
                city=selected_city,
                cookie_override=cookie_override,
            )

            if not image_payload or not image_payload.get("bytes"):
                raise RuntimeError("Material image BLOB was not resolved")

            now = datetime.utcnow()
            item = upsert_material(
                article=material["article"],
                name=material["name"],
                description=material.get("description"),
                color=material.get("color"),
                dimensions=material.get("dimensions"),
                thickness=material.get("thickness"),
                category=effective_category,
                image=material.get("image"),
                source_url=material.get("source_url") or effective_source_url,
                owner_user_id=effective_owner_user_id,
                is_default=is_default,
                source=source_site,
                product_type=effective_category,
                image_source_url=image_payload.get("resolved_url") or material.get("image") or effective_source_url,
                imported_at=now,
                static_updated_at=now,
            )

            for city_code, price_value in prices_by_city.items():
                upsert_material_price(
                    article=material["article"],
                    city=city_code,
                    price=price_value,
                )

            update_material_image_cache(
                article=material["article"],
                image_bytes=image_payload["bytes"],
                content_type=image_payload["content_type"],
            )
            ensure_material_user_link(
                article=material["article"],
                user_id=str(current_user.id),
                source=source_site,
                product_type=effective_category,
                source_url=material.get("source_url") or effective_source_url,
            )
            item = get_material_by_article(material["article"]) or item

            item = _resolve_material_with_city_context(
                material["article"],
                selected_city,
                current_user,
                effective_category,
            ) or item

            if is_default:
                pass

            create_audit_log(
                actor_user_id=current_user.id,
                actor_email=current_user.email,
                action="catalog.material_created",
                entity_type="material",
                entity_id=item["article"],
                details={
                    "article": item["article"],
                    "category": effective_category,
                    "city": selected_city,
                    "source_url": item.get("source_url"),
                    "is_default": is_default,
                    "prices_cities_count": len(prices_by_city),
                },
            )

            return {
                "success": True,
                "item": item,
                "selected_city": selected_city,
                "error": None,
            }
        except Exception:
            item = upsert_material(
                article=effective_article,
                name=effective_name or effective_article,
                category=effective_category,
                image=payload.image_url,
                source_url=effective_source_url,
                owner_user_id=effective_owner_user_id,
                is_default=is_default,
                source=source_site,
                product_type=effective_category,
                image_source_url=payload.image_url,
            )
            item = _resolve_material_with_city_context(
                effective_article,
                selected_city,
                current_user,
                effective_category,
            ) or item

            primary_job = await enqueue_material_import_job(
                article=effective_article,
                category=effective_category,
                city=selected_city,
                owner_user_id=str(current_user.id),
                preferred_url=effective_source_url,
            )

            if is_default:
                for city_code in MATERIAL_CITY_COOKIES.keys():
                    if city_code == selected_city:
                        continue
                    try:
                        await enqueue_material_import_job(
                            article=effective_article,
                            category=effective_category,
                            city=city_code,
                            owner_user_id=str(current_user.id),
                            preferred_url=effective_source_url,
                        )
                    except Exception:
                        pass

            return {
                "success": True,
                "item": item,
                "job": primary_job,
                "selected_city": selected_city,
                "error": "Material import queued. The system will retry automatically.",
            }

    if is_default:
        return {
            "success": False,
            "error": "Default material must be added from a source link",
        }

    if not effective_name:
        return {
            "success": False,
            "error": "Material name is required for a manual material",
        }

    if payload.price is None:
        return {
            "success": False,
            "error": "Price is required for a manual material",
        }

    manual_article = effective_article or f"manual-{current_user.id}-{uuid4().hex[:12]}"

    existing_manual_item = get_material_by_article(
        manual_article,
        viewer_user_id=str(current_user.id),
        viewer_role=current_user.role,
    )
    if existing_manual_item and not _can_manage_material_item(current_user, existing_manual_item):
        return {
            "success": False,
            "error": "Material with this article already exists",
        }

    if not existing_manual_item:
        _ensure_material_ownership_capacity(current_user)

    item = upsert_material(
        article=manual_article,
        name=effective_name,
        category=effective_category,
        image=payload.image_url,
        source_url=None,
        owner_user_id=str(current_user.id),
        is_default=False,
        source="manual",
        product_type=effective_category,
        image_source_url=payload.image_url,
    )
    upsert_material_price(
        article=manual_article,
        city=selected_city,
        price=payload.price,
    )
    ensure_material_user_link(
        article=manual_article,
        user_id=str(current_user.id),
        source="manual",
        product_type=effective_category,
        source_url=None,
    )
    item = _resolve_material_with_city_context(
        manual_article,
        selected_city,
        current_user,
        effective_category,
    ) or item

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="catalog.material_created_manual",
        entity_type="material",
        entity_id=manual_article,
        details={
            "article": manual_article,
            "name": effective_name,
            "category": effective_category,
            "city": selected_city,
            "price": payload.price,
        },
    )

    return {
        "success": True,
        "item": item,
        "selected_city": selected_city,
    }


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

    existing_item = _find_material_import_match(
        source_url=payload.source_url,
        article=normalized_article,
        category=payload.category,
    )

    if not payload.force_refresh and existing_item and not material_needs_full_sync(existing_item):
        if not _can_manage_material_item(current_user, existing_item):
            return {
                "success": False,
                "error": "Material with this article already exists",
            }

        _ensure_material_feature_access(current_user, "materials.edit")
        item = _link_material_for_user(
            material=existing_item,
            current_user=current_user,
            source_url=payload.source_url,
        )
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
            "item": item,
            "selected_city": selected_city,
            "error": None,
        }

    if existing_item:
        if not _can_manage_material_item(current_user, existing_item):
            return {
                "success": False,
                "error": "Material with this article already exists",
            }

        _ensure_material_feature_access(current_user, "materials.edit")
    else:
        _ensure_material_feature_access(current_user, "materials.create")

    if not existing_item and current_user.role != "admin":
        _ensure_material_ownership_capacity(current_user)

    cookie_override = await _resolve_viyar_cookie_for_user(current_user)
    try:
        material, prices_by_city = await _collect_material_prices_for_all_cities(
            article=normalized_article,
            preferred_url=(payload.source_url or "").strip() or None,
            cookie_override=cookie_override,
            selected_city=selected_city,
        )

        if not material:
            raise RuntimeError("Material details were not resolved")

        image_payload = prefetch_material_image_cache(
            article=material["article"],
            stored_image=material.get("image"),
            source_url=material.get("source_url") or payload.source_url,
            city=selected_city,
            cookie_override=cookie_override,
        )

        if not image_payload or not image_payload.get("bytes"):
            raise RuntimeError("Material image BLOB was not resolved")

        now = datetime.utcnow()
        is_default = current_user.role == "admin"
        item = upsert_material(
            article=material["article"],
            name=material["name"],
            description=material.get("description"),
            color=material.get("color"),
            dimensions=material.get("dimensions"),
            thickness=material.get("thickness"),
            category=payload.category,
            image=material.get("image"),
            source_url=material.get("source_url") or payload.source_url,
            owner_user_id=None if is_default else str(current_user.id),
            is_default=is_default,
            source=detect_material_source_site(material.get("source_url") or payload.source_url),
            product_type=payload.category,
            image_source_url=image_payload.get("resolved_url") or material.get("image") or payload.source_url,
            imported_at=now,
            static_updated_at=now,
        )

        for city_code, price_value in prices_by_city.items():
            upsert_material_price(
                article=material["article"],
                city=city_code,
                price=price_value,
            )

        update_material_image_cache(
            article=material["article"],
            image_bytes=image_payload["bytes"],
            content_type=image_payload["content_type"],
        )

        ensure_material_user_link(
            article=material["article"],
            user_id=str(current_user.id),
            source=detect_material_source_site(material.get("source_url") or payload.source_url),
            product_type=payload.category,
            source_url=material.get("source_url") or payload.source_url,
        )

        item = get_material_by_article(
            material["article"],
            viewer_user_id=str(current_user.id),
            viewer_role=current_user.role,
        ) or item

        create_audit_log(
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            action="catalog.material_import_completed",
            entity_type="material",
            entity_id=item["article"],
            details={
                "article": item["article"],
                "city": selected_city,
                "source": item.get("source"),
                "prices_cities_count": len(prices_by_city),
            }
        )

        return {
            "success": True,
            "item": item,
            "selected_city": selected_city,
            "error": None,
        }
    except Exception as error:
        return {
            "success": False,
            "error": str(error),
            "selected_city": selected_city,
        }


@router.get(
    "/materials/import-jobs/{job_id}",
    response_model=MaterialCatalogOperationResponseSchema,
)
async def get_material_import_job_route(

    job_id: int,
    current_user = Depends(require_catalog_reader)
):

    _ensure_material_feature_access(current_user, "materials.view")

    job = get_material_import_job(job_id)

    if not job:
        return {
            "success": False,
            "error": "Material import job not found",
        }

    job_owner_user_id = str(job.get("owner_user_id") or "").strip()
    if job_owner_user_id and current_user.role != "admin" and job_owner_user_id != str(current_user.id):
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": "Material import job not found",
            },
        )

    item = None

    if job["status"] == "success":
        item = get_material_import_job_result(
            job["article"],
            job["city"],
            viewer_user_id=str(current_user.id),
            viewer_role=current_user.role,
        )

    return {
        "success": True,
        "job": job,
        "item": item,
        "selected_city": job["city"],
    }


@router.get(
    "/materials/{article}",
    response_model=MaterialCatalogOperationResponseSchema,
)
async def get_material_route(
    article: str,
    city: str | None = Query(default=None),
    current_user = Depends(require_catalog_reader),
):

    _ensure_material_feature_access(current_user, "materials.view")

    selected_city = (city or current_user.city or "").strip() or None
    item = _resolve_material_with_city_context(
        article.strip(),
        selected_city,
        current_user,
    )

    if not item:
        return {
            "success": False,
            "error": "Material not found",
        }

    return {
        "success": True,
        "item": item,
        "selected_city": selected_city,
    }


@router.patch(
    "/materials/{article}",
    response_model=MaterialCatalogOperationResponseSchema,
)
async def update_material_route(
    article: str,
    payload: MaterialCatalogUpdateSchema,
    current_user = Depends(require_material_editor),
):

    _ensure_material_feature_access(current_user, "materials.edit")

    normalized_article = article.strip()
    selected_city = (current_user.city or "").strip() or None
    existing_item = _resolve_material_with_city_context(
        normalized_article,
        selected_city,
        current_user,
    )

    if not existing_item:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": "Material not found",
            },
        )

    if not _can_manage_material_item(current_user, existing_item):
        if existing_item.get("is_default"):
            raise HTTPException(
                status_code=403,
                detail={
                    "success": False,
                    "error": "You do not have permission to edit this material",
                },
            )

        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": "Material not found",
            },
        )

    update_fields: dict[str, object] = {}
    provided_fields = set(payload.model_fields_set)

    if "name" in provided_fields:
        normalized_name = (payload.name or "").strip()
        if not normalized_name:
            raise HTTPException(
                status_code=422,
                detail={
                    "success": False,
                    "error": "Material name is required",
                },
            )
        update_fields["name"] = normalized_name

    if "description" in provided_fields:
        update_fields["description"] = (payload.description or "").strip() or None

    if "color" in provided_fields:
        update_fields["color"] = (payload.color or "").strip() or None

    if "dimensions" in provided_fields:
        update_fields["dimensions"] = (payload.dimensions or "").strip() or None

    if "thickness" in provided_fields:
        update_fields["thickness"] = (payload.thickness or "").strip() or None

    if "price" in provided_fields:
        if payload.price is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "success": False,
                    "error": "Price is required",
                },
            )

        if not selected_city:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "Select your city in profile settings first",
                },
            )

        update_fields["price"] = payload.price
        update_fields["price_city"] = selected_city

    if not update_fields:
        return {
            "success": True,
            "item": existing_item,
            "selected_city": selected_city,
            "error": None,
        }

    if not update_material(
        normalized_article,
        **update_fields,
    ):
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": "Material not found",
            },
        )

    updated_item = _resolve_material_with_city_context(
        normalized_article,
        selected_city,
        current_user,
    ) or existing_item

    return {
        "success": True,
        "item": updated_item,
        "selected_city": selected_city,
        "error": None,
    }


@router.post(
    "/materials/{article}/edges",
    response_model=MaterialEdgeOperationResponseSchema,
)
async def attach_material_edge_route(
    article: str,
    payload: MaterialEdgeAttachSchema,
    background_tasks: BackgroundTasks,
    current_user = Depends(require_material_editor),
):

    normalized_article = article.strip()
    selected_city = (payload.city or current_user.city or "").strip() or None
    material_item = _resolve_material_with_city_context(
        normalized_article,
        selected_city,
        current_user,
    )

    if not material_item:
        return {
            "success": False,
            "error": "Material not found",
        }

    if not _can_manage_material_item(current_user, material_item):
        return {
            "success": False,
            "error": "You do not have permission to edit this material",
        }

    _ensure_material_feature_access(current_user, "materials.edit")

    edge_key = (payload.edge_key or "").strip()

    if edge_key not in MATERIAL_EDGE_LABELS:
        return {
            "success": False,
            "error": "Unsupported edge type",
        }

    source_url = (payload.source_url or "").strip()
    if not source_url:
        return {
            "success": False,
            "error": "Edge source URL is required",
        }

    cookie_override = await _resolve_viyar_cookie_for_user(current_user)
    ordered_cities = []
    if selected_city:
        ordered_cities.append(selected_city)
    for city_code in MATERIAL_CITY_COOKIES.keys():
        if city_code not in ordered_cities:
            ordered_cities.append(city_code)

    edge_material = None
    prices_by_city: dict[str, float | None] = {}
    source_site = detect_material_source_site(source_url)

    if source_site == "viyar":
        for city_code in ordered_cities:
            try:
                parsed_edge, _debug_payload = await fetch_viyar_product_details_by_url_traced(
                    source_url,
                    city=city_code,
                    cookie_override=cookie_override,
                )
            except Exception:
                continue

            if not edge_material:
                edge_material = parsed_edge

            prices_by_city[city_code] = parsed_edge.get("price")
    else:
        metadata = await parse_fitting_source_metadata(source_url)
        if metadata.get("success"):
            edge_material = {
                "article": metadata.get("article"),
                "name": metadata.get("name"),
                "thickness": MATERIAL_EDGE_LABELS.get(edge_key),
                "image": metadata.get("image_url"),
                "price": metadata.get("price"),
                "source_url": metadata.get("final_url") or source_url,
                "source_site": metadata.get("source_site") or source_site,
            }
            prices_by_city = {
                city_code: edge_material.get("price")
                for city_code in ordered_cities
            }

    if not edge_material:
        return {
            "success": False,
            "error": "Unable to parse edge material by link",
        }

    edge_option = upsert_material_edge_option(
        material_article=normalized_article,
        edge_key=edge_key,
        article=edge_material.get("article"),
        name=edge_material.get("name"),
        thickness_label=MATERIAL_EDGE_LABELS.get(edge_key),
        image=edge_material.get("image"),
        source_url=edge_material.get("source_url") or source_url,
        source=source_site,
        product_type=edge_key,
        image_source_url=edge_material.get("image"),
        imported_at=datetime.utcnow(),
        static_updated_at=datetime.utcnow(),
    )

    for city_code, price_value in prices_by_city.items():
        upsert_material_edge_price(
            edge_option_id=edge_option["id"],
            city=city_code,
            price=price_value,
        )

    image_payload = resolve_material_image_payload(
        article=str(edge_material.get("article") or normalized_article).strip(),
        stored_image=edge_material.get("image"),
        source_url=edge_material.get("source_url") or source_url,
        city=selected_city,
        cookie_override=cookie_override,
    )

    if not image_payload or not image_payload.get("bytes"):
        return {
            "success": False,
            "error": "Unable to download edge image into local SQLite cache",
        }

    update_material_edge_image_cache(
        material_article=normalized_article,
        edge_key=edge_key,
        image_bytes=image_payload["bytes"],
        content_type=image_payload["content_type"],
    )

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="catalog.material_edge_attached",
        entity_type="material",
        entity_id=normalized_article,
        details={
            "material_article": normalized_article,
            "edge_key": edge_key,
            "edge_article": edge_material.get("article"),
            "source_url": source_url,
            "cities_count": len(prices_by_city),
        },
    )

    updated_item = _resolve_material_with_city_context(
        normalized_article,
        selected_city,
        current_user,
        material_item.get("category"),
    ) or material_item

    return {
        "success": True,
        "item": updated_item,
    }


@router.delete(
    "/materials/{article}",
    response_model=MaterialCatalogOperationResponseSchema,
)
async def delete_material_route(
    article: str,
    current_user = Depends(require_material_editor)
):

    existing_item = get_material_by_article(
        article.strip(),
        viewer_user_id=str(current_user.id),
        viewer_role=current_user.role,
    )

    if not existing_item:
        return {
            "success": False,
            "error": "Material not found",
        }

    if not _can_manage_material_item(current_user, existing_item):
        return {
            "success": False,
            "error": "You do not have permission to delete this material",
        }

    _ensure_material_feature_access(current_user, "materials.delete")

    result = delete_material(article.strip())

    if not result:
        return {
            "success": False,
            "error": "Material not found",
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

    background_tasks: BackgroundTasks,
    search: str | None = Query(default=None),
    city: str | None = Query(default=None),
    fitting_group: str | None = Query(default=None),
    fitting_type: str | None = Query(default=None),
    ownership_scope: str | None = Query(default=None),
    current_user = Depends(require_catalog_reader)
):
    _ensure_fitting_feature_access(current_user, "fittings.view")

    selected_city = city or current_user.city

    items = list_fittings(
        search=search,
        city=selected_city,
        viewer_user_id=current_user.id,
        viewer_role=current_user.role,
        fitting_group=fitting_group,
        fitting_type=fitting_type,
        ownership_scope=ownership_scope if current_user.role == "admin" else None,
    )
    # Прогрів картинок фурнітури тимчасово вимкнено для перевірки глобального блокування API.

    return {
        "success": True,
        "city_options": list_inventory_cities(),
        "selected_city": selected_city,
        "categories": list_fitting_categories(items, group=fitting_group),
        "items": items,
    }


@router.get(
    "/suppliers",
    response_model=FittingSupplierListResponseSchema,
)
async def list_fitting_suppliers_route(
    include_inactive: bool = Query(default=False),
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.view")

    return {
        "success": True,
        "items": list_suppliers(include_inactive=include_inactive),
    }


@router.get(
    "/fitting-manufacturers",
    response_model=FittingManufacturerListResponseSchema,
)
async def list_fitting_manufacturers_route(
    active_only: bool = Query(default=True),
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.view")

    return {
        "success": True,
        "items": list_fitting_manufacturers(active_only=active_only),
    }


@router.get(
    "/fitting-series",
    response_model=FittingSeriesListResponseSchema,
)
async def list_fitting_series_route(
    manufacturer_id: int | None = Query(default=None),
    active_only: bool = Query(default=True),
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.view")

    return {
        "success": True,
        "items": list_fitting_series(
            manufacturer_id=manufacturer_id,
            active_only=active_only,
        ),
    }


@router.get(
    "/fitting-categories",
    response_model=FittingCategoryListResponseSchema,
)
async def list_fitting_taxonomy_categories_route(
    parent_id: int | None = Query(default=None),
    active_only: bool = Query(default=True),
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.view")

    return {
        "success": True,
        "items": list_taxonomy_categories(
            parent_id=parent_id,
            active_only=active_only,
        ),
    }


@router.get(
    "/fitting-products",
    response_model=FittingProductListResponseSchema,
)
async def list_fitting_products_route(
    search: str | None = Query(default=None),
    manufacturer_id: int | None = Query(default=None),
    series_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    active_only: bool = Query(default=True),
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.view")

    return {
        "success": True,
        "items": list_fitting_products(
            search=search,
            manufacturer_id=manufacturer_id,
            series_id=series_id,
            category_id=category_id,
            active_only=active_only,
        ),
    }


@router.get(
    "/fitting-products/{item_id}",
    response_model=FittingProductDetailResponseSchema,
)
async def get_fitting_product_detail_route(
    item_id: str,
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.view")

    item = get_fitting_product_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Fitting product not found")

    return {
        "success": True,
        "item": item,
    }


def _normalize_admin_text(value: object | None) -> str:
    return " ".join(str(value or "").split()).strip()


def _category_has_descendant(*, category_id: int, target_id: int) -> bool:
    db = SessionLocal()
    try:
        current_parent_id = category_id
        seen: set[int] = set()

        while current_parent_id is not None and current_parent_id not in seen:
            if int(current_parent_id) == int(target_id):
                return True

            seen.add(int(current_parent_id))
            parent = (
                db.query(FittingCategoryModel.parent_id)
                .filter(FittingCategoryModel.id == int(current_parent_id))
                .first()
            )
            current_parent_id = int(parent[0]) if parent and parent[0] is not None else None

        return False
    finally:
        db.close()


def _category_has_child_categories(category_id: int) -> bool:
    db = SessionLocal()
    try:
        return (
            db.query(FittingCategoryModel.id)
            .filter(FittingCategoryModel.parent_id == int(category_id))
            .first()
            is not None
        )
    finally:
        db.close()


def _manufacturer_in_use(manufacturer_id: int) -> bool:
    db = SessionLocal()
    try:
        return (
            db.query(FittingSeriesModel.id)
            .filter(FittingSeriesModel.manufacturer_id == int(manufacturer_id))
            .first()
            is not None
        ) or (
            db.query(FittingProductModel.id)
            .filter(FittingProductModel.manufacturer_id == int(manufacturer_id))
            .first()
            is not None
        )
    finally:
        db.close()


def _series_in_use(series_id: int) -> bool:
    db = SessionLocal()
    try:
        return (
            db.query(FittingProductModel.id)
            .filter(FittingProductModel.series_id == int(series_id))
            .first()
            is not None
        )
    finally:
        db.close()


def _category_in_use(category_id: int) -> bool:
    db = SessionLocal()
    try:
        return (
            db.query(FittingProductModel.id)
            .filter(FittingProductModel.category_id == int(category_id))
            .first()
            is not None
        )
    finally:
        db.close()


@router.get(
    "/fitting-manufacturers/{item_id}",
    response_model=FittingManufacturerOperationResponseSchema,
)
async def get_fitting_manufacturer_detail_route(
    item_id: str,
    current_user = Depends(require_catalog_admin),
):
    item = get_fitting_manufacturer_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Fitting manufacturer not found")

    return {"success": True, "item": item}


@router.post(
    "/fitting-manufacturers",
    response_model=FittingManufacturerOperationResponseSchema,
)
async def create_fitting_manufacturer_route(
    payload: FittingManufacturerCreateSchema,
    current_user = Depends(require_catalog_admin),
):
    code = _normalize_admin_text(payload.code)
    name = _normalize_admin_text(payload.name)

    if not code:
        return {"success": False, "error": "Код виробника є обов'язковим"}

    if not name:
        return {"success": False, "error": "Назва виробника є обов'язковою"}

    db = SessionLocal()
    try:
        if (
            db.query(FittingManufacturerModel.id)
            .filter(FittingManufacturerModel.code == code)
            .first()
            is not None
        ):
            return {"success": False, "error": "Виробник з таким кодом уже існує"}
    finally:
        db.close()

    item = create_fitting_manufacturer(
        code=code,
        name=name,
        description=payload.description,
        website_url=payload.website_url,
        logo_url=payload.logo_url,
        country_code=payload.country_code,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )

    if not item:
        return {"success": False, "error": "Не вдалося створити виробника"}

    return {"success": True, "item": item}


@router.patch(
    "/fitting-manufacturers/{item_id}",
    response_model=FittingManufacturerOperationResponseSchema,
)
async def update_fitting_manufacturer_route(
    item_id: str,
    payload: FittingManufacturerUpdateSchema,
    current_user = Depends(require_catalog_admin),
):
    code = _normalize_admin_text(payload.code)
    name = _normalize_admin_text(payload.name)

    if not code:
        return {"success": False, "error": "Код виробника є обов'язковим"}

    if not name:
        return {"success": False, "error": "Назва виробника є обов'язковою"}

    db = SessionLocal()
    try:
        existing = db.get(FittingManufacturerModel, int(item_id))
        if not existing:
            return {"success": False, "error": "Виробника не знайдено"}

        duplicate = (
            db.query(FittingManufacturerModel.id)
            .filter(FittingManufacturerModel.code == code)
            .filter(FittingManufacturerModel.id != int(item_id))
            .first()
        )
        if duplicate:
            return {"success": False, "error": "Виробник з таким кодом уже існує"}
    finally:
        db.close()

    item = update_fitting_manufacturer(
        item_id,
        code=code,
        name=name,
        description=payload.description,
        website_url=payload.website_url,
        logo_url=payload.logo_url,
        country_code=payload.country_code,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )

    if not item:
        return {"success": False, "error": "Не вдалося оновити виробника"}

    return {"success": True, "item": item}


@router.delete(
    "/fitting-manufacturers/{item_id}",
    response_model=FittingManufacturerOperationResponseSchema,
)
async def delete_fitting_manufacturer_route(
    item_id: str,
    current_user = Depends(require_catalog_admin),
):
    item = get_fitting_manufacturer_by_id(item_id)
    if not item:
        return {"success": False, "error": "Виробника не знайдено"}

    if _manufacturer_in_use(int(item_id)):
        return {
            "success": False,
            "error": "Неможливо видалити виробника, бо він використовується у серіях або товарах",
        }

    deleted = delete_fitting_manufacturer(item_id)
    if not deleted:
        return {"success": False, "error": "Не вдалося видалити виробника"}

    return {"success": True, "item": deleted}


@router.get(
    "/fitting-series/{item_id}",
    response_model=FittingSeriesOperationResponseSchema,
)
async def get_fitting_series_detail_route(
    item_id: str,
    current_user = Depends(require_catalog_admin),
):
    item = get_fitting_series_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Fitting series not found")

    return {"success": True, "item": item}


@router.post(
    "/fitting-series",
    response_model=FittingSeriesOperationResponseSchema,
)
async def create_fitting_series_route(
    payload: FittingSeriesCreateSchema,
    current_user = Depends(require_catalog_admin),
):
    manufacturer_id = int(payload.manufacturer_id)
    code = _normalize_admin_text(payload.code)
    name = _normalize_admin_text(payload.name)

    if not code:
        return {"success": False, "error": "Код серії є обов'язковим"}

    if not name:
        return {"success": False, "error": "Назва серії є обов'язковою"}

    db = SessionLocal()
    try:
        if db.get(FittingManufacturerModel, manufacturer_id) is None:
            return {"success": False, "error": "Виробника не знайдено"}

        duplicate = (
            db.query(FittingSeriesModel.id)
            .filter(FittingSeriesModel.manufacturer_id == manufacturer_id)
            .filter(FittingSeriesModel.code == code)
            .first()
        )
        if duplicate:
            return {"success": False, "error": "Серія з таким кодом уже існує для цього виробника"}
    finally:
        db.close()

    item = create_fitting_series(
        manufacturer_id=manufacturer_id,
        code=code,
        name=name,
        description=payload.description,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )

    if not item:
        return {"success": False, "error": "Не вдалося створити серію"}

    return {"success": True, "item": item}


@router.patch(
    "/fitting-series/{item_id}",
    response_model=FittingSeriesOperationResponseSchema,
)
async def update_fitting_series_route(
    item_id: str,
    payload: FittingSeriesUpdateSchema,
    current_user = Depends(require_catalog_admin),
):
    manufacturer_id = int(payload.manufacturer_id)
    code = _normalize_admin_text(payload.code)
    name = _normalize_admin_text(payload.name)

    if not code:
        return {"success": False, "error": "Код серії є обов'язковим"}

    if not name:
        return {"success": False, "error": "Назва серії є обов'язковою"}

    db = SessionLocal()
    try:
        existing = db.get(FittingSeriesModel, int(item_id))
        if not existing:
            return {"success": False, "error": "Серію не знайдено"}

        if db.get(FittingManufacturerModel, manufacturer_id) is None:
            return {"success": False, "error": "Виробника не знайдено"}

        duplicate = (
            db.query(FittingSeriesModel.id)
            .filter(FittingSeriesModel.manufacturer_id == manufacturer_id)
            .filter(FittingSeriesModel.code == code)
            .filter(FittingSeriesModel.id != int(item_id))
            .first()
        )
        if duplicate:
            return {"success": False, "error": "Серія з таким кодом уже існує для цього виробника"}
    finally:
        db.close()

    item = update_fitting_series(
        item_id,
        manufacturer_id=manufacturer_id,
        code=code,
        name=name,
        description=payload.description,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )

    if not item:
        return {"success": False, "error": "Не вдалося оновити серію"}

    return {"success": True, "item": item}


@router.delete(
    "/fitting-series/{item_id}",
    response_model=FittingSeriesOperationResponseSchema,
)
async def delete_fitting_series_route(
    item_id: str,
    current_user = Depends(require_catalog_admin),
):
    item = get_fitting_series_by_id(item_id)
    if not item:
        return {"success": False, "error": "Серію не знайдено"}

    if _series_in_use(int(item_id)):
        return {
            "success": False,
            "error": "Неможливо видалити серію, бо вона використовується у товарах",
        }

    deleted = delete_fitting_series(item_id)
    if not deleted:
        return {"success": False, "error": "Не вдалося видалити серію"}

    return {"success": True, "item": deleted}


@router.get(
    "/fitting-categories/{item_id}",
    response_model=FittingTaxonomyCategoryOperationResponseSchema,
)
async def get_fitting_category_detail_route(
    item_id: str,
    current_user = Depends(require_catalog_admin),
):
    item = get_fitting_category_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Fitting category not found")

    return {"success": True, "item": item}


@router.post(
    "/fitting-categories",
    response_model=FittingTaxonomyCategoryOperationResponseSchema,
)
async def create_fitting_category_route(
    payload: FittingTaxonomyCategoryCreateSchema,
    current_user = Depends(require_catalog_admin),
):
    code = _normalize_admin_text(payload.code)
    name = _normalize_admin_text(payload.name)
    parent_id = payload.parent_id

    if not code:
        return {"success": False, "error": "Код категорії є обов'язковим"}

    if not name:
        return {"success": False, "error": "Назва категорії є обов'язковою"}

    db = SessionLocal()
    try:
        if (
            db.query(FittingCategoryModel.id)
            .filter(FittingCategoryModel.code == code)
            .first()
            is not None
        ):
            return {"success": False, "error": "Категорія з таким кодом уже існує"}

        if parent_id is not None:
            parent = db.get(FittingCategoryModel, int(parent_id))
            if parent is None:
                return {"success": False, "error": "Батьківську категорію не знайдено"}
    finally:
        db.close()

    item = create_fitting_category(
        code=code,
        name=name,
        parent_id=parent_id,
        description=payload.description,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )

    if not item:
        return {"success": False, "error": "Не вдалося створити категорію"}

    return {"success": True, "item": item}


@router.patch(
    "/fitting-categories/{item_id}",
    response_model=FittingTaxonomyCategoryOperationResponseSchema,
)
async def update_fitting_category_route(
    item_id: str,
    payload: FittingTaxonomyCategoryUpdateSchema,
    current_user = Depends(require_catalog_admin),
):
    code = _normalize_admin_text(payload.code)
    name = _normalize_admin_text(payload.name)
    parent_id = payload.parent_id

    if not code:
        return {"success": False, "error": "Код категорії є обов'язковим"}

    if not name:
        return {"success": False, "error": "Назва категорії є обов'язковою"}

    category_id = int(item_id)
    db = SessionLocal()
    try:
        existing = db.get(FittingCategoryModel, category_id)
        if not existing:
            return {"success": False, "error": "Категорію не знайдено"}

        duplicate = (
            db.query(FittingCategoryModel.id)
            .filter(FittingCategoryModel.code == code)
            .filter(FittingCategoryModel.id != category_id)
            .first()
        )
        if duplicate:
            return {"success": False, "error": "Категорія з таким кодом уже існує"}

        normalized_parent_id = int(parent_id) if parent_id is not None else None
        if normalized_parent_id is not None:
            if normalized_parent_id == category_id:
                return {"success": False, "error": "Категорія не може бути власною батьківською категорією"}

            parent = db.get(FittingCategoryModel, normalized_parent_id)
            if parent is None:
                return {"success": False, "error": "Батьківську категорію не знайдено"}

            if _category_has_descendant(category_id=normalized_parent_id, target_id=category_id):
                return {"success": False, "error": "Неможливо зробити категорію дочірньою для власного нащадка"}
    finally:
        db.close()

    item = update_fitting_category(
        item_id,
        code=code,
        name=name,
        parent_id=parent_id,
        description=payload.description,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )

    if not item:
        return {"success": False, "error": "Не вдалося оновити категорію"}

    return {"success": True, "item": item}


@router.delete(
    "/fitting-categories/{item_id}",
    response_model=FittingTaxonomyCategoryOperationResponseSchema,
)
async def delete_fitting_category_route(
    item_id: str,
    current_user = Depends(require_catalog_admin),
):
    item = get_fitting_category_by_id(item_id)
    if not item:
        return {"success": False, "error": "Категорію не знайдено"}

    category_id = int(item_id)
    if _category_has_child_categories(category_id):
        return {"success": False, "error": "Неможливо видалити категорію, бо вона має дочірні категорії"}

    if _category_in_use(category_id):
        return {"success": False, "error": "Неможливо видалити категорію, бо вона використовується у товарах"}

    deleted = delete_fitting_category(item_id)
    if not deleted:
        return {"success": False, "error": "Не вдалося видалити категорію"}

    return {"success": True, "item": deleted}


@router.patch(
    "/fitting-products/{item_id}/taxonomy",
    response_model=FittingProductTaxonomyOperationResponseSchema,
)
async def update_fitting_product_taxonomy_route(
    item_id: str,
    payload: FittingProductTaxonomyUpdateSchema,
    current_user = Depends(require_catalog_admin),
):
    product_id = int(item_id)
    manufacturer_id = payload.manufacturer_id
    series_id = payload.series_id
    category_id = payload.category_id
    is_active = payload.is_active

    db = SessionLocal()
    try:
        existing = db.get(FittingProductModel, product_id)
        if not existing:
            return {"success": False, "error": "Технічний продукт не знайдено"}

        manufacturer_row = None
        series_row = None
        category_row = None
        normalized_manufacturer_id = int(manufacturer_id) if manufacturer_id is not None else None
        normalized_series_id = int(series_id) if series_id is not None else None
        normalized_category_id = int(category_id) if category_id is not None else None
        existing_series_id = int(existing.series_id) if existing.series_id is not None else None
        effective_series_id = normalized_series_id

        if normalized_manufacturer_id is not None:
            manufacturer_row = db.get(FittingManufacturerModel, normalized_manufacturer_id)
            if manufacturer_row is None:
                return {"success": False, "error": "Виробника не знайдено"}

        if normalized_series_id is not None:
            series_row = db.get(FittingSeriesModel, normalized_series_id)
            if series_row is None:
                return {"success": False, "error": "Серію не знайдено"}
            if normalized_manufacturer_id is None:
                return {"success": False, "error": "Для серії потрібно вказати виробника"}
            if int(series_row.manufacturer_id) != int(normalized_manufacturer_id):
                return {"success": False, "error": "Серія має належати вибраному виробнику"}
        elif normalized_manufacturer_id is not None and existing_series_id is not None:
            existing_series = db.get(FittingSeriesModel, existing_series_id)
            if existing_series is not None and int(existing_series.manufacturer_id) != int(normalized_manufacturer_id):
                effective_series_id = None

        if normalized_category_id is not None:
            category_row = db.get(FittingCategoryModel, normalized_category_id)
            if category_row is None:
                return {"success": False, "error": "Категорію не знайдено"}

        item = update_fitting_product_taxonomy(
            product_id,
            manufacturer_id=normalized_manufacturer_id,
            series_id=effective_series_id,
            category_id=normalized_category_id,
            is_active=is_active,
        )
    finally:
        db.close()

    if not item:
        return {"success": False, "error": "Не вдалося оновити taxonomy технічного продукту"}

    return {"success": True, "item": item}


@router.get(
    "/fittings/{item_id}/supplier-offers",
    response_model=FittingSupplierOfferListResponseSchema,
)
async def list_fitting_supplier_offers_route(
    item_id: str,
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.view")

    fitting = get_fitting_by_id(
        item_id,
        viewer_user_id=current_user.id,
        viewer_role=current_user.role,
    )
    if not fitting:
        raise HTTPException(status_code=404, detail="Fitting not found")

    return {
        "success": True,
        "items": list_fitting_supplier_offers(item_id),
    }


@router.post(
    "/fittings/{item_id}/supplier-offers",
    response_model=FittingSupplierOfferOperationResponseSchema,
)
async def create_fitting_supplier_offer_route(
    item_id: str,
    payload: FittingSupplierOfferInputSchema,
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.edit")

    fitting = get_fitting_by_id(
        item_id,
        viewer_user_id=current_user.id,
        viewer_role=current_user.role,
    )
    if not fitting:
        raise HTTPException(status_code=404, detail="Fitting not found")

    if payload.supplier_id is None:
        return {
            "success": False,
            "error": "Supplier is required",
        }

    has_meaningful_offer_data = any(
        getattr(payload, field) not in (None, "", 0)
        for field in (
            "article",
            "external_product_id",
            "source_url",
            "price",
            "currency",
            "unit",
            "stock",
        )
    ) or payload.is_active is False or int(payload.priority or 0) != 100

    if not has_meaningful_offer_data:
        return {
            "success": False,
            "error": "Supplier offer data is required",
        }

    db = SessionLocal()
    try:
        fitting_model = db.query(FittingModel).filter(FittingModel.id == int(item_id)).first()
        if not fitting_model:
            raise HTTPException(status_code=404, detail="Fitting not found")

        supplier = (
            db.query(SupplierModel)
            .filter(SupplierModel.id == int(payload.supplier_id))
            .first()
        )
        if not supplier or not supplier.is_active:
            return {
                "success": False,
                "error": "Supplier not found or inactive",
            }

        foundation_repo = FittingFoundationRepository(db)
        offer = foundation_repo.create_offer(
            fitting_id=fitting_model.id,
            supplier_id=int(payload.supplier_id),
            article=payload.article,
            external_product_id=payload.external_product_id,
            source_url=payload.source_url,
            price=payload.price,
            currency=payload.currency,
            unit=payload.unit,
            stock=payload.stock,
            is_active=payload.is_active,
            priority=payload.priority,
        )
        if offer is None:
            return {
                "success": False,
                "error": "Unable to create supplier offer",
            }

        db.commit()
        db.refresh(offer)
        offer.supplier = supplier
        return {
            "success": True,
            "item": _serialize_fitting_supplier_offer(offer),
        }
    except Exception as error:
        db.rollback()
        logger.exception("Fitting supplier offer create failed")
        return {
            "success": False,
            "error": str(error) or "Unable to create supplier offer",
        }
    finally:
        db.close()


@router.put(
    "/fittings/{item_id}/supplier-offers/{offer_id}",
    response_model=FittingSupplierOfferOperationResponseSchema,
)
async def update_fitting_supplier_offer_route(
    item_id: str,
    offer_id: str,
    payload: FittingSupplierOfferInputSchema,
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.edit")

    fitting = get_fitting_by_id(
        item_id,
        viewer_user_id=current_user.id,
        viewer_role=current_user.role,
    )
    if not fitting:
        raise HTTPException(status_code=404, detail="Fitting not found")

    db = SessionLocal()
    try:
        fitting_model = db.query(FittingModel).filter(FittingModel.id == int(item_id)).first()
        if not fitting_model:
            raise HTTPException(status_code=404, detail="Fitting not found")

        foundation_repo = FittingFoundationRepository(db)
        offer = foundation_repo.get_offer_by_id(int(offer_id))
        if not offer or int(offer.fitting_id) != int(fitting_model.id):
            return {
                "success": False,
                "error": "Supplier offer not found",
            }

        if payload.supplier_id is not None:
            supplier = (
                db.query(SupplierModel)
                .filter(SupplierModel.id == int(payload.supplier_id))
                .first()
            )
            if not supplier:
                return {
                    "success": False,
                    "error": "Supplier not found",
                }
        else:
            supplier = db.query(SupplierModel).filter(SupplierModel.id == int(offer.supplier_id)).first()

        updated_offer = foundation_repo.update_offer(
            offer,
            supplier_id=int(payload.supplier_id) if payload.supplier_id is not None else int(offer.supplier_id),
            article=payload.article,
            external_product_id=payload.external_product_id,
            source_url=payload.source_url,
            price=payload.price,
            currency=payload.currency,
            unit=payload.unit,
            stock=payload.stock,
            is_active=payload.is_active,
            priority=payload.priority,
        )

        db.commit()
        db.refresh(updated_offer)
        if supplier is not None:
            updated_offer.supplier = supplier

        return {
            "success": True,
            "item": _serialize_fitting_supplier_offer(updated_offer),
        }
    except Exception as error:
        db.rollback()
        logger.exception("Fitting supplier offer update failed")
        return {
            "success": False,
            "error": str(error) or "Unable to update supplier offer",
        }
    finally:
        db.close()


@router.get("/fittings/{item_id}/image")
async def get_fitting_image_route(
    item_id: str,
    access_token: str | None = Query(default=None),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    current_user = Depends(optional_current_user),
):
    authorized_user = current_user

    if not authorized_user and access_token:
        authorized_user = get_user_from_token(access_token)

    _ensure_fitting_feature_access(authorized_user, "fittings.view")

    fitting = get_fitting_by_id(
        item_id,
        viewer_user_id=getattr(authorized_user, "id", None),
        viewer_role=getattr(authorized_user, "role", "free") if authorized_user else "free",
    )

    if not fitting:
        return Response(status_code=404)

    fitting_image = get_fitting_image_by_id(item_id)

    if fitting_image and fitting_image.get("image_cached_bytes"):
        return _image_response(
            fitting_image["image_cached_bytes"],
            fitting_image.get("image_cached_content_type"),
            if_none_match,
        )
    return Response(status_code=404)


@router.get("/fittings/{item_id}/images/{image_id}")
async def get_fitting_gallery_image_route(
    item_id: str,
    image_id: str,
    access_token: str | None = Query(default=None),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    current_user = Depends(optional_current_user),
):
    authorized_user = current_user

    if not authorized_user and access_token:
        authorized_user = get_user_from_token(access_token)

    _ensure_fitting_feature_access(authorized_user, "fittings.view")

    fitting = get_fitting_by_id(
        item_id,
        viewer_user_id=getattr(authorized_user, "id", None),
        viewer_role=getattr(authorized_user, "role", "free") if authorized_user else "free",
    )

    if not fitting:
        return Response(status_code=404)

    fitting_image = get_fitting_image(item_id, image_id)

    if not fitting_image:
        return Response(status_code=404)

    return _image_response(
        fitting_image["image_cached_bytes"],
        fitting_image.get("image_cached_content_type"),
        if_none_match,
    )


@router.get(
    "/fittings/{item_id}",
    response_model=FittingCatalogDetailResponseSchema,
)
async def get_fitting_detail_route(
    item_id: str,
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.view")

    fitting = get_fitting_by_id(
        item_id,
        viewer_user_id=current_user.id,
        viewer_role=current_user.role,
    )

    if not fitting:
        raise HTTPException(status_code=404, detail="Fitting not found")

    item = _load_fitting_detail_item(item_id, current_user=current_user)
    if not item:
        raise HTTPException(status_code=404, detail="Fitting not found")

    return {
        "success": True,
        "item": item,
    }


def _can_manage_fitting_item(current_user, item: dict | None) -> bool:

    if not item:
        return False

    if current_user.role == "admin":
        return True

    return (
        not item.get("is_system") and
        item.get("owner_user_id") == str(current_user.id)
    )


@router.post(
    "/fittings",
    response_model=FittingCatalogOperationResponseSchema,
)
async def create_fitting_route(
    payload: FittingCatalogCreateSchema,
    background_tasks: BackgroundTasks,
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.create")

    if payload.is_system and current_user.role != "admin":
        return {
            "success": False,
            "error": "Only admin can create system fittings",
        }

    is_system = current_user.role == "admin"

    effective_name = (payload.name or "").strip()
    effective_image_url = payload.image_url
    effective_source_url = (payload.source_url or "").strip() or None
    effective_article = (payload.article or "").strip() or None
    effective_code = (payload.code or "").strip() or None
    effective_price = payload.price
    effective_stock = (payload.stock or "").strip() or None
    effective_source = None
    effective_brand = None
    effective_description = None
    source_payload: dict | None = None
    technical_product_payload: dict | None = None
    prepared_gallery_images = None
    selected_city = (payload.city or current_user.city or "").strip() or None
    if not effective_source_url and _looks_like_url(effective_name):
        effective_source_url = effective_name
        effective_name = ""
    source_site = detect_material_source_site(effective_source_url) if effective_source_url else "manual"

    if effective_source_url:
        if source_site == "viyar":
            metadata, error_response = await _parse_fitting_source_or_error(effective_source_url)
            if error_response:
                return error_response

            effective_name = metadata.get("name") or effective_name
            effective_image_url = metadata.get("image_url") or effective_image_url
            effective_source_url = metadata.get("final_url") or effective_source_url
            effective_article = effective_article or metadata.get("article")
            effective_price = metadata.get("price") if metadata.get("price") is not None else effective_price
            effective_source = (metadata.get("source_site") or "").strip() or None
            effective_brand = (metadata.get("brand") or "").strip() or None
            if not effective_stock:
                effective_stock = (metadata.get("availability") or "").strip() or None
            effective_description = metadata.get("description") or effective_description
            source_payload = {
                "source_site": source_site,
                "source_url": effective_source_url,
                "selected_city": selected_city,
                "parsed_item": metadata,
            }
            technical_product_payload = {
                "article": effective_article,
                "code": effective_code or effective_article,
                "name": effective_name or effective_article or effective_code or "",
                "brand": effective_brand,
                "description": effective_description,
                "manufacturer_id": None,
                "series_id": None,
                "category_id": None,
                "is_active": bool(payload.is_active),
            }

            metadata_image_urls = metadata.get("image_urls") or []
            if not metadata_image_urls:
                logger.warning(
                    "Fitting gallery import failed: source returned no image_urls",
                    extra={
                        "source_url": effective_source_url,
                        "source_site": source_site,
                    },
                )
                return {
                    "success": False,
                    "error": "Не вдалося отримати дані за посиланням. Перевірте посилання або спробуйте пізніше.",
                }

            try:
                prepared_gallery_images = prepare_fitting_gallery_images(
                    normalize_fitting_gallery_image_urls(metadata_image_urls),
                    fetcher=lambda source_url: fetch_remote_image_payload(
                        source_url,
                        city=selected_city,
                    ),
                )
            except FittingGalleryPreparationError as error:
                logger.warning(
                    "Fitting gallery import failed",
                    extra={
                        "source_url": effective_source_url,
                        "source_site": source_site,
                        "error": str(error),
                    },
                )
                return {
                    "success": False,
                    "error": "Не вдалося отримати дані за посиланням. Перевірте посилання або спробуйте пізніше.",
                }

            effective_image_url = prepared_gallery_images[0].source_url
        else:
            metadata, error_response = await _parse_fitting_source_or_error(effective_source_url)
            if error_response:
                return error_response

            effective_name = metadata.get("name") or effective_name
            effective_source_url = metadata.get("final_url") or effective_source_url
            effective_article = effective_article or metadata.get("article")
            effective_price = metadata.get("price") if metadata.get("price") is not None else effective_price
            effective_source = (metadata.get("source_site") or "").strip() or None
            effective_brand = (metadata.get("brand") or "").strip() or None
            if not effective_stock:
                effective_stock = (metadata.get("availability") or "").strip() or None
            effective_description = metadata.get("description") or effective_description
            source_payload = {
                "source_site": source_site,
                "source_url": effective_source_url,
                "selected_city": selected_city,
                "parsed_item": metadata,
            }
            technical_product_payload = {
                "article": effective_article,
                "code": effective_code or effective_article,
                "name": effective_name or effective_article or effective_code or "",
                "brand": effective_brand,
                "description": effective_description,
                "manufacturer_id": None,
                "series_id": None,
                "category_id": None,
                "is_active": bool(payload.is_active),
            }
            metadata_image_urls = metadata.get("image_urls") or []

            if not metadata_image_urls:
                logger.warning(
                    "Fitting gallery import failed: source returned no image_urls",
                    extra={
                        "source_url": effective_source_url,
                        "source_site": source_site,
                    },
                )
                return {
                    "success": False,
                    "error": "Не вдалося отримати дані за посиланням. Перевірте посилання або спробуйте пізніше.",
                }

            try:
                prepared_gallery_images = prepare_fitting_gallery_images(
                    normalize_fitting_gallery_image_urls(metadata_image_urls),
                    fetcher=lambda source_url: fetch_remote_image_payload(
                        source_url,
                        city=selected_city,
                    ),
                )
            except FittingGalleryPreparationError as error:
                logger.warning(
                    "Fitting gallery import failed",
                    extra={
                        "source_url": effective_source_url,
                        "source_site": source_site,
                        "error": str(error),
                    },
                )
                return {
                    "success": False,
                    "error": "Не вдалося отримати дані за посиланням. Перевірте посилання або спробуйте пізніше.",
                }

            effective_image_url = prepared_gallery_images[0].source_url

    if not effective_name and effective_article:
        effective_name = effective_article

    if effective_source_url and not effective_name.strip():
        return {
            "success": False,
            "error": "Не вдалося отримати дані за посиланням. Перевірте посилання або спробуйте пізніше.",
        }

    if not effective_name.strip():
        return {
            "success": False,
            "error": "Fitting name is required",
        }

    owner_user_id = None if is_system else str(current_user.id)

    try:
        item = create_fitting(
            city=selected_city,
            code=effective_code,
            article=effective_article,
            name=effective_name,
            description=effective_description,
            price=effective_price,
            stock=effective_stock,
            source=effective_source,
            brand=effective_brand,
            fitting_type=payload.fitting_type,
            fitting_group=payload.fitting_group,
            image_url=effective_image_url,
            source_url=effective_source_url,
            source_payload_json=json.dumps(source_payload, ensure_ascii=False) if source_payload else None,
            owner_user_id=owner_user_id,
            is_system=is_system,
            is_active=payload.is_active,
            sort_order=payload.sort_order,
            technical_product=technical_product_payload,
            supplier_offer=payload.supplier_offer.model_dump() if payload.supplier_offer else None,
            prepared_gallery_images=prepared_gallery_images,
        )
    except Exception as error:
        logger.exception("Fitting create failed")
        return {
            "success": False,
            "error": str(error) or "Unable to create fitting",
        }

    if not prepared_gallery_images and item.get("image_url") and _claim_fitting_image_warm(item.get("id")):
        background_tasks.add_task(_warm_fitting_image_cache_task, item)

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
        "item": _load_fitting_detail_item(item["id"], current_user=current_user) or item,
    }


@router.put(
    "/fittings/{item_id}",
    response_model=FittingCatalogOperationResponseSchema,
)
async def update_fitting_route(
    item_id: str,
    payload: FittingCatalogUpdateSchema,
    background_tasks: BackgroundTasks,
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.edit")

    existing_item = get_fitting_by_id(
        item_id,
        viewer_user_id=str(current_user.id),
        viewer_role=current_user.role,
    )

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

    owner_user_id = existing_item.get("owner_user_id")
    is_system = bool(existing_item.get("is_system"))
    selected_city = (payload.city or current_user.city or "").strip() or None

    effective_name = (payload.name or "").strip()
    effective_image_url = payload.image_url
    effective_source_url = (payload.source_url or "").strip() or None
    effective_article = (payload.article or "").strip() or None
    effective_price = payload.price
    effective_stock = payload.stock
    effective_description = None
    source_payload: dict | None = None
    if not effective_source_url and _looks_like_url(effective_name):
        effective_source_url = effective_name
        effective_name = ""
    source_site = detect_material_source_site(effective_source_url) if effective_source_url else "manual"

    if effective_source_url:
        if source_site == "viyar":
            ordered_cities: list[str] = []
            if selected_city:
                ordered_cities.append(selected_city)
            for city_code in MATERIAL_CITY_COOKIES.keys():
                if city_code not in ordered_cities:
                    ordered_cities.append(city_code)

            city_prices: dict[str, float | None] = {}
            first_result: dict | None = None

            for city_code in ordered_cities:
                try:
                    parsed_result, _debug_payload = await fetch_viyar_product_details_by_url_traced(
                        effective_source_url,
                        city=city_code,
                    )
                except Exception:
                    continue

                if parsed_result and parsed_result.get("name") and first_result is None:
                    first_result = parsed_result

                city_prices[city_code] = parsed_result.get("price") if parsed_result else None

            if first_result:
                selected_price = city_prices.get(selected_city) if selected_city else None
                effective_name = first_result.get("name") or effective_name
                effective_image_url = first_result.get("image") or effective_image_url
                effective_source_url = first_result.get("source_url") or effective_source_url
                effective_article = effective_article or first_result.get("article")
                effective_price = selected_price if selected_price is not None else first_result.get("price")
                effective_description = first_result.get("description") or effective_description
                source_payload = {
                    "source_site": source_site,
                    "source_url": effective_source_url,
                    "selected_city": selected_city,
                    "city_prices": city_prices,
                    "parsed_item": first_result,
                }
        else:
            metadata, error_response = await _parse_fitting_source_or_error(effective_source_url)
            if error_response:
                return error_response

            effective_name = metadata.get("name") or effective_name
            effective_image_url = metadata.get("image_url") or effective_image_url
            effective_source_url = metadata.get("final_url") or effective_source_url
            effective_article = effective_article or metadata.get("article")
            effective_price = metadata.get("price") if metadata.get("price") is not None else effective_price
            effective_description = metadata.get("description") or effective_description
            source_payload = {
                "source_site": source_site,
                "source_url": effective_source_url,
                "selected_city": selected_city,
                "parsed_item": metadata,
            }

    if not effective_name and effective_article:
        effective_name = effective_article

    if effective_source_url and not effective_name.strip():
        return {
            "success": False,
            "error": "Unable to parse fitting from source link",
        }

    try:
        item = update_fitting(
            item_id=item_id,
            city=selected_city,
            code=payload.code,
            article=effective_article,
            name=effective_name,
            description=effective_description,
            price=effective_price,
            stock=effective_stock,
            fitting_type=payload.fitting_type,
            fitting_group=payload.fitting_group,
            image_url=effective_image_url,
            source_url=effective_source_url,
            source_payload_json=json.dumps(source_payload, ensure_ascii=False) if source_payload else None,
            owner_user_id=owner_user_id,
            is_system=is_system,
            is_active=payload.is_active,
            sort_order=payload.sort_order,
            supplier_offer=payload.supplier_offer.model_dump() if payload.supplier_offer else None,
        )
    except Exception as error:
        logger.exception("Fitting update failed")
        return {
            "success": False,
            "error": str(error) or "Unable to update fitting",
        }

    if item and item.get("image_url") and not item.get("has_cached_image"):
        if _claim_fitting_image_warm(item.get("id")):
            background_tasks.add_task(_warm_fitting_image_cache_task, item)

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
        "item": _load_fitting_detail_item(item["id"], current_user=current_user) or item,
    }


@router.delete(
    "/fittings/{item_id}",
    response_model=FittingCatalogOperationResponseSchema,
)
async def delete_fitting_route(
    item_id: str,
    current_user = Depends(require_catalog_reader),
):
    _ensure_fitting_feature_access(current_user, "fittings.delete")

    existing_item = get_fitting_by_id(
        item_id,
        viewer_user_id=str(current_user.id),
        viewer_role=current_user.role,
    )

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

    dependent_nodes = list_fitting_delete_dependencies(item_id)
    if dependent_nodes:
        node_labels = []
        for node in dependent_nodes:
            node_name = str(node.get("name") or "").strip() or str(node.get("code") or "").strip()
            node_id = str(node.get("id") or "").strip()
            if node_name and node_id:
                node_labels.append(f"{node_name} (ID {node_id})")
            elif node_name:
                node_labels.append(node_name)
            elif node_id:
                node_labels.append(f"ID {node_id}")

        return {
            "success": False,
            "error": (
                "Неможливо видалити фурнітуру. "
                "Вона використовується в монтажних вузлах: "
                + "; ".join(node_labels)
                + ". Спочатку замініть цю фурнітуру у зазначених вузлах, збережіть вузли та повторіть видалення."
            ),
            "dependent_nodes": dependent_nodes,
        }

    result = delete_fitting(item_id)

    if not result or not result.get("success"):
        return {
            "success": False,
            "error": "Unable to delete fitting",
        }

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="catalog.fitting_deleted",
        entity_type="fitting",
        entity_id=item_id,
        details=result,
    )

    return result


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
    description_audit = get_viyar_service_description_audit(
        include_inactive=include_inactive,
    )

    return {
        "success": True,
        "source": "viyar",
        "description_audit": description_audit,
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
            "import_audit": result.get("import_audit", {}),
            "description_audit": result.get("description_audit", {}),
            "description_backfill_audit": result.get("description_backfill_audit", {}),
        }
    )

    return {
        "success": True,
        "source": "viyar",
        "imported_count": result["imported_count"],
        "folder_count": result["folder_count"],
        "service_count": result["service_count"],
        "fallback_only_import": result.get("fallback_only_import", False),
        "import_audit": result.get("import_audit"),
        "description_audit": result.get("description_audit"),
        "description_backfill_audit": result.get("description_backfill_audit"),
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
