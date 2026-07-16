import asyncio

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
    CatalogItemUpdateSchema,
    ManualServiceCatalogItemCreateSchema,
    ManualServiceCatalogItemUpdateSchema,
    MaterialCatalogCreateSchema,
    MaterialEdgeAttachSchema,
    MaterialEdgeOperationResponseSchema,
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
from database.models.fitting import (
    FittingModel,
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
    create_fitting,
    delete_fitting,
    delete_material,
    get_fitting_image,
    get_fitting_by_id,
    get_fitting_image_by_id,
    get_material_by_import_identity,
    get_material_edge_image,
    get_material_by_article,
    list_fitting_images,
    list_fittings,
    list_fitting_categories,
    list_inventory_cities,
    list_material_categories,
    list_materials,
    _serialize_fitting,
    upsert_material,
    upsert_material_edge_option,
    upsert_material_edge_price,
    upsert_material_price,
    material_needs_full_sync,
    update_fitting,
    update_fitting_image_cache,
    update_material_edge_image_cache,
    update_material_image_cache,
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
from services.auth_service import (
    get_user_from_token,
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


def _normalize_fitting_detail_text(value: object | None) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


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
    source_payload = _safe_parse_source_payload_json(item.source_payload_json)
    parsed_item = source_payload.get("parsed_item") if isinstance(source_payload, dict) else {}
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
        "premium",
        "pro",
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

    if current_user.role not in ("admin", "premium", "pro"):
        return False

    if item.get("is_default"):
        return True

    return item.get("owner_user_id") == str(current_user.id)


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
        get_material_by_article(normalized_article),
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
    current_user = Depends(require_catalog_reader)
):

    selected_city = city or current_user.city
    items = list_materials(
        search=search,
        category=category,
        city=selected_city,
        viewer_user_id=str(current_user.id),
        viewer_role=current_user.role,
    )

    # Прогрів картинок тимчасово вимкнено для діагностики швидкодії.

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

    is_default = bool(payload.is_default)

    if is_default and current_user.role not in ("admin", "premium", "pro"):
        return {
            "success": False,
            "error": "Only admin, Premium or PRO can create default materials",
        }

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

    if effective_source_url:
        if not effective_article:
            return {
                "success": False,
                "error": "Article is required when adding material from a link",
            }

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
            owner_user_id=str(current_user.id),
            is_default=False,
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


@router.get(
    "/materials/{article}",
    response_model=MaterialCatalogOperationResponseSchema,
)
async def get_material_route(
    article: str,
    city: str | None = Query(default=None),
    current_user = Depends(require_catalog_reader),
):

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

    if current_user.role != "admin" and not item.get("is_default") and item.get("owner_user_id") != str(current_user.id):
        return {
            "success": False,
            "error": "Material not found",
        }

    return {
        "success": True,
        "item": item,
        "selected_city": selected_city,
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
    # Прогрів картинок фурнітури тимчасово вимкнено для перевірки глобального блокування API.

    return {
        "success": True,
        "city_options": list_inventory_cities(),
        "selected_city": selected_city,
        "categories": list_fitting_categories(items, group=fitting_group),
        "items": items,
    }


@router.get("/fittings/{item_id}/image")
async def get_fitting_image_route(
    item_id: str,
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
):
    fitting = get_fitting_image_by_id(item_id)

    if not fitting:
        return Response(status_code=404)

    if fitting.get("image_cached_bytes"):
        return _image_response(
            fitting["image_cached_bytes"],
            fitting.get("image_cached_content_type"),
            if_none_match,
        )
    return Response(status_code=404)


@router.get("/fittings/{item_id}/images/{image_id}")
async def get_fitting_gallery_image_route(
    item_id: str,
    image_id: str,
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
):
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

    db = SessionLocal()
    try:
        item = (
            db.query(FittingModel)
            .filter(FittingModel.id == int(item_id))
            .first()
        )
        if not item:
            raise HTTPException(status_code=404, detail="Fitting not found")

        serialized_item = _serialize_fitting_detail(item)
        serialized_item["images"] = list_fitting_images(item_id)

        return {
            "success": True,
            "item": serialized_item,
        }
    finally:
        db.close()


def _can_manage_fitting_item(current_user, item: dict | None) -> bool:

    if not item:
        return False

    if current_user.role == "admin":
        return True

    return (
        current_user.role in ("premium", "pro") and
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
    effective_description = None
    source_payload: dict | None = None
    selected_city = (payload.city or current_user.city or "").strip() or None
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
            metadata = await parse_fitting_source_metadata(effective_source_url)
            if metadata.get("success"):
                effective_name = metadata.get("name") or effective_name
                effective_image_url = metadata.get("image_url") or effective_image_url
                effective_source_url = metadata.get("final_url") or effective_source_url
                effective_article = effective_article or metadata.get("article")
                effective_price = metadata.get("price") if metadata.get("price") is not None else effective_price
                effective_description = metadata.get("description") or effective_description
                source_payload = metadata

    if not effective_name and effective_article:
        effective_name = effective_article

    if effective_source_url and not effective_name.strip():
        return {
            "success": False,
            "error": "Unable to parse fitting from source link",
        }

    if not effective_name.strip():
        return {
            "success": False,
            "error": "Fitting name is required",
        }

    owner_user_id = None if payload.is_system else str(current_user.id)

    item = create_fitting(
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
        is_system=payload.is_system,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )

    if item.get("image_url") and _claim_fitting_image_warm(item.get("id")):
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
        "item": item,
    }


@router.put(
    "/fittings/{item_id}",
    response_model=FittingCatalogOperationResponseSchema,
)
async def update_fitting_route(
    item_id: str,
    payload: FittingCatalogUpdateSchema,
    background_tasks: BackgroundTasks,
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
            metadata = await parse_fitting_source_metadata(effective_source_url)
            if metadata.get("success"):
                effective_name = metadata.get("name") or effective_name
                effective_image_url = metadata.get("image_url") or effective_image_url
                effective_source_url = metadata.get("final_url") or effective_source_url
                effective_article = effective_article or metadata.get("article")
                effective_price = metadata.get("price") if metadata.get("price") is not None else effective_price
                effective_description = metadata.get("description") or effective_description
                source_payload = metadata

    if not effective_name and effective_article:
        effective_name = effective_article

    if effective_source_url and not effective_name.strip():
        return {
            "success": False,
            "error": "Unable to parse fitting from source link",
        }

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
        is_system=payload.is_system,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )

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
