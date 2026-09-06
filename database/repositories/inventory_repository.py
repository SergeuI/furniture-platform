from collections import defaultdict
import json
from hashlib import sha256
from datetime import date, datetime, timedelta
import re
from typing import Sequence
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import load_only, object_session, selectinload

from database.models.fitting import (
    FittingModel,
    FittingHolePointModel,
    FittingHoleTemplateModel,
    FittingCategoryModel,
    FittingManufacturerModel,
    FittingProductModel,
    FittingSupplierOfferModel,
    SupplierModel,
)
from database.models.fitting_image import (
    FittingImageModel,
)
from database.models.mounting_node import (
    MountingNodeItemModel,
    MountingNodeModel,
    MountingNodeTemplateModel,
)
from database.models.material import (
    MaterialModel,
)
from database.models.material_image import (
    MaterialImageModel,
)
from database.models.material_edge import (
    MaterialEdgeModel,
)
from database.models.material_edge_price import (
    MaterialEdgePriceModel,
)
from database.models.canonical_edge import (
    CanonicalEdgeModel,
    EdgeSupplierOfferModel,
    EdgeSupplierOfferPriceModel,
    MaterialEdgeRelationModel,
)
from database.models.material_price import (
    MaterialPriceModel,
)
from database.models.material_supplier_offer import (
    MaterialSupplierOfferModel,
)
from database.models.material_taxonomy import (
    MaterialManufacturerModel,
)
from database.models.material_user_link import (
    MaterialUserLinkModel,
)
from database.models.user import (
    UserModel,
)
from database.session import (
    SessionLocal,
)
from database.repositories.fitting_foundation_repository import (
    FittingFoundationRepository,
)
from services.fitting_image_gallery_service import (
    PreparedFittingGalleryImage,
)
from services.material_catalog_service import (
    is_material_gallery_candidate_url,
    normalize_material_gallery_image_url,
)


_FITTINGS_CATALOG_KEY_COLUMN_CACHE: dict[int, bool] = {}


_UNSET = object()


def _normalize_price_value(value) -> float | None:

    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        return float(value)

    normalized = str(value).strip().replace(" ", "").replace(",", ".")

    try:
        return float(normalized)
    except ValueError:
        return None


def _normalize_source(value: str | None) -> str | None:

    normalized = str(value or "").strip()

    return normalized or None


def _normalize_material_price_summary_unit(value: str | None) -> str | None:

    normalized = _normalize_source(value)
    if not normalized:
        return None

    candidate = normalized.replace("\u00a0", " ").strip()
    if "/" in candidate:
        prefix, suffix = candidate.split("/", 1)
        prefix_key = prefix.strip().casefold()
        suffix_value = _normalize_source(suffix)
        if prefix_key in {"₴", "грн", "uah"} and suffix_value:
            return suffix_value

    return candidate


def _safe_parse_supplier_offer_payload_json(value: object | None) -> dict[str, object]:

    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    raw_text = _normalize_source(value)
    if not raw_text:
        return {}

    try:
        parsed = json.loads(raw_text)
    except Exception:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _extract_supplier_offer_square_meter_support(offer: MaterialSupplierOfferModel) -> bool | None:

    payload = _safe_parse_supplier_offer_payload_json(getattr(offer, "source_payload_json", None))
    if not payload:
        return None

    parsed_material = payload.get("parsed_material")
    if isinstance(parsed_material, dict):
        parsed_flag = parsed_material.get("supports_square_meter_sale")
        if parsed_flag is not None:
            return bool(parsed_flag)

    direct_flag = payload.get("supports_square_meter_sale")
    if direct_flag is not None:
        return bool(direct_flag)

    return None


def _extract_supplier_offer_characteristics(offer: MaterialSupplierOfferModel) -> dict[str, str]:

    payload = _safe_parse_supplier_offer_payload_json(getattr(offer, "source_payload_json", None))
    parsed_material = payload.get("parsed_material")
    raw_characteristics = (
        parsed_material.get("characteristics")
        if isinstance(parsed_material, dict)
        else payload.get("characteristics")
    )
    if not isinstance(raw_characteristics, dict):
        return {}

    return {
        key: value
        for raw_key, raw_value in raw_characteristics.items()
        if (key := _normalize_source(raw_key)) and (value := _normalize_source(raw_value))
    }


def _extract_supplier_offer_image_urls(offer: MaterialSupplierOfferModel) -> list[str]:
    payload = _safe_parse_supplier_offer_payload_json(getattr(offer, "source_payload_json", None))
    parsed_material = payload.get("parsed_material")
    raw_image_urls = parsed_material.get("image_urls") if isinstance(parsed_material, dict) else []
    if not isinstance(raw_image_urls, list):
        return []

    normalized_urls: list[str] = []
    seen_urls: set[str] = set()
    for raw_url in raw_image_urls:
        if not isinstance(raw_url, str):
            continue
        normalized_raw_url = raw_url.strip()
        if urlparse(normalized_raw_url).scheme.lower() not in {"http", "https"}:
            continue
        if not is_material_gallery_candidate_url(normalized_raw_url):
            continue
        normalized_url = normalize_material_gallery_image_url(normalized_raw_url)
        if not normalized_url or normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        normalized_urls.append(normalized_url)
    return normalized_urls


def _serialize_material_price_row(price: MaterialPriceModel) -> dict:

    return {
        "city": price.city,
        "price": _normalize_price_value(price.price),
        "currency": price.currency,
        "availability": price.availability,
        "old_price": _normalize_price_value(price.old_price),
        "is_promo": bool(price.is_promo),
        "discount_percent": _normalize_price_value(price.discount_percent),
        "promo_label": price.promo_label,
        "promo_valid_until": price.promo_valid_until,
        "source_checked_at": price.source_checked_at,
        "updated_at": price.updated_at,
    }


def _build_material_price_summary_payload(
    db,
    material_ids: Sequence[int],
    *,
    city: str | None = None,
) -> dict[int, list[dict]]:

    normalized_material_ids = [int(material_id) for material_id in material_ids if material_id is not None]
    if not normalized_material_ids:
        return {}

    normalized_city_key = _normalize_fitting_city_key(city)
    offer_rows = (
        db.query(MaterialSupplierOfferModel)
        .options(
            load_only(
                MaterialSupplierOfferModel.id,
                MaterialSupplierOfferModel.material_id,
                MaterialSupplierOfferModel.price,
                MaterialSupplierOfferModel.currency,
                MaterialSupplierOfferModel.unit,
                MaterialSupplierOfferModel.city,
                MaterialSupplierOfferModel.supplier_id,
                MaterialSupplierOfferModel.source_url,
                MaterialSupplierOfferModel.is_active,
            )
        )
        .filter(MaterialSupplierOfferModel.material_id.in_(normalized_material_ids))
        .filter(MaterialSupplierOfferModel.is_active.is_(True))
        .filter(MaterialSupplierOfferModel.price.isnot(None))
        .all()
    )

    supplier_profiles = _load_material_supplier_profiles(
        db,
        [offer_row.supplier_id for offer_row in offer_rows],
    )

    grouped_rows: dict[int, dict[tuple[str | None, str | None], list[MaterialSupplierOfferModel]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for offer_row in offer_rows:
        supplier_profile = supplier_profiles.get(int(offer_row.supplier_id))
        if (
            normalized_city_key is not None
            and _material_supplier_city_policy(
                supplier_profile,
                source_url=offer_row.source_url,
            ) != "ignore_city"
            and _normalize_fitting_city_key(offer_row.city) != normalized_city_key
        ):
            continue

        currency_value = _normalize_source(offer_row.currency) or "UAH"
        unit_value = _normalize_material_price_summary_unit(offer_row.unit)
        grouped_rows[int(offer_row.material_id)][
            (currency_value.casefold(), unit_value.casefold() if unit_value else None)
        ].append(offer_row)

    payload_by_material_id: dict[int, list[dict]] = {}

    for material_id, grouped_offer_rows in grouped_rows.items():
        summary_rows: list[dict] = []
        for _, offer_group in sorted(
            grouped_offer_rows.items(),
            key=lambda item: ((item[0][1] or ""), (item[0][0] or "")),
        ):
            sorted_offer_group = sorted(offer_group, key=lambda row: row.id)
            normalized_prices = [
                normalized_price
                for normalized_price in (
                    _normalize_price_value(offer_row.price)
                    for offer_row in sorted_offer_group
                )
                if normalized_price is not None
            ]
            if not normalized_prices:
                continue

            first_offer = sorted_offer_group[0]
            summary_rows.append(
                {
                    "unit": _normalize_material_price_summary_unit(first_offer.unit),
                    "currency": _normalize_source(first_offer.currency) or "UAH",
                    "min_price": min(normalized_prices),
                    "max_price": max(normalized_prices),
                    "offer_count": len(normalized_prices),
                }
            )

        if summary_rows:
            payload_by_material_id[material_id] = summary_rows

    return payload_by_material_id


def _build_material_supplier_summary_payload(
    db,
    material_ids: Sequence[int],
    *,
    city: str | None = None,
) -> dict[int, list[dict]]:

    normalized_material_ids = [int(material_id) for material_id in material_ids if material_id is not None]
    if not normalized_material_ids:
        return {}

    normalized_city_key = _normalize_fitting_city_key(city)
    offer_rows = (
        db.query(MaterialSupplierOfferModel)
        .options(
            load_only(
                MaterialSupplierOfferModel.id,
                MaterialSupplierOfferModel.material_id,
                MaterialSupplierOfferModel.supplier_id,
                MaterialSupplierOfferModel.priority,
                MaterialSupplierOfferModel.city,
                MaterialSupplierOfferModel.source_url,
                MaterialSupplierOfferModel.is_active,
            )
        )
        .filter(MaterialSupplierOfferModel.material_id.in_(normalized_material_ids))
        .filter(MaterialSupplierOfferModel.is_active.is_(True))
        .order_by(
            MaterialSupplierOfferModel.priority.asc(),
            MaterialSupplierOfferModel.id.asc(),
        )
        .all()
    )

    supplier_profiles = _load_material_supplier_profiles(
        db,
        [offer_row.supplier_id for offer_row in offer_rows],
    )

    payload_by_material_id: dict[int, list[dict]] = {}
    seen_supplier_ids_by_material_id: dict[int, set[int]] = defaultdict(set)

    for offer_row in offer_rows:
        supplier_profile = supplier_profiles.get(int(offer_row.supplier_id))
        if (
            normalized_city_key is not None
            and _material_supplier_city_policy(
                supplier_profile,
                source_url=offer_row.source_url,
            ) != "ignore_city"
            and _normalize_fitting_city_key(offer_row.city) != normalized_city_key
        ):
            continue

        material_id = int(offer_row.material_id)
        supplier_id = int(offer_row.supplier_id)
        seen_supplier_ids = seen_supplier_ids_by_material_id[material_id]

        if supplier_id in seen_supplier_ids:
            continue

        seen_supplier_ids.add(supplier_id)
        supplier_profile = supplier_profiles.get(supplier_id)
        supplier_name = getattr(supplier_profile, "name", None) or f"Supplier {supplier_id}"
        payload_by_material_id.setdefault(material_id, []).append(
            {
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "supplier_logo_url": getattr(supplier_profile, "logo_url", None),
            }
        )

    return payload_by_material_id


def _build_material_square_meter_support_payload(
    db,
    material_ids: Sequence[int],
    *,
    city: str | None = None,
) -> dict[int, bool]:
    """Expose the existing offer flag for material cards without text heuristics."""

    normalized_material_ids = [int(material_id) for material_id in material_ids if material_id is not None]
    if not normalized_material_ids:
        return {}

    offer_rows = (
        db.query(MaterialSupplierOfferModel)
        .options(
            load_only(
                MaterialSupplierOfferModel.material_id,
                MaterialSupplierOfferModel.supplier_id,
                MaterialSupplierOfferModel.source_url,
                MaterialSupplierOfferModel.source_payload_json,
                MaterialSupplierOfferModel.city,
                MaterialSupplierOfferModel.is_active,
            )
        )
        .filter(MaterialSupplierOfferModel.material_id.in_(normalized_material_ids))
        .filter(MaterialSupplierOfferModel.is_active.is_(True))
        .all()
    )
    supplier_profiles = _load_material_supplier_profiles(
        db,
        [offer_row.supplier_id for offer_row in offer_rows],
    )
    normalized_city_key = _normalize_fitting_city_key(city)
    supported_material_ids: set[int] = set()

    for offer_row in offer_rows:
        supplier_profile = supplier_profiles.get(int(offer_row.supplier_id))
        if (
            normalized_city_key is not None
            and _material_supplier_city_policy(
                supplier_profile,
                source_url=offer_row.source_url,
            ) != "ignore_city"
            and _normalize_fitting_city_key(offer_row.city) != normalized_city_key
        ):
            continue
        if _extract_supplier_offer_square_meter_support(offer_row):
            supported_material_ids.add(int(offer_row.material_id))

    return {material_id: True for material_id in supported_material_ids}


def _serialize_material_image_metadata(item: MaterialImageModel) -> dict:
    return {
        "id": int(item.id),
        "sort_order": int(item.sort_order or 0),
        "is_primary": bool(item.is_primary),
        "source_url": item.source_url,
        "content_type": item.image_cached_content_type,
    }


def _serialize_material_image_blob(item: MaterialImageModel) -> dict:
    return {
        "id": int(item.id),
        "material_id": int(item.material_id),
        "image_cached_bytes": item.image_cached_bytes,
        "image_cached_content_type": item.image_cached_content_type,
    }


def _list_material_images_for_db(db, material_id: int) -> list[dict]:
    rows = (
        db.query(MaterialImageModel)
        .options(
            load_only(
                MaterialImageModel.id,
                MaterialImageModel.material_id,
                MaterialImageModel.sort_order,
                MaterialImageModel.is_primary,
                MaterialImageModel.image_cached_content_type,
            )
        )
        .filter(MaterialImageModel.material_id == int(material_id))
        .order_by(
            MaterialImageModel.sort_order.asc(),
            MaterialImageModel.id.asc(),
        )
        .all()
    )

    return [
        _serialize_material_image_metadata(row)
        for row in rows
    ]


def _add_prepared_material_gallery_images(
    db,
    *,
    material_id: int,
    prepared_gallery_images: Sequence[PreparedFittingGalleryImage],
) -> None:
    db.add_all(
        [
            MaterialImageModel(
                material_id=material_id,
                sort_order=image.sort_order,
                is_primary=image.is_primary,
                source_url=image.source_url,
                image_cached_bytes=image.image_bytes,
                image_cached_content_type=image.content_type,
                image_sha256=image.sha256,
            )
            for image in prepared_gallery_images
        ]
    )


def _serialize_material_manufacturer_row(manufacturer: MaterialManufacturerModel | None) -> dict | None:

    if not manufacturer:
        return None

    return {
        "id": int(manufacturer.id),
        "name": manufacturer.name,
        "code": manufacturer.code,
        "logo_url": manufacturer.logo_url,
    }


def _load_material_manufacturer_profiles(db, manufacturer_ids: list[int | None]) -> dict[int, dict]:

    normalized_ids = sorted(
        {
            int(manufacturer_id)
            for manufacturer_id in manufacturer_ids
            if manufacturer_id is not None and str(manufacturer_id).strip()
        }
    )

    if not normalized_ids:
        return {}

    manufacturers = (
        db.query(MaterialManufacturerModel)
        .filter(MaterialManufacturerModel.id.in_(normalized_ids))
        .all()
    )

    return {
        int(item.id): _serialize_material_manufacturer_row(item)
        for item in manufacturers
    }


def _serialize_material_supplier_offer_row(
    offer: MaterialSupplierOfferModel,
    *,
    supplier: SupplierModel | None = None,
) -> dict:

    offer_supplier = supplier or getattr(offer, "supplier", None)

    return {
        "id": int(offer.id),
        "material_id": int(offer.material_id),
        "supplier_id": int(offer.supplier_id),
        "supplier_name": getattr(offer_supplier, "name", None),
        "supplier_logo_url": getattr(offer_supplier, "logo_url", None),
        "article": _normalize_source(offer.article),
        "external_product_id": _normalize_source(offer.external_product_id),
        "source_url": _normalize_source(offer.source_url),
        "price": _normalize_price_value(offer.price),
        "currency": _normalize_source(offer.currency),
        "unit": _normalize_source(offer.unit),
        "stock": _normalize_source(offer.stock),
        "city": _normalize_source(offer.city),
        "region": _normalize_source(offer.region),
        "supports_square_meter_sale": _extract_supplier_offer_square_meter_support(offer),
        "characteristics": _extract_supplier_offer_characteristics(offer),
        "image_urls": _extract_supplier_offer_image_urls(offer),
        "is_active": bool(offer.is_active),
        "priority": int(offer.priority or 0),
        "parsed_at": offer.parsed_at,
        "price_updated_at": offer.price_updated_at,
        "created_at": offer.created_at,
        "updated_at": offer.updated_at,
    }


def _load_material_supplier_profiles(db, supplier_ids: list[int | None]) -> dict[int, SupplierModel]:

    normalized_ids = sorted(
        {
            int(supplier_id)
            for supplier_id in supplier_ids
            if supplier_id is not None and str(supplier_id).strip()
        }
    )

    if not normalized_ids:
        return {}

    suppliers = (
        db.query(SupplierModel)
        .filter(SupplierModel.id.in_(normalized_ids))
        .all()
    )

    return {
        int(item.id): item
        for item in suppliers
    }


def _normalize_material_supplier_offer_currency(value: str | None) -> str | None:

    normalized = _normalize_source(value)
    if normalized is None:
        return None

    normalized = normalized.upper()
    if not re.fullmatch(r"[A-Z0-9]{2,16}", normalized):
        raise ValueError("Invalid currency")

    return normalized


def _normalize_material_supplier_offer_source_url(value: str | None) -> str | None:

    normalized = _normalize_import_source_url(value)
    if normalized is None:
        return None

    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid source URL")

    return normalized


def _list_material_supplier_offers(
    db,
    material_id: str | int,
    *,
    city: str | None = None,
) -> list[dict]:

    rows = (
        db.query(MaterialSupplierOfferModel)
        .options(
            load_only(
                MaterialSupplierOfferModel.id,
                MaterialSupplierOfferModel.material_id,
                MaterialSupplierOfferModel.supplier_id,
                MaterialSupplierOfferModel.article,
                MaterialSupplierOfferModel.external_product_id,
                MaterialSupplierOfferModel.source_url,
                MaterialSupplierOfferModel.price,
                MaterialSupplierOfferModel.currency,
                MaterialSupplierOfferModel.unit,
                MaterialSupplierOfferModel.stock,
                MaterialSupplierOfferModel.city,
                MaterialSupplierOfferModel.region,
                MaterialSupplierOfferModel.source_payload_json,
                MaterialSupplierOfferModel.is_active,
                MaterialSupplierOfferModel.priority,
                MaterialSupplierOfferModel.parsed_at,
                MaterialSupplierOfferModel.price_updated_at,
                MaterialSupplierOfferModel.created_at,
                MaterialSupplierOfferModel.updated_at,
            )
        )
        .filter(MaterialSupplierOfferModel.material_id == int(material_id))
        .order_by(
            MaterialSupplierOfferModel.priority.asc(),
            MaterialSupplierOfferModel.id.asc(),
        )
        .all()
    )

    supplier_profiles = _load_material_supplier_profiles(
        db,
        [row.supplier_id for row in rows],
    )

    normalized_city_key = _normalize_fitting_city_key(city)
    filtered_rows = []
    for row in rows:
        supplier_profile = supplier_profiles.get(int(row.supplier_id))
        if (
            normalized_city_key is not None
            and _material_supplier_city_policy(
                supplier_profile,
                source_url=row.source_url,
            ) != "ignore_city"
            and _normalize_fitting_city_key(row.city) != normalized_city_key
        ):
            continue
        filtered_rows.append(row)

    return [
        _serialize_material_supplier_offer_row(
            row,
            supplier=supplier_profiles.get(int(row.supplier_id)),
        )
        for row in filtered_rows
    ]


def list_material_supplier_offers(material_id: str | int, city: str | None = None) -> list[dict]:

    db = SessionLocal()

    try:
        return _list_material_supplier_offers(db, material_id, city=city)
    finally:
        db.close()


def create_material_supplier_offer(
    *,
    material_id: str | int,
    supplier_id: str | int,
    article: str,
    external_product_id: str | None = None,
    source_url: str | None = None,
    price: float | None = None,
    currency: str | None = None,
    unit: str | None = None,
    stock: str | None = None,
    city: str | None = None,
    region: str | None = None,
    is_active: bool = True,
    priority: int = 0,
    parsed_at: datetime | None = None,
    price_updated_at: datetime | None = None,
    source_payload_json: str | None = None,
) -> dict | None:

    db = SessionLocal()

    try:
        material = db.get(MaterialModel, int(material_id))
        supplier = db.get(SupplierModel, int(supplier_id))
        if not material or not supplier:
            return None

        if _normalize_price_value(price) is not None and _normalize_price_value(price) < 0:
            raise ValueError("Price must be non-negative")

        offer = MaterialSupplierOfferModel(
            material_id=int(material.id),
            supplier_id=int(supplier.id),
            article=_normalize_source(article),
            external_product_id=_normalize_source(external_product_id),
            source_url=_normalize_material_supplier_offer_source_url(source_url),
            price=_normalize_price_value(price),
            currency=_normalize_material_supplier_offer_currency(currency),
            unit=_normalize_source(unit),
            stock=_normalize_source(stock),
            city=_normalize_source(city),
            region=_normalize_source(region),
            is_active=bool(is_active),
            priority=int(priority or 0),
            parsed_at=parsed_at,
            price_updated_at=price_updated_at,
            source_payload_json=source_payload_json,
        )
        db.add(offer)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return None
        db.refresh(offer)
        offer.supplier = supplier
        return _serialize_material_supplier_offer_row(offer, supplier=supplier)
    finally:
        db.close()


def upsert_material_supplier_offer_for_import(
    *,
    material_id: str | int,
    supplier_id: str | int,
    article: str,
    external_product_id: str | None = None,
    source_url: str | None = None,
    price: float | None = None,
    currency: str | None = None,
    unit: str | None = None,
    stock: str | None = None,
    city: str | None = None,
    region: str | None = None,
    is_active: bool = True,
    priority: int = 0,
    parsed_at: datetime | None = None,
    price_updated_at: datetime | None = None,
    source_payload_json: str | None = None,
) -> dict | None:

    db = SessionLocal()

    try:
        material = db.get(MaterialModel, int(material_id))
        supplier = db.get(SupplierModel, int(supplier_id))
        if not material or not supplier:
            return None

        normalized_external_product_id = _normalize_source(external_product_id)
        query = (
            db.query(MaterialSupplierOfferModel)
            .filter(
                MaterialSupplierOfferModel.material_id == int(material.id),
                MaterialSupplierOfferModel.supplier_id == int(supplier.id),
            )
            .order_by(
                MaterialSupplierOfferModel.updated_at.desc(),
                MaterialSupplierOfferModel.id.desc(),
            )
        )

        if normalized_external_product_id is not None:
            offer = query.filter(
                MaterialSupplierOfferModel.external_product_id == normalized_external_product_id,
            ).first()
        else:
            offer = None

        if not offer:
            offer = query.first()

        if not offer:
            offer = MaterialSupplierOfferModel(
                material_id=int(material.id),
                supplier_id=int(supplier.id),
            )
            db.add(offer)

        offer.article = _normalize_source(article)
        offer.external_product_id = normalized_external_product_id
        offer.source_url = _normalize_material_supplier_offer_source_url(source_url)
        offer.price = _normalize_price_value(price)
        offer.currency = _normalize_material_supplier_offer_currency(currency)
        offer.unit = _normalize_source(unit)
        offer.stock = _normalize_source(stock)
        offer.city = _normalize_source(city)
        offer.region = _normalize_source(region)
        offer.is_active = bool(is_active)
        offer.priority = int(priority or 0)
        offer.parsed_at = parsed_at
        offer.price_updated_at = price_updated_at
        offer.source_payload_json = source_payload_json

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            offer = (
                db.query(MaterialSupplierOfferModel)
                .filter(
                    MaterialSupplierOfferModel.material_id == int(material.id),
                    MaterialSupplierOfferModel.supplier_id == int(supplier.id),
                )
                .order_by(
                    MaterialSupplierOfferModel.updated_at.desc(),
                    MaterialSupplierOfferModel.id.desc(),
                )
                .filter(
                    MaterialSupplierOfferModel.external_product_id == normalized_external_product_id
                    if normalized_external_product_id is not None
                    else MaterialSupplierOfferModel.external_product_id.is_(None)
                )
                .first()
            )
            if not offer:
                return None

        db.refresh(offer)
        offer.supplier = supplier
        return _serialize_material_supplier_offer_row(offer, supplier=supplier)
    finally:
        db.close()


def update_material_supplier_offer(
    offer_id: str | int,
    *,
    supplier_id: str | int | None | object = _UNSET,
    article: str | None | object = _UNSET,
    external_product_id: str | None | object = _UNSET,
    source_url: str | None | object = _UNSET,
    price: float | None | object = _UNSET,
    currency: str | None | object = _UNSET,
    unit: str | None | object = _UNSET,
    stock: str | None | object = _UNSET,
    city: str | None | object = _UNSET,
    region: str | None | object = _UNSET,
    is_active: bool | object = _UNSET,
    priority: int | object = _UNSET,
    parsed_at: datetime | None | object = _UNSET,
    price_updated_at: datetime | None | object = _UNSET,
    source_payload_json: str | None | object = _UNSET,
) -> dict | None:

    db = SessionLocal()

    try:
        offer = (
            db.query(MaterialSupplierOfferModel)
            .filter(MaterialSupplierOfferModel.id == int(offer_id))
            .first()
        )
        if not offer:
            return None

        supplier = None
        if supplier_id is not _UNSET:
            if supplier_id is None:
                raise ValueError("Supplier is required")
            supplier = db.get(SupplierModel, int(supplier_id))
            if not supplier:
                return None
            offer.supplier_id = int(supplier.id)
        else:
            supplier = db.get(SupplierModel, int(offer.supplier_id))

        if article is not _UNSET:
            offer.article = _normalize_source(article)
        if external_product_id is not _UNSET:
            offer.external_product_id = _normalize_source(external_product_id)
        if source_url is not _UNSET:
            offer.source_url = _normalize_material_supplier_offer_source_url(source_url)
        if price is not _UNSET:
            normalized_price = _normalize_price_value(price)
            if normalized_price is not None and normalized_price < 0:
                raise ValueError("Price must be non-negative")
            offer.price = normalized_price
        if currency is not _UNSET:
            offer.currency = _normalize_material_supplier_offer_currency(currency)
        if unit is not _UNSET:
            offer.unit = _normalize_source(unit)
        if stock is not _UNSET:
            offer.stock = _normalize_source(stock)
        if city is not _UNSET:
            offer.city = _normalize_source(city)
        if region is not _UNSET:
            offer.region = _normalize_source(region)
        if is_active is not _UNSET:
            offer.is_active = bool(is_active)
        if priority is not _UNSET:
            offer.priority = int(priority or 0)
        if parsed_at is not _UNSET:
            offer.parsed_at = parsed_at
        if price_updated_at is not _UNSET:
            offer.price_updated_at = price_updated_at
        if source_payload_json is not _UNSET:
            offer.source_payload_json = source_payload_json

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return None
        db.refresh(offer)
        if supplier is not None:
            offer.supplier = supplier
        return _serialize_material_supplier_offer_row(offer, supplier=supplier)
    finally:
        db.close()


def delete_material_supplier_offer(offer_id: str | int) -> dict | None:

    db = SessionLocal()

    try:
        offer = (
            db.query(MaterialSupplierOfferModel)
            .filter(MaterialSupplierOfferModel.id == int(offer_id))
            .first()
        )
        if not offer:
            return None

        supplier = db.get(SupplierModel, int(offer.supplier_id))
        serialized = _serialize_material_supplier_offer_row(offer, supplier=supplier)
        db.delete(offer)
        db.commit()
        return serialized
    finally:
        db.close()


def get_material_supplier_offer(offer_id: str | int) -> dict | None:

    db = SessionLocal()

    try:
        offer = (
            db.query(MaterialSupplierOfferModel)
            .options(
                load_only(
                    MaterialSupplierOfferModel.id,
                    MaterialSupplierOfferModel.material_id,
                    MaterialSupplierOfferModel.supplier_id,
                    MaterialSupplierOfferModel.article,
                    MaterialSupplierOfferModel.external_product_id,
                    MaterialSupplierOfferModel.source_url,
                    MaterialSupplierOfferModel.price,
                    MaterialSupplierOfferModel.currency,
                    MaterialSupplierOfferModel.unit,
                    MaterialSupplierOfferModel.stock,
                    MaterialSupplierOfferModel.city,
                    MaterialSupplierOfferModel.region,
                    MaterialSupplierOfferModel.is_active,
                    MaterialSupplierOfferModel.priority,
                    MaterialSupplierOfferModel.parsed_at,
                    MaterialSupplierOfferModel.price_updated_at,
                    MaterialSupplierOfferModel.created_at,
                    MaterialSupplierOfferModel.updated_at,
                )
            )
            .filter(MaterialSupplierOfferModel.id == int(offer_id))
            .first()
        )

        if not offer:
            return None

        supplier = db.get(SupplierModel, int(offer.supplier_id))
        return _serialize_material_supplier_offer_row(offer, supplier=supplier)
    finally:
        db.close()


def _normalize_import_source_url(value: str | None) -> str | None:

    normalized = str(value or "").strip()

    if not normalized:
        return None

    if "://" not in normalized:
        normalized = f"https://{normalized}"

    try:
        parsed = urlparse(normalized)
        scheme = (parsed.scheme or "https").lower()
        host = (parsed.netloc or "").lower()
        path = parsed.path or ""
        query = f"?{parsed.query}" if parsed.query else ""
        fragment = f"#{parsed.fragment}" if parsed.fragment else ""
        rebuilt = f"{scheme}://{host}{path}{query}{fragment}"
        return rebuilt.rstrip("/") if rebuilt.endswith("/") and path not in ("", "/") else rebuilt
    except Exception:
        return normalized


def _normalize_import_article(value: str | None) -> str | None:

    normalized = str(value or "").strip()

    return normalized or None


def _image_hash(image_bytes: bytes | None) -> str | None:

    if not image_bytes:
        return None

    return sha256(image_bytes).hexdigest()


FITTING_GROUP_LABELS = {
    "fittings": "Фурнітура",
    "fasteners": "Метизна фурнітура",
}


FITTING_CATEGORY_DEFINITIONS = [
    {
        "code": "connectors_fasteners",
        "name": "З'єднувальна та кріпильна фурнітура",
        "group": "fasteners",
        "description": "Стяжки, шканти, куточки, саморізи та інші кріпильні елементи.",
        "icon_key": "blocks",
        "keywords": [
            "саморіз",
            "шуруп",
            "гвинт",
            "євровинт",
            "болт",
            "гайк",
            "шайб",
            "стяж",
            "конфірм",
            "шкант",
            "ламел",
            "дюб",
            "метиз",
            "кутник",
            "кріп",
            "screw",
            "confirmat",
            "bolt",
            "nut",
            "washer",
        ],
    },
    {
        "code": "drawer_slides",
        "name": "Висувні механізми",
        "group": "fittings",
        "description": "Направляючі та системи висування для шухляд.",
        "icon_key": "move-horizontal",
        "keywords": [
            "направ",
            "телескоп",
            "шухляд",
            "ящик",
            "роликова",
            "tandem",
            "slide",
            "drawer",
            "box",
        ],
    },
    {
        "code": "handles_hooks",
        "name": "Ручки та гачки",
        "group": "fittings",
        "description": "Ручки меблеві, гачки та декоративні елементи відкривання.",
        "icon_key": "wrench",
        "keywords": [
            "ручк",
            "гач",
            "handle",
            "hook",
        ],
    },
    {
        "code": "profiles_gola",
        "name": "Ручки-профіль, система Gola",
        "group": "fittings",
        "description": "Профільні ручки та системи Gola для фасадів.",
        "icon_key": "panel-top",
        "keywords": [
            "gola",
            "профіл",
            "profile",
        ],
    },
    {
        "code": "plinth_vents",
        "name": "Цоколі та вентиляційні решітки",
        "group": "fittings",
        "description": "Цоколі, решітки та комплектуючі нижньої бази меблів.",
        "icon_key": "layout-grid",
        "keywords": [
            "цокол",
            "решітк",
            "вент",
            "plinth",
            "grille",
            "vent",
        ],
    },
    {
        "code": "legs_wheels",
        "name": "Ніжки, ролики",
        "group": "fittings",
        "description": "Опори, ніжки та меблеві ролики.",
        "icon_key": "circle",
        "keywords": [
            "ніжк",
            "опор",
            "ролик",
            "колес",
            "leg",
            "wheel",
            "caster",
        ],
    },
    {
        "code": "locks_magnets",
        "name": "Замки, магніти, засувки",
        "group": "fittings",
        "description": "Замки, магніти та елементи фіксації фасадів.",
        "icon_key": "lock",
        "keywords": [
            "зам",
            "магніт",
            "засув",
            "lock",
            "magnet",
            "latch",
        ],
    },
    {
        "code": "wardrobe_systems",
        "name": "Меблеві труби та системи",
        "group": "fittings",
        "description": "Труби, рейлінги, торгові та гардеробні системи.",
        "icon_key": "pipe",
        "keywords": [
            "труб",
            "рейл",
            "гардероб",
            "торгов",
            "rail",
            "wardrobe",
            "closet",
        ],
    },
    {
        "code": "hinges",
        "name": "Навіси меблеві",
        "group": "fittings",
        "description": "Петлі, навіси та рейки для корпусних меблів.",
        "icon_key": "door-open",
        "keywords": [
            "петл",
            "навіс",
            "hinge",
            "lift",
        ],
    },
    {
        "code": "bathroom",
        "name": "Фурнітура для санвузлів",
        "group": "fittings",
        "description": "Фурнітура для сантехнічних перегородок та ванних кімнат.",
        "icon_key": "bath",
        "keywords": [
            "санвуз",
            "ванн",
            "сифон",
            "bath",
            "bathroom",
            "shower",
        ],
    },
    {
        "code": "packaging",
        "name": "Пакувальний матеріал",
        "group": "fasteners",
        "description": "Стретч, скотч та пакувальні матеріали.",
        "icon_key": "package",
        "keywords": [
            "стретч",
            "скотч",
            "пакув",
            "package",
            "tape",
        ],
    },
    {
        "code": "bed_components",
        "name": "Комплектуючі для ліжок",
        "group": "fittings",
        "description": "Каркаси, підйомні механізми та фурнітура для ліжок.",
        "icon_key": "bed",
        "keywords": [
            "ліж",
            "матрац",
            "bed",
            "slat",
        ],
    },
    {
        "code": "wardrobe_fillings",
        "name": "Гардеробне наповнення",
        "group": "fittings",
        "description": "Кошики, брючниці, мікроліфти та наповнення шаф.",
        "icon_key": "shirt",
        "keywords": [
            "кошик",
            "брюч",
            "мікроліфт",
            "гардероб",
            "basket",
            "wardrobe",
        ],
    },
    {
        "code": "other_fittings",
        "name": "Інша фурнітура",
        "group": "fittings",
        "description": "Позиції, які поки не віднесено до окремого типу.",
        "icon_key": "package",
        "keywords": [],
    },
    {
        "code": "other_fasteners",
        "name": "Інший кріпіж",
        "group": "fasteners",
        "description": "Інші кріпильні елементи та метизи.",
        "icon_key": "blocks",
        "keywords": [],
    },
]

FITTING_CATEGORY_MAP = {
    item["code"]: item
    for item in FITTING_CATEGORY_DEFINITIONS
}


def _normalize_fitting_value(value: str | None) -> str | None:

    if value is None:
        return None

    normalized = str(value).strip()

    return normalized or None


def _normalize_fitting_city_key(value: str | None) -> str | None:

    normalized = _normalize_fitting_value(value)

    if normalized is None:
        return None

    return normalized.casefold()


def _fitting_catalog_key_column_exists(item: FittingModel) -> bool:

    session = object_session(item)
    if session is None:
        return False

    bind = session.get_bind()
    cache_key = id(bind)
    if cache_key in _FITTINGS_CATALOG_KEY_COLUMN_CACHE:
        return _FITTINGS_CATALOG_KEY_COLUMN_CACHE[cache_key]

    rows = session.execute(text("PRAGMA table_info(fittings)")).fetchall()
    exists = any(str(row[1]) == "catalog_key" for row in rows)
    _FITTINGS_CATALOG_KEY_COLUMN_CACHE[cache_key] = exists
    return exists


def _get_fitting_catalog_key(item: FittingModel) -> str:

    catalog_key = _normalize_fitting_value(item.__dict__.get("catalog_key"))
    if catalog_key is None and _fitting_catalog_key_column_exists(item):
        session = object_session(item)
        if session is not None:
            row = session.execute(
                text("SELECT catalog_key FROM fittings WHERE id = :id"),
                {"id": item.id},
            ).first()
            if row is not None:
                catalog_key = _normalize_fitting_value(row[0])

    if catalog_key:
        return f"catalog_key:{catalog_key.casefold()}"

    article = _normalize_fitting_value(item.article)
    if article:
        return f"article:{article.casefold()}"

    code = _normalize_fitting_value(item.code)
    if code:
        return f"code:{code.casefold()}"

    name = _normalize_fitting_value(item.name)
    if name:
        return f"name:{name.casefold()}"

    return f"id:{item.id}"


def _normalize_fitting_delete_key(value: str | None) -> str | None:

    normalized = _normalize_fitting_value(value)

    if normalized is None:
        return None

    return normalized.casefold()


def _build_fitting_delete_signature(item: FittingModel) -> dict[str, object | None]:

    return {
        "catalog_key": _get_fitting_catalog_key(item),
        "source": _normalize_fitting_delete_key(item.source),
        "source_url": _normalize_fitting_delete_key(item.source_url),
        "is_system": bool(item.is_system),
        "owner_user_id": _normalize_fitting_delete_key(item.owner_user_id),
    }


def _fitting_matches_delete_signature(
    candidate: FittingModel,
    signature: dict[str, object | None],
) -> bool:

    return (
        _get_fitting_catalog_key(candidate) == signature["catalog_key"]
        and _normalize_fitting_delete_key(candidate.source) == signature["source"]
        and _normalize_fitting_delete_key(candidate.source_url) == signature["source_url"]
        and bool(candidate.is_system) == bool(signature["is_system"])
        and _normalize_fitting_delete_key(candidate.owner_user_id) == signature["owner_user_id"]
    )


def _list_fitting_delete_candidates(db, item: FittingModel) -> list[FittingModel]:

    query = db.query(FittingModel)

    article = _normalize_fitting_value(item.article)
    code = _normalize_fitting_value(item.code)
    name = _normalize_fitting_value(item.name)

    if article:
        query = query.filter(FittingModel.article == article)
    elif code:
        query = query.filter(FittingModel.code == code)
    elif name:
        query = query.filter(FittingModel.name == name)
    else:
        query = query.filter(FittingModel.id == item.id)

    return (
        query.order_by(
            FittingModel.city.asc().nullsfirst(),
            FittingModel.id.asc(),
        )
        .all()
    )


def _resolve_fitting_category(
    fitting_type: str | None,
    fitting_group: str | None,
    *values: str | None,
) -> dict:

    if fitting_type and fitting_type in FITTING_CATEGORY_MAP:
        item = FITTING_CATEGORY_MAP[fitting_type]
        return {
            **item,
            "group": fitting_group or item["group"],
        }

    haystack = " ".join(
        value.lower()
        for value in values
        if value
    )

    for item in FITTING_CATEGORY_DEFINITIONS:
        if any(keyword in haystack for keyword in item["keywords"]):
            return item

    fallback_code = "other_fasteners" if fitting_group == "fasteners" else "other_fittings"

    return FITTING_CATEGORY_MAP[fallback_code]


def _serialize_fitting(item: FittingModel, *, owner_profile: dict | None = None) -> dict:

    category = _resolve_fitting_category(
        item.fitting_type,
        item.fitting_group,
        item.name,
        item.article,
        item.code,
        item.stock,
    )

    source_site = _detect_fitting_source_site(item.source_url)
    supplier_offers = [
        _serialize_fitting_supplier_offer(offer)
        for offer in sorted(
            getattr(item, "supplier_offers", []) or [],
            key=lambda offer: (int(offer.priority or 0), int(offer.id or 0)),
        )
    ]
    technical_product = getattr(item, "technical_product", None)

    return {
        "id": str(item.id),
        "city": item.city,
        "code": item.code,
        "article": item.article,
        "name": item.name,
        "description": item.description,
        "price": item.price,
        "stock": item.stock,
        "fitting_type": category["code"],
        "fitting_type_name": category["name"],
        "fitting_group": category["group"],
        "fitting_group_name": FITTING_GROUP_LABELS.get(category["group"], category["group"]),
        "fitting_description": category.get("description"),
        "image_url": item.image_url,
        "has_cached_image": bool(item.image_cached_bytes),
        "source_url": item.source_url,
        "source_site": source_site,
        "owner_user_id": item.owner_user_id,
        "owner_display_name": (owner_profile or {}).get("display_name"),
        "owner_login": (owner_profile or {}).get("login"),
        "owner_email": (owner_profile or {}).get("email"),
        "technical_product_id": int(item.technical_product_id) if item.technical_product_id is not None else None,
        "manufacturer_id": int(technical_product.manufacturer_id) if technical_product and technical_product.manufacturer_id is not None else None,
        "supplier_offers": supplier_offers,
        "is_system": bool(item.is_system),
        "is_active": bool(item.is_active),
        "sort_order": item.sort_order or 0,
        "created_at": getattr(item, "created_at", None),
        "updated_at": getattr(item, "updated_at", None),
    }


def _serialize_supplier(item: SupplierModel) -> dict:

    return {
        "id": int(item.id),
        "code": item.code,
        "name": item.name,
        "logo_url": item.logo_url,
        "owner_user_id": item.owner_user_id,
        "is_system": bool(item.is_system),
        "is_active": bool(item.is_active),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def get_supplier_by_id(item_id: str | int) -> dict | None:

    db = SessionLocal()

    try:
        item = db.get(SupplierModel, int(item_id))
        return _serialize_supplier(item) if item else None
    finally:
        db.close()


def get_supplier_by_code(code: str) -> dict | None:

    normalized_code = str(code or "").strip()
    if not normalized_code:
        return None

    db = SessionLocal()

    try:
        item = db.query(SupplierModel).filter(SupplierModel.code == normalized_code).first()
        if item:
            return _serialize_supplier(item)

        normalized_code_key = normalized_code.casefold()
        supplier_aliases = {
            "viyar": {"viyar", "VIYAR", "Viyar", "віяр", "ВІЯР", "Віяр"},
            "kronas": {"kronas", "KRONAS", "Kronas", "кронас", "Кронас", "КРОНАС"},
        }.get(normalized_code_key)

        if not supplier_aliases:
            return None

        normalized_aliases = {str(alias).strip() for alias in supplier_aliases if str(alias).strip()}
        if not normalized_aliases:
            return None

        item = (
            db.query(SupplierModel)
            .filter(
                SupplierModel.code.in_(normalized_aliases)
                | SupplierModel.name.in_(normalized_aliases)
            )
            .first()
        )
        return _serialize_supplier(item) if item else None
    finally:
        db.close()


def _generate_supplier_code(name: str | None, code: str | None = None) -> str:

    normalized_code = _normalize_fitting_value(code)
    if normalized_code:
        return normalized_code

    normalized_name = _normalize_fitting_value(name) or "supplier"
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized_name.casefold()).strip("-")
    if not slug:
        slug = "supplier"
    return f"{slug}-{uuid4().hex[:8]}"


def create_supplier(
    *,
    code: str | None = None,
    name: str,
    logo_url: str | None = None,
    owner_user_id: str | None = None,
    is_system: bool = False,
    is_active: bool = True,
) -> dict | None:

    db = SessionLocal()

    try:
        normalized_name = _normalize_fitting_value(name)
        if not normalized_name:
            return None

        item = SupplierModel(
            code=_generate_supplier_code(normalized_name, code),
            name=normalized_name,
            logo_url=_normalize_fitting_value(logo_url),
            owner_user_id=_normalize_fitting_value(owner_user_id),
            is_system=bool(is_system),
            is_active=bool(is_active),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return _serialize_supplier(item)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def update_supplier(
    item_id: str | int,
    *,
    code: str | None = None,
    name: str | None = None,
    logo_url: str | None = None,
    owner_user_id: str | None = None,
    is_system: bool | None = None,
    is_active: bool | None = None,
) -> dict | None:

    db = SessionLocal()

    try:
        item = db.get(SupplierModel, int(item_id))
        if not item:
            return None

        if code is not None:
            normalized_code = _normalize_fitting_value(code)
            if normalized_code:
                item.code = normalized_code

        if name is not None:
            normalized_name = _normalize_fitting_value(name)
            if normalized_name:
                item.name = normalized_name

        if logo_url is not None:
            item.logo_url = _normalize_fitting_value(logo_url)

        if owner_user_id is not None:
            item.owner_user_id = _normalize_fitting_value(owner_user_id)

        if is_system is not None:
            item.is_system = bool(is_system)

        if is_active is not None:
            item.is_active = bool(is_active)

        db.commit()
        db.refresh(item)
        return _serialize_supplier(item)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def delete_supplier(item_id: str | int) -> dict | None:

    db = SessionLocal()

    try:
        item = db.get(SupplierModel, int(item_id))
        if not item:
            return None

        serialized = _serialize_supplier(item)
        db.delete(item)
        db.commit()
        return serialized
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def count_supplier_offer_usage(supplier_id: str | int) -> int:

    db = SessionLocal()

    try:
        return int(
            db.query(func.count(FittingSupplierOfferModel.id))
            .filter(FittingSupplierOfferModel.supplier_id == int(supplier_id))
            .scalar()
            or 0,
        )
    finally:
        db.close()


def count_material_supplier_offer_usage(supplier_id: str | int) -> int:

    db = SessionLocal()

    try:
        return int(
            db.query(func.count(MaterialSupplierOfferModel.id))
            .filter(MaterialSupplierOfferModel.supplier_id == int(supplier_id))
            .scalar()
            or 0,
        )
    finally:
        db.close()


def _serialize_fitting_supplier_offer(item: FittingSupplierOfferModel) -> dict:

    supplier = getattr(item, "supplier", None)
    supplier_code = getattr(supplier, "code", None) or ""
    supplier_name = getattr(supplier, "name", None) or ""
    supplier_logo_url = getattr(supplier, "logo_url", None) or ""

    return {
        "id": int(item.id),
        "fitting_id": int(item.fitting_id),
        "supplier_id": int(item.supplier_id),
        "supplier_code": supplier_code,
        "supplier_name": supplier_name,
        "supplier_logo_url": supplier_logo_url,
        "article": _normalize_fitting_value(item.article),
        "external_product_id": _normalize_fitting_value(item.external_product_id),
        "source_url": _normalize_fitting_value(item.source_url),
        "price": _normalize_price_value(item.price),
        "currency": _normalize_fitting_value(item.currency),
        "unit": _normalize_fitting_value(item.unit),
        "stock": _normalize_fitting_value(item.stock),
        "is_active": bool(item.is_active),
        "priority": int(item.priority or 0),
    }


def _normalize_fitting_supplier_offer_payload(
    supplier_offer: dict | None,
) -> dict | None:

    if not supplier_offer:
        return None

    normalized_supplier_id = supplier_offer.get("supplier_id")
    if normalized_supplier_id in (None, "", 0):
        return None

    normalized_article = _normalize_fitting_value(supplier_offer.get("article"))
    normalized_external_product_id = _normalize_fitting_value(supplier_offer.get("external_product_id"))
    normalized_source_url = _normalize_fitting_value(supplier_offer.get("source_url"))
    normalized_currency = _normalize_fitting_value(supplier_offer.get("currency"))
    normalized_unit = _normalize_fitting_value(supplier_offer.get("unit"))
    normalized_stock = _normalize_fitting_value(supplier_offer.get("stock"))
    normalized_price = _normalize_price_value(supplier_offer.get("price"))
    normalized_priority = int(supplier_offer.get("priority") or 0)

    return {
        "offer_id": supplier_offer.get("offer_id"),
        "supplier_id": int(normalized_supplier_id),
        "article": normalized_article,
        "external_product_id": normalized_external_product_id,
        "source_url": normalized_source_url,
        "price": normalized_price,
        "currency": normalized_currency,
        "unit": normalized_unit,
        "stock": normalized_stock,
        "is_active": bool(supplier_offer.get("is_active", True)),
        "priority": normalized_priority,
    }


def _has_meaningful_supplier_offer_data(supplier_offer: dict | None) -> bool:

    if not supplier_offer:
        return False

    if supplier_offer.get("is_active") is False:
        return True

    if int(supplier_offer.get("priority") or 0) not in (0, 100):
        return True

    return any(
        supplier_offer.get(key) not in (None, "", 0)
        for key in (
            "article",
            "external_product_id",
            "source_url",
            "price",
            "currency",
            "unit",
            "stock",
        )
    )


def _resolve_or_create_technical_product(
    db,
    technical_product: dict | None,
) -> FittingProductModel | None:

    if not technical_product:
        return None

    normalized_name = str(technical_product.get("name") or "").strip()
    normalized_article = _normalize_fitting_value(technical_product.get("article"))
    normalized_code = _normalize_fitting_value(technical_product.get("code"))
    normalized_brand = _normalize_fitting_value(technical_product.get("brand"))
    normalized_description = _normalize_fitting_value(technical_product.get("description"))
    manufacturer_id = technical_product.get("manufacturer_id")
    series_id = technical_product.get("series_id")
    category_id = technical_product.get("category_id")
    is_active = technical_product.get("is_active")
    resolved_manufacturer_id: int | None = None
    if manufacturer_id is not None:
        try:
            candidate_manufacturer_id = int(manufacturer_id)
        except (TypeError, ValueError):
            candidate_manufacturer_id = None
        if candidate_manufacturer_id is not None:
            manufacturer_exists = (
                db.query(FittingManufacturerModel.id)
                .filter(FittingManufacturerModel.id == candidate_manufacturer_id)
                .first()
            )
            if manufacturer_exists is not None:
                resolved_manufacturer_id = candidate_manufacturer_id
    resolved_category_id: int | None = None
    if category_id is not None:
        try:
            candidate_category_id = int(category_id)
        except (TypeError, ValueError):
            candidate_category_id = None
        if candidate_category_id is not None:
            category_exists = (
                db.query(FittingCategoryModel.id)
                .filter(FittingCategoryModel.id == candidate_category_id)
                .first()
            )
            if category_exists is not None:
                resolved_category_id = candidate_category_id

    if normalized_article:
        existing = (
            db.query(FittingProductModel)
            .filter(FittingProductModel.article == normalized_article)
            .first()
        )
        if existing:
            if normalized_code and not _normalize_fitting_value(existing.code):
                existing.code = normalized_code
            if normalized_name and not _normalize_fitting_value(existing.name):
                existing.name = normalized_name
            if normalized_brand and not _normalize_fitting_value(existing.brand):
                existing.brand = normalized_brand
            if normalized_description and not _normalize_fitting_value(existing.description):
                existing.description = normalized_description
            if resolved_manufacturer_id is not None and existing.manufacturer_id is None:
                existing.manufacturer_id = resolved_manufacturer_id
            if series_id is not None and existing.series_id is None:
                existing.series_id = int(series_id)
            if resolved_category_id is not None and existing.category_id is None:
                existing.category_id = resolved_category_id
            if is_active is not None:
                existing.is_active = bool(is_active)
            db.flush()
            return existing

    if not normalized_name and not normalized_article and not normalized_code:
        return None

    product = FittingProductModel(
        article=normalized_article,
        code=normalized_code,
        name=normalized_name or normalized_article or normalized_code or "Technical product",
        brand=normalized_brand,
        description=normalized_description,
        manufacturer_id=resolved_manufacturer_id,
        series_id=int(series_id) if series_id is not None else None,
        category_id=resolved_category_id,
        is_active=True if is_active is None else bool(is_active),
    )
    db.add(product)
    db.flush()
    return product


def _apply_fitting_supplier_offer(
    db,
    *,
    fitting_id: int,
    supplier_offer: dict | None,
) -> None:

    normalized_supplier_offer = _normalize_fitting_supplier_offer_payload(supplier_offer)
    if not normalized_supplier_offer or not _has_meaningful_supplier_offer_data(normalized_supplier_offer):
        return

    foundation_repo = FittingFoundationRepository(db)
    offer = None
    offer_id = normalized_supplier_offer.get("offer_id")
    if offer_id not in (None, "", 0):
        offer = foundation_repo.get_offer_by_id(int(offer_id))
        if offer and int(offer.fitting_id) != int(fitting_id):
            offer = None
    if offer is None:
        offer = (
            db.query(FittingSupplierOfferModel)
            .filter(FittingSupplierOfferModel.fitting_id == int(fitting_id))
            .filter(FittingSupplierOfferModel.supplier_id == normalized_supplier_offer["supplier_id"])
            .order_by(
                FittingSupplierOfferModel.priority.asc(),
                FittingSupplierOfferModel.id.asc(),
            )
            .first()
        )

    offer_payload = {
        "supplier_id": normalized_supplier_offer["supplier_id"],
        "article": normalized_supplier_offer["article"],
        "external_product_id": normalized_supplier_offer["external_product_id"],
        "source_url": normalized_supplier_offer["source_url"],
        "price": normalized_supplier_offer["price"],
        "currency": normalized_supplier_offer["currency"],
        "unit": normalized_supplier_offer["unit"],
        "stock": normalized_supplier_offer["stock"],
        "is_active": normalized_supplier_offer["is_active"],
        "priority": normalized_supplier_offer["priority"],
    }

    if offer is None:
        created_offer = foundation_repo.create_offer(
            fitting_id=fitting_id,
            **offer_payload,
        )
        if created_offer is None:
            raise ValueError("Unable to create fitting supplier offer")
        return

    foundation_repo.update_offer(
        offer,
        **offer_payload,
    )


def _delete_exact_fittings(db, fitting_ids: Sequence[int]) -> list[dict]:
    normalized_ids = [
        int(fitting_id)
        for fitting_id in fitting_ids
        if fitting_id not in (None, "")
    ]
    if not normalized_ids:
        return []

    rows = (
        db.query(FittingModel)
        .filter(FittingModel.id.in_(normalized_ids))
        .order_by(FittingModel.id.asc())
        .all()
    )
    if not rows:
        return []

    row_ids = [int(row.id) for row in rows]
    deleted_items = [_serialize_fitting(row) for row in rows]

    db.query(MountingNodeItemModel).filter(
        MountingNodeItemModel.fitting_id.in_(row_ids),
    ).delete(synchronize_session=False)

    template_rows = (
        db.query(FittingHoleTemplateModel.id)
        .filter(FittingHoleTemplateModel.fitting_id.in_(row_ids))
        .all()
    )
    template_ids = [int(row[0]) for row in template_rows]

    if template_ids:
        db.query(FittingHolePointModel).filter(
            FittingHolePointModel.template_id.in_(template_ids),
        ).delete(synchronize_session=False)

    db.query(FittingSupplierOfferModel).filter(
        FittingSupplierOfferModel.fitting_id.in_(row_ids),
    ).delete(synchronize_session=False)

    db.query(FittingImageModel).filter(
        FittingImageModel.fitting_id.in_(row_ids),
    ).delete(synchronize_session=False)

    if template_ids:
        db.query(FittingHoleTemplateModel).filter(
            FittingHoleTemplateModel.id.in_(template_ids),
        ).delete(synchronize_session=False)

    db.query(FittingModel).filter(
        FittingModel.id.in_(row_ids),
    ).delete(synchronize_session=False)

    return deleted_items


def _serialize_fitting_image_metadata(item: FittingImageModel) -> dict:
    return {
        "id": int(item.id),
        "sort_order": int(item.sort_order or 0),
        "is_primary": bool(item.is_primary),
        "content_type": item.image_cached_content_type,
    }


def _serialize_fitting_image_blob(item: FittingImageModel) -> dict:
    return {
        "id": int(item.id),
        "fitting_id": int(item.fitting_id),
        "image_cached_bytes": item.image_cached_bytes,
        "image_cached_content_type": item.image_cached_content_type,
    }


def _add_prepared_fitting_gallery_images(
    db,
    *,
    fitting_id: int,
    prepared_gallery_images: Sequence[PreparedFittingGalleryImage],
) -> None:
    db.add_all(
        [
            FittingImageModel(
                fitting_id=fitting_id,
                sort_order=image.sort_order,
                is_primary=image.is_primary,
                source_url=image.source_url,
                image_cached_bytes=image.image_bytes,
                image_cached_content_type=image.content_type,
                image_sha256=image.sha256,
            )
            for image in prepared_gallery_images
        ]
    )


def _detect_source_site(source_url: str | None) -> str:

    if not source_url:
        return "manual"

    raw_value = str(source_url).strip()

    if not raw_value:
        return "manual"

    normalized_url = raw_value if "://" in raw_value else f"https://{raw_value}"

    try:
        parsed = urlparse(normalized_url)
        host = (parsed.netloc or parsed.path or "").lower()
        path = (parsed.path or "").lower()
    except Exception:
        host = raw_value.lower()
        path = raw_value.lower()

    haystack = f"{host} {path}"

    if "viyar" in haystack:
        return "viyar"

    if "kronas" in haystack:
        return "kronas"

    if "blum" in haystack or "mt" in haystack:
        return "blum"

    return "manual"


def _material_supplier_city_policy(
    supplier: SupplierModel | None,
    *,
    source_url: str | None = None,
) -> str:
    """Return the city matching policy for a material supplier offer."""

    source_site = _detect_source_site(source_url)
    supplier_code = str(getattr(supplier, "code", "") or "").strip().casefold()

    if source_site == "viyar" or supplier_code == "viyar":
        return "exact_city"
    if source_site == "kronas" or supplier_code == "kronas":
        return "ignore_city"
    return "legacy"


def _detect_fitting_source_site(source_url: str | None) -> str:
    return _detect_source_site(source_url)


MATERIAL_EDGE_LABELS = {
    "edge_04": "0,4 мм",
    "edge_08": "0,8 мм",
    "edge_1": "1 мм",
    "edge_1x43": "1х43 мм",
    "edge_2": "2 мм",
    "edge_2x43": "2х43 мм",
}


def _serialize_material_edge(
    item: MaterialEdgeModel,
    prices_by_edge_id: dict[int, list[MaterialEdgePriceModel]],
    city: str | None = None,
) -> dict:

    sorted_prices = sorted(
        prices_by_edge_id.get(item.id, []),
        key=lambda row: ((row.city or ""), row.id),
    )
    normalized_prices = [
        {
            "city": price.city,
            "price": _normalize_price_value(price.price),
        }
        for price in sorted_prices
    ]
    exact_price_row = next(
        (
            price
            for price in normalized_prices
            if city and price["city"] == city and price["price"] is not None
        ),
        None,
    )
    fallback_price_row = next(
        (
            price
            for price in normalized_prices
            if price["price"] is not None
        ),
        None,
    )
    active_price_row = exact_price_row if city else fallback_price_row

    return {
        "id": str(item.id),
        "edge_key": item.edge_key,
        "label": MATERIAL_EDGE_LABELS.get(item.edge_key, item.edge_key),
        "article": item.article,
        "name": item.name,
        "thickness": item.thickness_label,
        "image": item.image,
        "has_cached_image": bool(item.image_cached_bytes),
        "source_url": item.source_url,
        "source": item.source,
        "product_type": item.product_type or item.edge_key,
        "source_site": _detect_source_site(item.source_url),
        "current_price": active_price_row["price"] if active_price_row else None,
        "current_price_city": active_price_row["city"] if active_price_row else None,
        "current_price_exact": bool(exact_price_row),
        "prices": normalized_prices,
    }


def _load_material_edges_payload(
    db,
    material_articles: list[str],
    city: str | None = None,
) -> dict[str, list[dict]]:

    if not material_articles:
        return {}

    edge_rows = (
        db.query(MaterialEdgeModel)
        .options(
            load_only(
                MaterialEdgeModel.id,
                MaterialEdgeModel.material_article,
                MaterialEdgeModel.edge_key,
                MaterialEdgeModel.article,
                MaterialEdgeModel.name,
                MaterialEdgeModel.thickness_label,
                MaterialEdgeModel.image,
                MaterialEdgeModel.source_url,
                MaterialEdgeModel.source,
                MaterialEdgeModel.product_type,
            )
        )
        .filter(MaterialEdgeModel.material_article.in_(material_articles))
        .order_by(MaterialEdgeModel.material_article.asc(), MaterialEdgeModel.edge_key.asc(), MaterialEdgeModel.id.asc())
        .all()
    )

    edge_prices = db.query(MaterialEdgePriceModel).all()
    prices_by_edge_id: dict[int, list[MaterialEdgePriceModel]] = defaultdict(list)
    edge_articles_with_cache = {
        (row[0], row[1])
        for row in (
            db.query(
                MaterialEdgeModel.material_article,
                MaterialEdgeModel.edge_key,
            )
            .filter(MaterialEdgeModel.material_article.in_(material_articles))
            .filter(MaterialEdgeModel.image_cached_bytes.isnot(None))
            .filter(func.length(MaterialEdgeModel.image_cached_bytes) > 0)
            .all()
        )
    }

    for price in edge_prices:
        prices_by_edge_id[price.edge_option_id].append(price)

    payload: dict[str, list[dict]] = defaultdict(list)

    for row in edge_rows:
        sorted_prices = sorted(
            prices_by_edge_id.get(row.id, []),
            key=lambda price_row: ((price_row.city or ""), price_row.id),
        )
        normalized_prices = [
            {
                "city": price.city,
                "price": _normalize_price_value(price.price),
            }
            for price in sorted_prices
        ]
        exact_price_row = next(
            (
                price
                for price in normalized_prices
                if city and price["city"] == city and price["price"] is not None
            ),
            None,
        )
        fallback_price_row = next(
            (
                price
                for price in normalized_prices
                if price["price"] is not None
            ),
            None,
        )
        active_price_row = exact_price_row if city else fallback_price_row

        payload[row.material_article].append(
            {
                "id": str(row.id),
                "edge_key": row.edge_key,
                "label": MATERIAL_EDGE_LABELS.get(row.edge_key, row.edge_key),
                "article": row.article,
                "name": row.name,
                "thickness": row.thickness_label,
                "image": row.image,
                "has_cached_image": (
                    row.image is not None
                    and (row.material_article, row.edge_key) in edge_articles_with_cache
                ),
                "source_url": row.source_url,
                "source": row.source,
                "product_type": row.product_type or row.edge_key,
                "source_site": _detect_source_site(row.source_url),
                "current_price": active_price_row["price"] if active_price_row else None,
                "current_price_city": active_price_row["city"] if active_price_row else None,
                "current_price_exact": bool(exact_price_row),
                "prices": normalized_prices,
            }
        )

    return payload


def _load_material_canonical_edges_payload(
    db,
    material_ids: list[int],
    *,
    material_articles: list[str] | None = None,
    city: str | None = None,
) -> dict[str, list[dict]]:

    if not material_ids:
        return {}

    article_rows = (
        db.query(MaterialModel.id, MaterialModel.article)
        .filter(MaterialModel.id.in_(material_ids))
        .all()
    )
    article_by_material_id = {
        int(row.id): str(row.article)
        for row in article_rows
        if row.id is not None and row.article
    }

    if material_articles:
        allowed_articles = {str(article) for article in material_articles if article}
        article_by_material_id = {
            material_id: article
            for material_id, article in article_by_material_id.items()
            if article in allowed_articles
        }

    if not article_by_material_id:
        return {}

    material_rows = (
        db.query(
            MaterialEdgeRelationModel,
            CanonicalEdgeModel,
        )
        .join(CanonicalEdgeModel, CanonicalEdgeModel.id == MaterialEdgeRelationModel.edge_id)
        .filter(MaterialEdgeRelationModel.material_id.in_(article_by_material_id.keys()))
        .order_by(
            MaterialEdgeRelationModel.material_id.asc(),
            MaterialEdgeRelationModel.relation_type.asc(),
            MaterialEdgeRelationModel.id.asc(),
        )
        .all()
    )

    if not material_rows:
        return {}

    edge_ids = [int(edge.id) for _, edge in material_rows if edge and edge.id is not None]
    manufacturer_profiles = _load_material_manufacturer_profiles(
        db,
        [
            int(edge.manufacturer_id)
            for _, edge in material_rows
            if edge and edge.manufacturer_id is not None
        ],
    )
    offer_rows = (
        db.query(EdgeSupplierOfferModel, SupplierModel)
        .outerjoin(SupplierModel, SupplierModel.id == EdgeSupplierOfferModel.supplier_id)
        .filter(EdgeSupplierOfferModel.edge_id.in_(edge_ids))
        .order_by(
            EdgeSupplierOfferModel.edge_id.asc(),
            EdgeSupplierOfferModel.priority.asc(),
            EdgeSupplierOfferModel.id.asc(),
        )
        .all()
    )
    offer_ids = [int(offer.id) for offer, _ in offer_rows if offer and offer.id is not None]
    price_rows = (
        db.query(EdgeSupplierOfferPriceModel)
        .filter(EdgeSupplierOfferPriceModel.offer_id.in_(offer_ids))
        .order_by(
            EdgeSupplierOfferPriceModel.offer_id.asc(),
            EdgeSupplierOfferPriceModel.city.asc(),
            EdgeSupplierOfferPriceModel.id.asc(),
        )
        .all()
    )

    prices_by_offer_id: dict[int, list[EdgeSupplierOfferPriceModel]] = defaultdict(list)
    for row in price_rows:
        prices_by_offer_id[int(row.offer_id)].append(row)

    offers_by_edge_id: dict[int, list[dict]] = defaultdict(list)
    for offer_row, supplier_row in offer_rows:
        if not offer_row or offer_row.edge_id is None:
            continue

        sorted_prices = sorted(
            prices_by_offer_id.get(int(offer_row.id), []),
            key=lambda price_row: ((price_row.city or ""), price_row.id),
        )
        normalized_prices = [
            {
                "city": price.city,
                "price": _normalize_price_value(price.price),
                "currency": price.currency,
                "availability": price.availability,
            }
            for price in sorted_prices
        ]
        exact_price_row = next(
            (
                price
                for price in normalized_prices
                if city and price["city"] == city and price["price"] is not None
            ),
            None,
        )
        fallback_price_row = next(
            (
                price
                for price in normalized_prices
                if price["price"] is not None
            ),
            None,
        )
        active_price_row = exact_price_row if city else fallback_price_row
        supplier_name = getattr(supplier_row, "name", None) if supplier_row else None
        supplier_logo_url = getattr(supplier_row, "logo_url", None) if supplier_row else None

        offers_by_edge_id[int(offer_row.edge_id)].append(
            {
                "id": int(offer_row.id),
                "edge_id": int(offer_row.edge_id),
                "supplier_id": int(offer_row.supplier_id),
                "supplier_name": supplier_name,
                "supplier_logo_url": supplier_logo_url,
                "article": offer_row.article,
                "external_product_id": offer_row.external_product_id,
                "source_url": offer_row.source_url,
                "unit": offer_row.unit,
                "stock": offer_row.stock,
                "availability": active_price_row["availability"] if active_price_row else None,
                "is_active": bool(offer_row.is_active),
                "priority": int(offer_row.priority or 0),
                "parsed_at": offer_row.parsed_at,
                "price_updated_at": offer_row.price_updated_at,
                "created_at": offer_row.created_at,
                "updated_at": offer_row.updated_at,
                "prices": normalized_prices,
                "_active_price": active_price_row,
            }
        )

    payload: dict[str, list[dict]] = defaultdict(list)
    for relation_row, edge_row in material_rows:
        if not relation_row or not edge_row:
            continue
        article = article_by_material_id.get(int(relation_row.material_id))
        if not article:
            continue

        offer_candidates = offers_by_edge_id.get(int(edge_row.id), [])
        primary_offer = offer_candidates[0] if offer_candidates else None
        active_price_row = (primary_offer or {}).get("_active_price") if primary_offer else None
        edge_current_price = active_price_row["price"] if active_price_row else None
        edge_current_price_city = active_price_row["city"] if active_price_row else None
        edge_prices = (primary_offer or {}).get("prices", []) if primary_offer else []
        if not edge_prices and offer_candidates:
            edge_prices = offer_candidates[0].get("prices", [])

        payload[article].append(
            {
                "id": str(edge_row.id),
                "edge_key": f"recommended:{edge_row.id}",
                "label": None,
                "relation_type": relation_row.relation_type,
                "manufacturer_id": int(edge_row.manufacturer_id) if edge_row.manufacturer_id is not None else None,
                "manufacturer_name": None,
                "manufacturer_article": edge_row.manufacturer_article,
                "material_type": edge_row.material_type,
                "width_mm": edge_row.width_mm,
                "thickness_mm": edge_row.thickness_mm,
                "article": primary_offer["article"] if primary_offer else None,
                "name": edge_row.name,
                "thickness": (
                    f"{edge_row.thickness_mm:g} мм"
                    if edge_row.thickness_mm is not None
                    else None
                ),
                "image": edge_row.image_url,
                "has_cached_image": False,
                "source_url": primary_offer["source_url"] if primary_offer else relation_row.source_url,
                "source_site": _detect_source_site((primary_offer or {}).get("source_url") or relation_row.source_url),
                "current_price": edge_current_price,
                "current_price_city": edge_current_price_city,
                "prices": [
                    {
                        "city": price.get("city"),
                        "price": price.get("price"),
                    }
                    for price in edge_prices
                ],
                "supplier_offers": [
                    {
                        **{key: value for key, value in offer.items() if not key.startswith("_")},
                        "prices": [
                            {
                                "city": price.get("city"),
                                "price": price.get("price"),
                                "currency": price.get("currency"),
                                "availability": price.get("availability"),
                            }
                            for price in offer.get("prices", [])
                        ],
                    }
                    for offer in offer_candidates
                ],
                "source_supplier_id": relation_row.source_supplier_id,
                "manufacturer_name": manufacturer_profiles.get(int(edge_row.manufacturer_id), {}).get("name")
                if edge_row.manufacturer_id is not None
                else None,
            }
        )

    return payload


def get_material_edge_image(
    material_article: str,
    edge_key: str,
) -> dict | None:
    db = SessionLocal()

    try:
        item = (
            db.query(MaterialEdgeModel)
            .filter(
                MaterialEdgeModel.material_article == material_article,
                MaterialEdgeModel.edge_key == edge_key,
            )
            .first()
        )

        if not item:
            return None

        return {
            "id": str(item.id),
            "material_article": item.material_article,
            "edge_key": item.edge_key,
            "article": item.article,
            "image": item.image,
            "source_url": item.source_url,
            "source": item.source,
            "product_type": item.product_type or item.edge_key,
            "image_source_url": item.image_source_url or item.image,
            "image_cached_bytes": item.image_cached_bytes,
            "image_cached_content_type": item.image_cached_content_type,
            "image_cached_hash": item.image_cached_hash,
        }
    finally:
        db.close()


def update_material_edge_image_cache(
    material_article: str,
    edge_key: str,
    image_bytes: bytes | None,
    content_type: str | None,
) -> dict | None:
    db = SessionLocal()

    try:
        item = (
            db.query(MaterialEdgeModel)
            .filter(
                MaterialEdgeModel.material_article == material_article,
                MaterialEdgeModel.edge_key == edge_key,
            )
            .first()
        )

        if not item:
            return None

        item.image_cached_bytes = image_bytes
        item.image_cached_content_type = content_type
        item.image_cached_hash = _image_hash(image_bytes)
        db.commit()

        return {
            "id": str(item.id),
            "has_cached_image": bool(item.image_cached_bytes),
            "image_cached_content_type": item.image_cached_content_type,
        }
    finally:
        db.close()


def list_fitting_categories(
    items: list[dict] | None = None,
    group: str | None = None,
) -> list[dict]:

    counts: dict[str, int] = defaultdict(int)

    for item in items or []:
        counts[item["fitting_type"]] += 1

    categories = []

    for category in FITTING_CATEGORY_DEFINITIONS:
        if group and category["group"] != group:
            continue

        categories.append(
            {
                "code": category["code"],
                "name": category["name"],
                "group": category["group"],
                "group_name": FITTING_GROUP_LABELS.get(category["group"], category["group"]),
                "description": category.get("description"),
                "icon_key": category.get("icon_key"),
                "item_count": counts.get(category["code"], 0),
            }
        )

    return categories


def list_material_categories() -> list[dict]:

    db = SessionLocal()

    try:

        rows = (
            db.query(
                MaterialModel.category,
            )
            .filter(MaterialModel.category.isnot(None))
            .distinct()
            .order_by(MaterialModel.category.asc())
            .all()
        )

        return [
            {
                "code": row[0],
                "name": row[0],
            }
            for row in rows
            if row[0]
        ]

    finally:

        db.close()


def list_inventory_cities() -> list[str]:

    db = SessionLocal()

    try:

        material_city_rows = (
            db.query(MaterialPriceModel.city)
            .filter(MaterialPriceModel.city.isnot(None))
            .distinct()
            .all()
        )
        fitting_city_rows = (
            db.query(FittingModel.city)
            .filter(FittingModel.city.isnot(None))
            .distinct()
            .all()
        )
        user_city_rows = (
            db.query(UserModel.city)
            .filter(UserModel.is_active.is_(True))
            .filter(UserModel.city.isnot(None))
            .distinct()
            .all()
        )

        return sorted(
            {
                row[0]
                for row in [*material_city_rows, *fitting_city_rows, *user_city_rows]
                if row[0]
            }
        )

    finally:

        db.close()


def _material_visible_to_viewer(
    item: MaterialModel,
    viewer_user_id: str | None,
    viewer_role: str | None,
    linked_article_ids: set[str] | None = None,
) -> bool:

    if viewer_role == "admin":
        return True

    if bool(item.is_default) and item.owner_user_id is None:
        return True

    normalized_user_id = _normalize_fitting_value(viewer_user_id)
    if normalized_user_id and item.owner_user_id == normalized_user_id:
        return True

    if linked_article_ids and item.article in linked_article_ids:
        return True

    return False


def _normalize_material_ownership_scope(value: str | None) -> str:

    normalized = str(value or "").strip().casefold()

    if normalized in {"system", "mine", "users", "all"}:
        return normalized

    return "all"


def _fitting_visible_to_viewer(
    item: FittingModel,
    viewer_user_id: str | None,
    viewer_role: str | None,
) -> bool:

    if viewer_role == "admin":
        return True

    if bool(item.is_system):
        return True

    normalized_user_id = _normalize_fitting_value(viewer_user_id)
    if normalized_user_id and item.owner_user_id == normalized_user_id:
        return True

    return False


def material_needs_full_sync(material: dict | None) -> bool:

    if not material:
        return True

    required_fields = [
        "name",
        "source_url",
        "source",
        "product_type",
        "image_source_url",
        "imported_at",
    ]

    for field in required_fields:
        if not material.get(field):
            return True

    prices = material.get("prices") or []
    if not prices or not any(price.get("price") is not None for price in prices):
        return True

    cached_bytes = material.get("image_cached_bytes")
    if not cached_bytes or len(cached_bytes) == 0:
        return True

    return False


def _load_material_user_links(
    db,
    viewer_user_id: str | None,
) -> set[str]:

    normalized_user_id = _normalize_fitting_value(viewer_user_id)
    if not normalized_user_id:
        return set()

    rows = (
        db.query(MaterialUserLinkModel.material_article)
        .filter(MaterialUserLinkModel.user_id == normalized_user_id)
        .all()
    )
    return {row[0] for row in rows if row and row[0]}


def _serialize_material_owner(user: UserModel) -> dict:
    login = (user.username or user.email.split("@")[0]).strip()
    return {
        "id": str(user.id),
        "display_name": user.username or login or None,
        "login": login or None,
        "email": user.email,
    }


def _serialize_fitting_owner(user: UserModel) -> dict:
    login = (user.username or user.email.split("@")[0]).strip()
    return {
        "id": str(user.id),
        "display_name": user.username or login or None,
        "login": login or None,
        "email": user.email,
    }


def _load_fitting_owner_profiles(
    db,
    owner_user_ids: Sequence[str | None],
) -> dict[str, dict]:

    normalized_owner_user_ids = [
        str(owner_user_id).strip()
        for owner_user_id in owner_user_ids
        if str(owner_user_id or "").strip()
    ]

    if not normalized_owner_user_ids:
        return {}

    users = (
        db.query(UserModel)
        .filter(UserModel.id.in_(normalized_owner_user_ids))
        .all()
    )

    return {
        str(user.id): _serialize_fitting_owner(user)
        for user in users
    }


def get_material_by_import_identity(
    *,
    source: str | None,
    product_type: str | None,
    article: str | None,
    source_url: str | None,
) -> dict | None:

    db = SessionLocal()

    try:
        normalized_source = _normalize_source(source)
        normalized_product_type = _normalize_source(product_type)
        normalized_article = _normalize_import_article(article)
        normalized_source_url = _normalize_import_source_url(source_url)

        query = db.query(MaterialModel)

        if normalized_source and normalized_product_type and normalized_article:
            item = (
                query
                .filter(MaterialModel.source == normalized_source)
                .filter(MaterialModel.product_type == normalized_product_type)
                .filter(MaterialModel.article == normalized_article)
                .first()
            )
            if item:
                return get_material_by_article(item.article)

        if normalized_source_url:
            item = (
                query
                .filter(MaterialModel.source_url == normalized_source_url)
                .first()
            )
            if item:
                return get_material_by_article(item.article)

        if normalized_article:
            item = (
                query
                .filter(MaterialModel.article == normalized_article)
                .first()
            )
            if item:
                return get_material_by_article(item.article)

        return None
    finally:

        db.close()


def ensure_material_user_link(
    *,
    article: str,
    user_id: str,
    source: str | None = None,
    product_type: str | None = None,
    source_url: str | None = None,
) -> dict | None:

    db = SessionLocal()

    try:
        normalized_article = _normalize_import_article(article)
        normalized_user_id = _normalize_fitting_value(user_id)

        if not normalized_article or not normalized_user_id:
            return None

        link = (
            db.query(MaterialUserLinkModel)
            .filter(MaterialUserLinkModel.material_article == normalized_article)
            .filter(MaterialUserLinkModel.user_id == normalized_user_id)
            .first()
        )

        if not link:
            link = MaterialUserLinkModel(
                material_article=normalized_article,
                user_id=normalized_user_id,
            )
            db.add(link)

        link.source = _normalize_source(source)
        link.product_type = _normalize_source(product_type)
        link.source_url = _normalize_import_source_url(source_url)

        db.commit()
        db.refresh(link)

        return {
            "id": str(link.id),
            "material_article": link.material_article,
            "user_id": link.user_id,
            "source": link.source,
            "product_type": link.product_type,
            "source_url": link.source_url,
            "created_at": link.created_at,
        }

    finally:

        db.close()


def count_owned_private_materials(owner_user_id: str | None) -> int:

    normalized_owner_user_id = _normalize_fitting_value(owner_user_id)
    if not normalized_owner_user_id:
        return 0

    db = SessionLocal()

    try:
        return (
            db.query(func.count(MaterialModel.id))
            .filter(MaterialModel.owner_user_id == normalized_owner_user_id)
            .filter(MaterialModel.is_default.is_(False))
            .scalar()
            or 0
        )
    finally:
        db.close()


def get_material_owners(material_article: str) -> dict | None:

    normalized_article = _normalize_import_article(material_article)
    if not normalized_article:
        return None

    db = SessionLocal()

    try:
        material = (
            db.query(MaterialModel.id, MaterialModel.article, MaterialModel.owner_user_id)
            .filter(MaterialModel.article == normalized_article)
            .first()
        )

        if not material:
            return None

        owner_ids: list[str] = []
        if material.owner_user_id:
            owner_ids.append(str(material.owner_user_id))

        link_owner_ids = [
            row[0]
            for row in (
                db.query(MaterialUserLinkModel.user_id)
                .filter(MaterialUserLinkModel.material_article == normalized_article)
                .distinct()
                .order_by(MaterialUserLinkModel.user_id.asc())
                .all()
            )
            if row and row[0]
        ]

        for owner_id in link_owner_ids:
            if owner_id not in owner_ids:
                owner_ids.append(owner_id)

        if not owner_ids:
            return {
                "material_article": normalized_article,
                "owners_count": 0,
                "owners": [],
            }

        users_by_id = {
            str(user.id): user
            for user in (
                db.query(UserModel)
                .filter(UserModel.id.in_(owner_ids))
                .all()
            )
        }

        owners = [
            _serialize_material_owner(users_by_id[owner_id])
            for owner_id in owner_ids
            if owner_id in users_by_id
        ]

        return {
            "material_article": normalized_article,
            "owners_count": len(owners),
            "owners": owners,
        }
    finally:
        db.close()


def list_materials(
    search: str | None = None,
    category: str | None = None,
    city: str | None = None,
    viewer_user_id: str | None = None,
    viewer_role: str | None = None,
    ownership_scope: str | None = None,
) -> list[dict]:

    db = SessionLocal()

    try:

        query = db.query(MaterialModel).options(
            load_only(
                MaterialModel.id,
                MaterialModel.article,
                MaterialModel.name,
                MaterialModel.description,
                MaterialModel.color,
                MaterialModel.dimensions,
                MaterialModel.thickness,
                MaterialModel.image,
                MaterialModel.source_url,
                MaterialModel.source,
                MaterialModel.product_type,
                MaterialModel.owner_user_id,
                MaterialModel.category,
                MaterialModel.manufacturer_id,
                MaterialModel.tg_file_id,
                MaterialModel.is_default,
            )
        )
        linked_article_ids = _load_material_user_links(db, viewer_user_id)

        if category:
            query = query.filter(
                MaterialModel.category == category,
            )

        normalized_ownership_scope = _normalize_material_ownership_scope(ownership_scope)

        if viewer_role == "admin":
            if normalized_ownership_scope == "system":
                query = query.filter(
                    MaterialModel.is_default.is_(True),
                    MaterialModel.owner_user_id.is_(None),
                )
            elif normalized_ownership_scope == "mine":
                query = query.filter(
                    MaterialModel.is_default.is_(False),
                    MaterialModel.owner_user_id == _normalize_fitting_value(viewer_user_id),
                )
            elif normalized_ownership_scope == "users":
                query = query.filter(
                    MaterialModel.is_default.is_(False),
                    MaterialModel.owner_user_id.isnot(None),
                    MaterialModel.owner_user_id != _normalize_fitting_value(viewer_user_id),
                )
        elif viewer_role and viewer_role != "admin":
            query = query.filter(
                (
                    (
                        MaterialModel.is_default.is_(True)
                        & MaterialModel.owner_user_id.is_(None)
                    )
                    | (MaterialModel.owner_user_id == _normalize_fitting_value(viewer_user_id))
                    | MaterialModel.article.in_(sorted(linked_article_ids))
                )
            )

        if search:
            search_value = f"%{search.strip()}%"
            query = query.filter(
                MaterialModel.name.ilike(search_value) |
                MaterialModel.article.ilike(search_value)
            )

        materials = (
            query.order_by(
                MaterialModel.category.asc(),
                MaterialModel.name.asc(),
                MaterialModel.article.asc(),
            )
            .all()
        )

        material_prices = db.query(MaterialPriceModel).all()
        prices_by_article: dict[str, list[MaterialPriceModel]] = defaultdict(list)
        manufacturer_profiles = _load_material_manufacturer_profiles(
            db,
            [item.manufacturer_id for item in materials],
        )
        supplier_summary_by_material_id = _build_material_supplier_summary_payload(
            db,
            [int(item.id) for item in materials],
            city=city,
        )
        cached_material_articles = {
            row[0]
            for row in (
                db.query(MaterialModel.article)
                .filter(MaterialModel.article.in_([item.article for item in materials if item.article]))
                .filter(MaterialModel.image_cached_bytes.isnot(None))
                .filter(func.length(MaterialModel.image_cached_bytes) > 0)
                .all()
            )
        }
        edges_by_article = _load_material_edges_payload(
            db,
            [item.article for item in materials if item.article],
            city=city,
        )
        price_summary_by_material_id = _build_material_price_summary_payload(
            db,
            [int(item.id) for item in materials],
            city=city,
        )
        square_meter_support_by_material_id = _build_material_square_meter_support_payload(
            db,
            [int(item.id) for item in materials],
            city=city,
        )

        for price in material_prices:
            prices_by_article[price.article].append(price)

        serialized_items = []

        for item in materials:
            sorted_prices = sorted(
                prices_by_article.get(item.article, []),
                key=lambda row: ((row.city or ""), row.id),
            )
            normalized_prices = [
                _serialize_material_price_row(price)
                for price in sorted_prices
            ]
            exact_price_row = next(
                (
                    price
                    for price in sorted_prices
                    if city and price.city == city and price.price is not None
                ),
                None,
            )
            fallback_price_row = next(
                (
                    price
                    for price in sorted_prices
                    if price.price is not None
                ),
                None,
            )
            # When a city is explicitly selected, show only the price that
            # belongs to that city. Do not silently substitute another city's
            # price in the main card because it confuses the user-facing city
            # context. Keep the fallback row separately for diagnostics/future UI.
            active_price_row = exact_price_row if city else fallback_price_row

            serialized_items.append(
                {
                    "id": str(item.id),
                    "article": item.article,
                    "display_article": (
                        None
                        if (not item.source_url and str(item.article or "").startswith("manual-"))
                        else item.article
                    ),
                    "name": item.name,
                    "description": item.description,
                    "color": item.color,
                    "dimensions": item.dimensions,
                    "thickness": item.thickness,
                    "category": item.category,
                    "manufacturer_id": int(item.manufacturer_id) if item.manufacturer_id is not None else None,
                    "manufacturer_name": (
                        manufacturer_profiles.get(int(item.manufacturer_id), {}).get("name")
                        if item.manufacturer_id is not None
                        else None
                    ),
                    "manufacturer_logo_url": (
                        manufacturer_profiles.get(int(item.manufacturer_id), {}).get("logo_url")
                        if item.manufacturer_id is not None
                        else None
                    ),
                    "image": item.image,
                    "source_url": item.source_url,
                    "source_site": _detect_source_site(item.source_url),
                    "tg_file_id": item.tg_file_id,
                    "owner_user_id": item.owner_user_id,
                    "is_default": bool(item.is_default),
                    "has_cached_image": item.article in cached_material_articles,
                    "prices": normalized_prices,
                    "current_price": active_price_row.price if active_price_row else None,
                    "current_price_city": active_price_row.city if active_price_row else None,
                    "current_price_exact": bool(exact_price_row),
                    "current_price_details": (
                        _serialize_material_price_row(active_price_row)
                        if active_price_row
                        else None
                    ),
                    "price_summary": price_summary_by_material_id.get(int(item.id), []),
                    "supports_square_meter_sale": bool(square_meter_support_by_material_id.get(int(item.id))),
                    "supplier_summary": supplier_summary_by_material_id.get(int(item.id), []),
                    "fallback_price": fallback_price_row.price if fallback_price_row else None,
                    "fallback_price_city": fallback_price_row.city if fallback_price_row else None,
                    "edge_options": edges_by_article.get(item.article, []),
                }
            )

        return serialized_items

    finally:

        db.close()


def list_fittings(
    search: str | None = None,
    city: str | None = None,
    viewer_user_id: str | None = None,
    viewer_role: str | None = None,
    fitting_group: str | None = None,
    fitting_type: str | None = None,
    ownership_scope: str | None = None,
    include_inactive: bool = False,
) -> list[dict]:

    db = SessionLocal()

    try:

        query = db.query(FittingModel)
        query = query.options(
            selectinload(FittingModel.supplier_offers).selectinload(FittingSupplierOfferModel.supplier),
            selectinload(FittingModel.technical_product),
        )

        if search:
            search_value = f"%{search.strip()}%"
            query = query.filter(
                FittingModel.name.ilike(search_value) |
                FittingModel.article.ilike(search_value) |
                FittingModel.code.ilike(search_value)
            )

        if not include_inactive:
            query = query.filter(FittingModel.is_active.is_(True))

        normalized_ownership_scope = _normalize_material_ownership_scope(ownership_scope)

        if viewer_role == "admin":
            if normalized_ownership_scope == "system":
                query = query.filter(
                    FittingModel.is_system.is_(True),
                    FittingModel.owner_user_id.is_(None),
                )
            elif normalized_ownership_scope == "mine":
                query = query.filter(
                    FittingModel.is_system.is_(False),
                    FittingModel.owner_user_id == _normalize_fitting_value(viewer_user_id),
                )
            elif normalized_ownership_scope == "users":
                query = query.filter(
                    FittingModel.is_system.is_(False),
                    FittingModel.owner_user_id.isnot(None),
                    FittingModel.owner_user_id != _normalize_fitting_value(viewer_user_id),
                )
        elif viewer_role != "admin":
            visible_filter = FittingModel.is_system.is_(True)

            if viewer_user_id:
                visible_filter = visible_filter | (FittingModel.owner_user_id == str(viewer_user_id))

            query = query.filter(visible_filter)

        fittings = (
            query.order_by(
                FittingModel.fitting_group.asc().nullsfirst(),
                FittingModel.fitting_type.asc().nullsfirst(),
                FittingModel.sort_order.asc(),
                FittingModel.city.asc(),
                FittingModel.name.asc(),
                FittingModel.code.asc(),
            )
            .all()
        )
        owner_profiles = _load_fitting_owner_profiles(
            db,
            [item.owner_user_id for item in fittings],
        )

        requested_city_key = _normalize_fitting_city_key(city)
        requested_city_value = _normalize_fitting_value(city)
        fittings_by_key: dict[str, list[FittingModel]] = defaultdict(list)

        for item in fittings:
            fittings_by_key[_get_fitting_catalog_key(item)].append(item)

        serialized = []

        for fitting_rows in fittings_by_key.values():
            selected_row = None
            exact_city_row = None

            if requested_city_key:
                exact_city_row = next(
                    (
                        row
                        for row in fitting_rows
                        if _normalize_fitting_city_key(row.city) == requested_city_key
                    ),
                    None,
                )

            if exact_city_row:
                selected_row = exact_city_row
            else:
                selected_row = next(
                    (
                        row
                        for row in fitting_rows
                        if _normalize_fitting_city_key(row.city) is None
                    ),
                    fitting_rows[0],
                )

            serialized_item = _serialize_fitting(
                selected_row,
                owner_profile=owner_profiles.get(str(selected_row.owner_user_id or "")),
            )

            if requested_city_key:
                if exact_city_row:
                    serialized_item["city"] = exact_city_row.city
                    serialized_item["price"] = _normalize_price_value(exact_city_row.price)
                else:
                    serialized_item["city"] = requested_city_value
                    serialized_item["price"] = None

            serialized.append(serialized_item)

        if fitting_group:
            serialized = [
                item
                for item in serialized
                if item["fitting_group"] == fitting_group
            ]

        if fitting_type:
            serialized = [
                item
                for item in serialized
                if item["fitting_type"] == fitting_type
            ]

        return serialized

    finally:

        db.close()


def create_fitting(
    *,
    city: str | None,
    code: str | None,
    article: str | None,
    name: str,
    description: str | None,
    price: float | None,
    stock: str | None,
    source: str | None,
    brand: str | None,
    fitting_type: str | None,
    fitting_group: str | None,
    image_url: str | None,
    source_url: str | None,
    source_payload_json: str | None,
    owner_user_id: str | None,
    is_system: bool,
    is_active: bool,
    sort_order: int = 0,
    technical_product: dict | None = None,
    supplier_offer: dict | None = None,
    prepared_gallery_images: Sequence[PreparedFittingGalleryImage] | None = None,
) -> dict:

    db = SessionLocal()

    try:

        category = _resolve_fitting_category(
            fitting_type,
            fitting_group,
            name,
            article,
            code,
            stock,
        )

        gallery_images = list(prepared_gallery_images or [])
        primary_gallery_image = gallery_images[0] if gallery_images else None
        normalized_image_url = _normalize_fitting_value(image_url)
        normalized_city = _normalize_fitting_value(city)
        normalized_source = _normalize_fitting_value(source)
        normalized_source_url = _normalize_fitting_value(source_url)

        if primary_gallery_image:
            normalized_image_url = primary_gallery_image.source_url

        technical_product_item = _resolve_or_create_technical_product(
            db,
            technical_product,
        )
        if technical_product and technical_product_item is None:
            raise ValueError("Unable to create canonical fitting product")

        item = None
        if technical_product_item is not None and normalized_source_url:
            item = (
                db.query(FittingModel)
                .filter(FittingModel.technical_product_id == int(technical_product_item.id))
                .filter(FittingModel.source == normalized_source)
                .filter(FittingModel.source_url == normalized_source_url)
                .filter(FittingModel.city == normalized_city)
                .order_by(FittingModel.id.asc())
                .first()
            )

        created = item is None
        if item is None:
            item = FittingModel(
                city=normalized_city,
                code=_normalize_fitting_value(code),
                article=_normalize_fitting_value(article),
                name=name.strip(),
                description=_normalize_fitting_value(description),
                price=_normalize_price_value(price),
                stock=_normalize_fitting_value(stock),
                source=normalized_source,
                brand=_normalize_fitting_value(brand),
                fitting_type=category["code"],
                fitting_group=category["group"],
                image_url=normalized_image_url,
                source_url=normalized_source_url,
                source_payload_json=_normalize_fitting_value(source_payload_json),
                owner_user_id=_normalize_fitting_value(owner_user_id),
                is_system=bool(is_system),
                is_active=bool(is_active),
                sort_order=int(sort_order or 0),
                image_cached_bytes=primary_gallery_image.image_bytes if primary_gallery_image else None,
                image_cached_content_type=primary_gallery_image.content_type if primary_gallery_image else None,
            )
            db.add(item)
            db.flush()
        else:
            item.city = normalized_city
            item.code = _normalize_fitting_value(code)
            item.article = _normalize_fitting_value(article)
            item.name = name.strip()
            item.description = _normalize_fitting_value(description)
            item.price = _normalize_price_value(price)
            item.stock = _normalize_fitting_value(stock)
            item.source = normalized_source
            item.brand = _normalize_fitting_value(brand)
            item.fitting_type = category["code"]
            item.fitting_group = category["group"]
            item.image_url = normalized_image_url
            item.source_url = normalized_source_url
            item.source_payload_json = _normalize_fitting_value(source_payload_json)
            item.owner_user_id = _normalize_fitting_value(owner_user_id)
            item.is_system = bool(is_system)
            item.is_active = bool(is_active)
            item.sort_order = int(sort_order or 0)
            item.image_cached_bytes = primary_gallery_image.image_bytes if primary_gallery_image else None
            item.image_cached_content_type = primary_gallery_image.content_type if primary_gallery_image else None

        if technical_product_item is not None:
            item.technical_product_id = technical_product_item.id
            db.flush()

        if created:
            _apply_fitting_supplier_offer(db, fitting_id=item.id, supplier_offer=supplier_offer)
        else:
            _apply_fitting_supplier_offer(db, fitting_id=item.id, supplier_offer=supplier_offer)

        if not created and gallery_images:
            db.query(FittingImageModel).filter(
                FittingImageModel.fitting_id == int(item.id),
            ).delete(synchronize_session=False)

        if gallery_images:
            _add_prepared_fitting_gallery_images(
                db,
                fitting_id=item.id,
                prepared_gallery_images=gallery_images,
            )

        db.commit()
        db.refresh(item)

        owner_profile = None
        if item.owner_user_id:
            owner_profile = _load_fitting_owner_profiles(db, [item.owner_user_id]).get(str(item.owner_user_id))

        serialized = _serialize_fitting(item, owner_profile=owner_profile)
        serialized["operation"] = "created" if created else "reused"
        return serialized

    except Exception:
        db.rollback()
        raise

    finally:

        db.close()


def get_fitting_by_id(
    item_id: str | int,
    viewer_user_id: str | None = None,
    viewer_role: str | None = None,
) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(FittingModel)
            .options(selectinload(FittingModel.technical_product))
            .filter(FittingModel.id == int(item_id))
            .first()
        )

        if not item:
            return None

        if (viewer_user_id is not None or viewer_role is not None) and not _fitting_visible_to_viewer(
            item,
            viewer_user_id=viewer_user_id,
            viewer_role=viewer_role,
        ):
            return None

        owner_profile = None
        if item.owner_user_id:
            owner_profile = _load_fitting_owner_profiles(db, [item.owner_user_id]).get(str(item.owner_user_id))

        return _serialize_fitting(item, owner_profile=owner_profile)

    finally:

        db.close()


def list_fitting_images(fitting_id: str | int) -> list[dict]:

    db = SessionLocal()

    try:

        rows = (
            db.query(FittingImageModel)
            .options(
                load_only(
                    FittingImageModel.id,
                    FittingImageModel.fitting_id,
                    FittingImageModel.sort_order,
                    FittingImageModel.is_primary,
                    FittingImageModel.image_cached_content_type,
                )
            )
            .filter(FittingImageModel.fitting_id == int(fitting_id))
            .order_by(
                FittingImageModel.sort_order.asc(),
                FittingImageModel.id.asc(),
            )
            .all()
        )

        return [
            _serialize_fitting_image_metadata(row)
            for row in rows
        ]

    finally:

        db.close()


def get_fitting_image(
    fitting_id: str | int,
    image_id: str | int,
) -> dict | None:

    db = SessionLocal()

    try:

        row = (
            db.query(FittingImageModel)
            .options(
                load_only(
                    FittingImageModel.id,
                    FittingImageModel.fitting_id,
                    FittingImageModel.image_cached_bytes,
                    FittingImageModel.image_cached_content_type,
                )
            )
            .filter(FittingImageModel.fitting_id == int(fitting_id))
            .filter(FittingImageModel.id == int(image_id))
            .first()
        )

        if not row or not row.image_cached_bytes or not row.image_cached_content_type:
            return None

        return _serialize_fitting_image_blob(row)

    finally:

        db.close()


def update_fitting(
    *,
    item_id: str | int,
    city: str | None,
    code: str | None,
    article: str | None,
    name: str,
    description: str | None,
    price: float | None,
    stock: str | None,
    fitting_type: str | None,
    fitting_group: str | None,
    image_url: str | None,
    source_url: str | None,
    source_payload_json: str | None,
    owner_user_id: str | None,
    is_system: bool,
    is_active: bool,
    sort_order: int = 0,
    technical_product: dict | None = None,
    supplier_offer: dict | None = None,
    prepared_gallery_images: Sequence[PreparedFittingGalleryImage] | None = None,
) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(FittingModel)
            .filter(FittingModel.id == int(item_id))
            .first()
        )

        if not item:
            return None

        category = _resolve_fitting_category(
            fitting_type,
            fitting_group,
            name,
            article,
            code,
            stock,
        )

        technical_product_item = None
        if technical_product:
            if item.technical_product_id is not None:
                technical_product_item = (
                    db.query(FittingProductModel)
                    .filter(FittingProductModel.id == int(item.technical_product_id))
                    .first()
                )
            if technical_product_item is None:
                technical_product_item = _resolve_or_create_technical_product(
                    db,
                    technical_product,
                )
            else:
                normalized_name = str(technical_product.get("name") or "").strip()
                normalized_article = _normalize_fitting_value(technical_product.get("article"))
                normalized_code = _normalize_fitting_value(technical_product.get("code"))
                normalized_brand = _normalize_fitting_value(technical_product.get("brand"))
                normalized_description = _normalize_fitting_value(technical_product.get("description"))
                manufacturer_id = technical_product.get("manufacturer_id")
                series_id = technical_product.get("series_id")
                category_id = technical_product.get("category_id")
                is_active = technical_product.get("is_active")

                if normalized_article:
                    technical_product_item.article = normalized_article
                if normalized_code:
                    technical_product_item.code = normalized_code
                if normalized_name:
                    technical_product_item.name = normalized_name
                if normalized_brand:
                    technical_product_item.brand = normalized_brand
                if normalized_description:
                    technical_product_item.description = normalized_description
                if manufacturer_id is not None:
                    technical_product_item.manufacturer_id = int(manufacturer_id)
                if series_id is not None:
                    technical_product_item.series_id = int(series_id)
                if category_id is not None:
                    technical_product_item.category_id = int(category_id)
                if is_active is not None:
                    technical_product_item.is_active = bool(is_active)
                db.flush()

        item.city = _normalize_fitting_value(city)
        item.code = _normalize_fitting_value(code)
        item.article = _normalize_fitting_value(article)
        item.name = name.strip()
        item.description = _normalize_fitting_value(description)
        item.price = _normalize_price_value(price)
        item.stock = _normalize_fitting_value(stock)
        item.fitting_type = category["code"]
        item.fitting_group = category["group"]
        normalized_image_url = _normalize_fitting_value(image_url)

        if normalized_image_url != item.image_url:
            item.image_cached_bytes = None
            item.image_cached_content_type = None

        item.image_url = normalized_image_url
        item.source_url = _normalize_fitting_value(source_url)
        item.source_payload_json = _normalize_fitting_value(source_payload_json)
        item.owner_user_id = _normalize_fitting_value(owner_user_id)
        item.is_system = bool(is_system)
        item.is_active = bool(is_active)
        item.sort_order = int(sort_order or 0)
        gallery_images = list(prepared_gallery_images or [])

        if technical_product_item is not None:
            item.technical_product_id = technical_product_item.id

        _apply_fitting_supplier_offer(db, fitting_id=int(item.id), supplier_offer=supplier_offer)

        if prepared_gallery_images is not None:
            db.query(FittingImageModel).filter(
                FittingImageModel.fitting_id == int(item.id),
            ).delete(synchronize_session=False)

        if gallery_images:
            _add_prepared_fitting_gallery_images(
                db,
                fitting_id=item.id,
                prepared_gallery_images=gallery_images,
            )

        db.commit()
        db.refresh(item)

        owner_profile = None
        if item.owner_user_id:
            owner_profile = _load_fitting_owner_profiles(db, [item.owner_user_id]).get(str(item.owner_user_id))

        return _serialize_fitting(item, owner_profile=owner_profile)

    finally:

        db.close()


def list_suppliers(
    include_inactive: bool = False,
    current_user_id: str | None = None,
) -> list[dict]:

    db = SessionLocal()

    try:
        query = db.query(SupplierModel)
        if not include_inactive:
            query = query.filter(SupplierModel.is_active.is_(True))
        normalized_current_user_id = _normalize_fitting_value(current_user_id)
        if normalized_current_user_id:
            query = query.filter(
                (
                    SupplierModel.is_system.is_(True)
                )
                | (
                    SupplierModel.owner_user_id == normalized_current_user_id
                )
            )
        else:
            query = query.filter(SupplierModel.is_system.is_(True))
        rows = query.order_by(
            SupplierModel.name.asc(),
            SupplierModel.code.asc(),
            SupplierModel.id.asc(),
        ).all()
        return [
            _serialize_supplier(row)
            for row in rows
        ]
    finally:
        db.close()


def list_fitting_supplier_offers(fitting_id: str | int) -> list[dict]:

    db = SessionLocal()

    try:
        rows = (
            db.query(FittingSupplierOfferModel)
            .options(
                load_only(
                    FittingSupplierOfferModel.id,
                    FittingSupplierOfferModel.fitting_id,
                    FittingSupplierOfferModel.supplier_id,
                    FittingSupplierOfferModel.article,
                    FittingSupplierOfferModel.external_product_id,
                    FittingSupplierOfferModel.source_url,
                    FittingSupplierOfferModel.price,
                    FittingSupplierOfferModel.currency,
                    FittingSupplierOfferModel.unit,
                    FittingSupplierOfferModel.stock,
                    FittingSupplierOfferModel.is_active,
                    FittingSupplierOfferModel.priority,
                )
            )
            .filter(FittingSupplierOfferModel.fitting_id == int(fitting_id))
            .order_by(
                FittingSupplierOfferModel.priority.asc(),
                FittingSupplierOfferModel.id.asc(),
            )
            .all()
        )

        supplier_ids = [
            int(row.supplier_id)
            for row in rows
        ]
        suppliers = {}
        if supplier_ids:
            supplier_rows = (
                db.query(SupplierModel)
                .filter(SupplierModel.id.in_(supplier_ids))
                .all()
            )
            suppliers = {int(row.id): row for row in supplier_rows}

        serialized_rows = []
        for row in rows:
            supplier = suppliers.get(int(row.supplier_id))
            if supplier is not None:
                row.supplier = supplier
            serialized_rows.append(_serialize_fitting_supplier_offer(row))

        return serialized_rows
    finally:
        db.close()


def update_fitting_price_fields(
    *,
    item_id: str | int,
    price: float | None | object = _UNSET,
    stock: str | None | object = _UNSET,
    currency: str | None | object = _UNSET,
    parsed_at: datetime | None | object = _UNSET,
    price_updated_at: datetime | None | object = _UNSET,
) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(FittingModel)
            .filter(FittingModel.id == int(item_id))
            .first()
        )

        if not item:
            return None

        if price is not _UNSET:
            item.price = _normalize_price_value(price)
        if stock is not _UNSET:
            item.stock = _normalize_fitting_value(stock)
        if currency is not _UNSET:
            item.currency = _normalize_fitting_value(currency)
        if parsed_at is not _UNSET:
            item.parsed_at = parsed_at
        if price_updated_at is not _UNSET:
            item.price_updated_at = price_updated_at

        db.commit()
        db.refresh(item)

        return {
            "id": str(item.id),
            "article": item.article,
            "city": item.city,
            "price": item.price,
            "stock": item.stock,
            "currency": item.currency,
            "parsed_at": item.parsed_at,
            "price_updated_at": item.price_updated_at,
        }

    finally:

        db.close()


def delete_fitting(item_id: str | int) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(FittingModel)
            .filter(FittingModel.id == int(item_id))
            .first()
        )

        if not item:
            return None

        db.query(MountingNodeItemModel).filter(
            MountingNodeItemModel.fitting_id == int(item.id),
        ).delete(synchronize_session=False)

        template_ids = [
            row[0]
            for row in db.query(FittingHoleTemplateModel.id)
            .filter(FittingHoleTemplateModel.fitting_id == int(item.id))
            .all()
        ]

        if template_ids:
            db.query(FittingHolePointModel).filter(
                FittingHolePointModel.template_id.in_(template_ids),
            ).delete(synchronize_session=False)

        db.query(FittingSupplierOfferModel).filter(
            FittingSupplierOfferModel.fitting_id == int(item.id),
        ).delete(synchronize_session=False)

        signature = _build_fitting_delete_signature(item)
        candidates = _list_fitting_delete_candidates(db, item)
        rows_to_delete = [
            candidate
            for candidate in candidates
            if _fitting_matches_delete_signature(candidate, signature)
        ]

        if (
            _get_fitting_catalog_key(item).startswith("name:")
            and len(rows_to_delete) > 1
        ):
            return None

        if not rows_to_delete:
            rows_to_delete = [item]

        row_ids = [int(row.id) for row in rows_to_delete]
        selected_item_id = str(item.id)
        deleted_items = [
            _serialize_fitting(row)
            for row in rows_to_delete
        ]
        deleted_ids = [row["id"] for row in deleted_items]
        deleted_cities = [
            row["city"]
            for row in deleted_items
            if row.get("city") is not None
        ]

        # Remove fitting-owned children before deleting the parent rows.
        # Mounting-node dependencies are blocked at the route level and are
        # intentionally not removed here.
        if template_ids:
            db.query(FittingHolePointModel).filter(
                FittingHolePointModel.template_id.in_(template_ids),
            ).delete(synchronize_session=False)

            db.query(FittingHoleTemplateModel).filter(
                FittingHoleTemplateModel.id.in_(template_ids),
            ).delete(synchronize_session=False)

        db.query(FittingSupplierOfferModel).filter(
            FittingSupplierOfferModel.fitting_id == int(item.id),
        ).delete(synchronize_session=False)

        db.query(FittingImageModel).filter(
            FittingImageModel.fitting_id.in_(row_ids)
        ).delete(synchronize_session=False)

        db.query(FittingModel).filter(
            FittingModel.id.in_(row_ids),
        ).delete(synchronize_session=False)

        db.commit()

        primary_item = deleted_items[0] if deleted_items else _serialize_fitting(item)

        return {
            "success": True,
            "selected_item_id": selected_item_id,
            "deleted_count": len(deleted_items),
            "deleted_ids": deleted_ids,
            "deleted_cities": deleted_cities,
            "item": primary_item,
        }

    except Exception:
        db.rollback()
        return None

    finally:

        db.close()


def delete_fittings_exact(item_ids: Sequence[str | int], db=None) -> list[dict]:

    owns_session = db is None
    db = db or SessionLocal()

    try:
        fitting_ids = [
            int(item_id)
            for item_id in item_ids
            if item_id not in (None, "")
        ]
        deleted_items = _delete_exact_fittings(db, fitting_ids)
        if not deleted_items:
            return []

        if owns_session:
            db.commit()
        return deleted_items

    except Exception:
        db.rollback()
        raise

    finally:
        if owns_session:
            db.close()


def list_fitting_delete_dependencies(item_id: str | int) -> list[dict]:

    db = SessionLocal()

    try:
        item = (
            db.query(FittingModel.id)
            .filter(FittingModel.id == int(item_id))
            .first()
        )

        if not item:
            return []

        item_rows = (
            db.query(
                MountingNodeModel.id,
                MountingNodeModel.code,
                MountingNodeModel.name,
            )
            .join(MountingNodeItemModel, MountingNodeItemModel.node_id == MountingNodeModel.id)
            .filter(MountingNodeItemModel.fitting_id == int(item_id))
            .filter(MountingNodeModel.is_archived.is_(False))
            .order_by(
                MountingNodeModel.name.asc(),
                MountingNodeModel.code.asc(),
                MountingNodeModel.id.asc(),
            )
            .distinct()
            .all()
        )

        template_rows = (
            db.query(
                MountingNodeModel.id,
                MountingNodeModel.code,
                MountingNodeModel.name,
            )
            .join(MountingNodeTemplateModel, MountingNodeTemplateModel.node_id == MountingNodeModel.id)
            .join(FittingHoleTemplateModel, FittingHoleTemplateModel.id == MountingNodeTemplateModel.template_id)
            .filter(FittingHoleTemplateModel.fitting_id == int(item_id))
            .filter(MountingNodeModel.is_archived.is_(False))
            .order_by(
                MountingNodeModel.name.asc(),
                MountingNodeModel.code.asc(),
                MountingNodeModel.id.asc(),
            )
            .distinct()
            .all()
        )

        merged_rows: dict[int, dict] = {}
        for row in list(item_rows) + list(template_rows):
            merged_rows[int(row[0])] = {
                "id": int(row[0]),
                "code": str(row[1] or ""),
                "name": str(row[2] or ""),
            }

        return [
            {
                "id": data["id"],
                "code": data["code"],
                "name": data["name"],
            }
            for data in sorted(
                merged_rows.values(),
                key=lambda entry: (
                    str(entry["name"] or ""),
                    str(entry["code"] or ""),
                    int(entry["id"] or 0),
                ),
            )
        ]
    finally:
        db.close()


def get_fitting_image_by_id(item_id: str | int) -> dict | None:
    db = SessionLocal()

    try:
        item = db.query(FittingModel).filter(FittingModel.id == int(item_id)).first()

        if not item:
            return None

        return {
            "id": str(item.id),
            "image_url": item.image_url,
            "source_url": item.source_url,
            "city": item.city,
            "image_cached_bytes": item.image_cached_bytes,
            "image_cached_content_type": item.image_cached_content_type,
        }
    finally:
        db.close()


def update_fitting_image_cache(
    item_id: str | int,
    image_bytes: bytes | None,
    content_type: str | None,
) -> dict | None:
    db = SessionLocal()

    try:
        item = db.query(FittingModel).filter(FittingModel.id == int(item_id)).first()

        if not item:
            return None

        item.image_cached_bytes = image_bytes
        item.image_cached_content_type = content_type
        db.commit()

        return {
            "id": str(item.id),
            "has_cached_image": bool(item.image_cached_bytes),
            "image_cached_content_type": item.image_cached_content_type,
        }
    finally:
        db.close()


def get_material_by_article(
    article: str,
    viewer_user_id: str | None = None,
    viewer_role: str | None = None,
    city: str | None = None,
) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(MaterialModel)
            .filter(MaterialModel.article == article)
            .first()
        )

        if not item:
            return None

        manufacturer_profile = None
        if item.manufacturer_id is not None:
            manufacturer_profile = _load_material_manufacturer_profiles(
                db,
                [item.manufacturer_id],
            ).get(int(item.manufacturer_id))

        if (viewer_user_id is not None or viewer_role is not None) and not _material_visible_to_viewer(
            item,
            viewer_user_id=viewer_user_id,
            viewer_role=viewer_role,
            linked_article_ids=_load_material_user_links(db, viewer_user_id),
        ):
            return None

        price_summary = _build_material_price_summary_payload(
            db,
            [int(item.id)],
            city=city,
        ).get(int(item.id), [])
        supports_square_meter_sale = bool(
            _build_material_square_meter_support_payload(
                db,
                [int(item.id)],
                city=city,
            ).get(int(item.id))
        )
        supplier_summary = _build_material_supplier_summary_payload(
            db,
            [int(item.id)],
            city=city,
        ).get(int(item.id), [])

        return {
            "id": str(item.id),
            "article": item.article,
            "display_article": (
                None
                if (not item.source_url and str(item.article or "").startswith("manual-"))
                else item.article
            ),
            "name": item.name,
            "description": item.description,
            "color": item.color,
            "dimensions": item.dimensions,
            "thickness": item.thickness,
            "category": item.category,
            "manufacturer_id": int(item.manufacturer_id) if item.manufacturer_id is not None else None,
            "manufacturer_name": (manufacturer_profile or {}).get("name"),
            "manufacturer_logo_url": (manufacturer_profile or {}).get("logo_url"),
            "image": item.image,
            "source_url": item.source_url,
            "source": item.source,
            "product_type": item.product_type or item.category,
            "source_site": _detect_source_site(item.source_url),
            "tg_file_id": item.tg_file_id,
            "owner_user_id": item.owner_user_id,
            "is_default": bool(item.is_default),
            "has_cached_image": bool(item.image_cached_bytes),
            "image_cached_bytes": item.image_cached_bytes,
            "image_cached_content_type": item.image_cached_content_type,
            "image_source_url": item.image_source_url or item.image,
            "image_cached_hash": item.image_cached_hash,
            "images": _list_material_images_for_db(db, int(item.id)),
            "imported_at": item.imported_at,
            "static_updated_at": item.static_updated_at,
            "prices": [
                _serialize_material_price_row(price)
                for price in sorted(
                    (
                        db.query(MaterialPriceModel)
                        .filter(MaterialPriceModel.article == item.article)
                        .all()
                    ),
                    key=lambda row: ((row.city or ""), row.id),
                )
            ],
            "current_price_details": None,
            "price_summary": price_summary,
            "supports_square_meter_sale": supports_square_meter_sale,
            "supplier_summary": supplier_summary,
            "supplier_offers": _list_material_supplier_offers(db, item.id, city=city),
            "edge_options": [
                *(
                    _load_material_edges_payload(
                        db,
                        [item.article],
                        city=city,
                    ).get(item.article, [])
                ),
                *(
                    _load_material_canonical_edges_payload(
                        db,
                        [int(item.id)],
                        material_articles=[item.article],
                        city=city,
                    ).get(item.article, [])
                ),
            ],
        }

    finally:

        db.close()


def list_material_images(material_id: str | int) -> list[dict]:

    db = SessionLocal()

    try:
        return _list_material_images_for_db(db, int(material_id))
    finally:
        db.close()


def get_material_image_by_id(article: str, image_id: str | int) -> dict | None:

    db = SessionLocal()

    try:
        material = (
            db.query(MaterialModel)
            .filter(MaterialModel.article == article)
            .first()
        )
        if not material:
            return None

        row = (
            db.query(MaterialImageModel)
            .options(
                load_only(
                    MaterialImageModel.id,
                    MaterialImageModel.material_id,
                    MaterialImageModel.image_cached_bytes,
                    MaterialImageModel.image_cached_content_type,
                )
            )
            .filter(MaterialImageModel.material_id == int(material.id))
            .filter(MaterialImageModel.id == int(image_id))
            .first()
        )

        if not row or not row.image_cached_bytes or not row.image_cached_content_type:
            return None

        return _serialize_material_image_blob(row)
    finally:
        db.close()


def update_material(
    article: str,
    *,
    name: str | None | object = _UNSET,
    description: str | None | object = _UNSET,
    color: str | None | object = _UNSET,
    dimensions: str | None | object = _UNSET,
    thickness: str | None | object = _UNSET,
    manufacturer_id: int | None | object = _UNSET,
    price: float | None | object = _UNSET,
    price_city: str | None = None,
) -> dict | None:

    db = SessionLocal()

    try:
        item = (
            db.query(MaterialModel)
            .filter(MaterialModel.article == article)
            .first()
        )

        if not item:
            return None

        if name is not _UNSET:
            item.name = _normalize_source(name)
        if description is not _UNSET:
            item.description = _normalize_source(description)
        if color is not _UNSET:
            item.color = _normalize_source(color)
        if dimensions is not _UNSET:
            item.dimensions = _normalize_source(dimensions)
        if thickness is not _UNSET:
            item.thickness = _normalize_source(thickness)
        if manufacturer_id is not _UNSET:
            item.manufacturer_id = int(manufacturer_id) if manufacturer_id is not None else None

        if price is not _UNSET:
            normalized_city = _normalize_source(price_city)
            if not normalized_city:
                raise ValueError("price_city is required when price is provided")

            price_row = (
                db.query(MaterialPriceModel)
                .filter(
                    MaterialPriceModel.article == item.article,
                    MaterialPriceModel.city == normalized_city,
                )
                .first()
            )

            if not price_row:
                price_row = MaterialPriceModel(
                    article=item.article,
                    city=normalized_city,
                )
                db.add(price_row)

            price_row.price = _normalize_price_value(price)
            price_row.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(item)

        return {
            "article": item.article,
        }

    except Exception:
        db.rollback()
        raise

    finally:

        db.close()


def upsert_material(
    article: str,
    name: str,
    category: str,
    description: str | None = None,
    color: str | None = None,
    dimensions: str | None = None,
    thickness: str | None = None,
    image: str | None = None,
    source_url: str | None = None,
    tg_file_id: str | None = None,
    owner_user_id: str | None = None,
    is_default: bool | None = None,
    source: str | None = None,
    product_type: str | None = None,
    image_source_url: str | None = None,
    image_cached_hash: str | None = None,
    imported_at: datetime | None = None,
    static_updated_at: datetime | None = None,
    manufacturer_id: int | None | object = _UNSET,
    prepared_gallery_images: Sequence[PreparedFittingGalleryImage] | None = None,
    allow_deleted_restore: bool = False,
) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(MaterialModel)
            .filter(MaterialModel.article == article)
            .first()
        )

        if not item:
            if not allow_deleted_restore and is_auto_recreate_suppressed(db, "material", article):
                return None

            item = MaterialModel(
                article=article,
            )
            db.add(item)

        item.name = name
        item.description = description
        item.color = color
        item.dimensions = dimensions
        item.thickness = thickness
        item.category = category
        item.source = _normalize_source(source) or _detect_source_site(source_url)
        item.product_type = _normalize_source(product_type) or category
        if manufacturer_id is not _UNSET:
            item.manufacturer_id = int(manufacturer_id) if manufacturer_id is not None else None
        normalized_new_image = str(image or "").strip() or None
        normalized_old_image = str(item.image or "").strip() or None

        if normalized_new_image != normalized_old_image:
            # The binary cache is derived from the parsed image URL. Never keep
            # serving old bytes after the parser discovers a new source image.
            item.image_cached_bytes = None
            item.image_cached_content_type = None
            item.image_cached_hash = None

        item.image = normalized_new_image
        item.image_source_url = _normalize_import_source_url(image_source_url or image)
        if image_cached_hash is not None:
            item.image_cached_hash = image_cached_hash
        if source_url is not None:
            item.source_url = _normalize_import_source_url(source_url)
        if tg_file_id is not None:
            item.tg_file_id = tg_file_id
        if owner_user_id is not None or is_default is True:
            item.owner_user_id = owner_user_id
        if is_default is not None:
            item.is_default = bool(is_default)
        if imported_at is not None and item.imported_at is None:
            item.imported_at = imported_at
        if static_updated_at is not None:
            item.static_updated_at = static_updated_at
        if prepared_gallery_images is not None:
            if item.id is None:
                db.flush()
            db.query(MaterialImageModel).filter(
                MaterialImageModel.material_id == int(item.id)
            ).delete(synchronize_session=False)
            if prepared_gallery_images:
                _add_prepared_material_gallery_images(
                    db,
                    material_id=int(item.id),
                    prepared_gallery_images=prepared_gallery_images,
                )

        db.commit()
        db.refresh(item)

        return {
            "id": str(item.id),
            "article": item.article,
            "display_article": (
                None
                if (not item.source_url and str(item.article or "").startswith("manual-"))
                else item.article
            ),
            "name": item.name,
            "description": item.description,
            "color": item.color,
            "dimensions": item.dimensions,
            "thickness": item.thickness,
            "category": item.category,
            "manufacturer_id": int(item.manufacturer_id) if item.manufacturer_id is not None else None,
            "manufacturer_name": (
                _load_material_manufacturer_profiles(db, [item.manufacturer_id]).get(int(item.manufacturer_id), {}).get("name")
                if item.manufacturer_id is not None
                else None
            ),
            "manufacturer_logo_url": (
                _load_material_manufacturer_profiles(db, [item.manufacturer_id]).get(int(item.manufacturer_id), {}).get("logo_url")
                if item.manufacturer_id is not None
                else None
            ),
            "image": item.image,
            "source_url": item.source_url,
            "source": item.source,
            "product_type": item.product_type,
            "source_site": _detect_source_site(item.source_url),
            "tg_file_id": item.tg_file_id,
            "owner_user_id": item.owner_user_id,
            "is_default": bool(item.is_default),
            "has_cached_image": bool(item.image_cached_bytes),
            "image_cached_bytes": item.image_cached_bytes,
            "image_cached_content_type": item.image_cached_content_type,
            "image_source_url": item.image_source_url,
            "image_cached_hash": item.image_cached_hash,
            "images": _list_material_images_for_db(db, int(item.id)),
            "imported_at": item.imported_at,
            "static_updated_at": item.static_updated_at,
        }

    finally:

        db.close()


def delete_material(article: str) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(MaterialModel)
            .filter(MaterialModel.article == article)
            .first()
        )

        if not item:
            return None

        (
            db.query(MaterialPriceModel)
            .filter(MaterialPriceModel.article == article)
            .delete(synchronize_session=False)
        )
        (
            db.query(MaterialUserLinkModel)
            .filter(MaterialUserLinkModel.material_article == article)
            .delete(synchronize_session=False)
        )
        db.query(MaterialImageModel).filter(
            MaterialImageModel.material_id == int(item.id)
        ).delete(synchronize_session=False)
        db.delete(item)
        db.commit()

        return {
            "deleted": True,
            "is_default": bool(item.is_default),
        }

    finally:

        db.close()


def update_material_image_cache(
    article: str,
    image_bytes: bytes | None,
    content_type: str | None,
) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(MaterialModel)
            .filter(MaterialModel.article == article)
            .first()
        )

        if not item:
            return None

        item.image_cached_bytes = image_bytes
        item.image_cached_content_type = content_type
        item.image_cached_hash = _image_hash(image_bytes)

        db.commit()
        db.refresh(item)

        return {
            "article": item.article,
            "has_cached_image": bool(item.image_cached_bytes),
            "image_cached_content_type": item.image_cached_content_type,
        }

    finally:

        db.close()


def upsert_material_price(
    article: str,
    city: str,
    price: float | None,
    currency: str | None = None,
    availability: str | None = None,
    *,
    old_price: float | None | object = _UNSET,
    is_promo: bool | object = _UNSET,
    discount_percent: float | None | object = _UNSET,
    promo_label: str | None | object = _UNSET,
    promo_valid_until: date | None | object = _UNSET,
    source_checked_at: datetime | None | object = _UNSET,
) -> dict:

    db = SessionLocal()

    try:

        row = (
            db.query(MaterialPriceModel)
            .filter(
                MaterialPriceModel.article == article,
                MaterialPriceModel.city == city,
            )
            .first()
        )

        if not row:
            row = MaterialPriceModel(
                article=article,
                city=city,
            )
            db.add(row)

        row.price = price
        row.currency = _normalize_source(currency)
        row.availability = _normalize_source(availability)
        row.updated_at = datetime.utcnow()
        if old_price is not _UNSET:
            row.old_price = _normalize_price_value(old_price)
        if is_promo is not _UNSET:
            row.is_promo = bool(is_promo)
        if discount_percent is not _UNSET:
            row.discount_percent = _normalize_price_value(discount_percent)
        if promo_label is not _UNSET:
            row.promo_label = _normalize_source(promo_label)
        if promo_valid_until is not _UNSET:
            row.promo_valid_until = promo_valid_until
        if source_checked_at is not _UNSET:
            row.source_checked_at = source_checked_at

        db.commit()
        db.refresh(row)

        return {
            "article": row.article,
            "city": row.city,
            "price": row.price,
            "updated_at": row.updated_at,
        }

    finally:

        db.close()


def upsert_material_edge_option(
    *,
    material_article: str,
    edge_key: str,
    article: str | None,
    name: str | None,
    thickness_label: str | None,
    image: str | None,
    source_url: str | None,
    source: str | None = None,
    product_type: str | None = None,
    image_source_url: str | None = None,
    imported_at: datetime | None = None,
    static_updated_at: datetime | None = None,
) -> dict:

    db = SessionLocal()

    try:

        item = (
            db.query(MaterialEdgeModel)
            .filter(
                MaterialEdgeModel.material_article == material_article,
                MaterialEdgeModel.edge_key == edge_key,
            )
            .first()
        )

        if not item:
            item = MaterialEdgeModel(
                material_article=material_article,
                edge_key=edge_key,
            )
            db.add(item)

        item.article = article
        item.name = name
        item.thickness_label = thickness_label
        normalized_image = str(image or "").strip() or None

        if normalized_image != item.image:
            item.image_cached_bytes = None
            item.image_cached_content_type = None
            item.image_cached_hash = None

        item.image = normalized_image
        item.image_source_url = _normalize_import_source_url(image_source_url or image)
        item.source = _normalize_source(source) or _detect_source_site(source_url)
        item.product_type = _normalize_source(product_type) or edge_key
        item.source_url = _normalize_import_source_url(source_url)
        if imported_at is not None and item.imported_at is None:
            item.imported_at = imported_at
        if static_updated_at is not None:
            item.static_updated_at = static_updated_at

        db.commit()
        db.refresh(item)

        return {
            "id": str(item.id),
            "material_article": item.material_article,
            "edge_key": item.edge_key,
        }

    finally:

        db.close()


def upsert_material_edge_price(
    *,
    edge_option_id: int | str,
    city: str,
    price: float | None,
    currency: str | None = None,
    availability: str | None = None,
) -> dict:

    db = SessionLocal()

    try:

        row = (
            db.query(MaterialEdgePriceModel)
            .filter(
                MaterialEdgePriceModel.edge_option_id == int(edge_option_id),
                MaterialEdgePriceModel.city == city,
            )
            .first()
        )

        if not row:
            row = MaterialEdgePriceModel(
                edge_option_id=int(edge_option_id),
                city=city,
            )
            db.add(row)

        row.price = _normalize_price_value(price)
        row.currency = _normalize_source(currency)
        row.availability = _normalize_source(availability)
        row.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(row)

        return {
            "id": str(row.id),
            "edge_option_id": str(row.edge_option_id),
            "city": row.city,
            "price": row.price,
        }

    finally:

        db.close()


def list_material_price_refresh_targets(
    stale_hours: int = 24,
    limit: int = 20,
) -> list[dict]:

    db = SessionLocal()

    try:

        cutoff = datetime.utcnow() - timedelta(hours=max(1, stale_hours))
        stale_rows = (
            db.query(MaterialModel, MaterialPriceModel)
            .join(
                MaterialPriceModel,
                MaterialPriceModel.article == MaterialModel.article,
            )
            .filter(MaterialPriceModel.city.isnot(None))
            .filter(
                (MaterialPriceModel.updated_at.is_(None))
                | (MaterialPriceModel.updated_at <= cutoff)
            )
            .order_by(MaterialPriceModel.updated_at.asc().nullsfirst(), MaterialModel.article.asc())
            .limit(limit)
            .all()
        )
        targets = [
            {
                "article": material.article,
                "category": material.category or "dsp",
                "city": price.city,
                "source_url": material.source_url,
                "updated_at": price.updated_at,
            }
            for material, price in stale_rows
            if material.article and price.city
        ]

        if len(targets) >= limit:
            return targets[:limit]

        known_price_pairs = {
            (row.article, row.city)
            for row in db.query(MaterialPriceModel.article, MaterialPriceModel.city)
            .filter(MaterialPriceModel.article.isnot(None))
            .filter(MaterialPriceModel.city.isnot(None))
            .all()
        }
        queued_pairs = {
            (target["article"], target["city"])
            for target in targets
        }
        active_user_cities = [
            row[0]
            for row in db.query(UserModel.city)
            .filter(UserModel.is_active.is_(True))
            .filter(UserModel.city.isnot(None))
            .distinct()
            .order_by(UserModel.city.asc())
            .all()
            if row[0]
        ]
        materials = (
            db.query(MaterialModel)
            .filter(MaterialModel.article.isnot(None))
            .order_by(MaterialModel.article.asc())
            .all()
        )

        for city in active_user_cities:
            for material in materials:
                pair = (material.article, city)

                if pair in known_price_pairs or pair in queued_pairs:
                    continue

                targets.append(
                    {
                        "article": material.article,
                        "category": material.category or "dsp",
                        "city": city,
                        "source_url": material.source_url,
                        "updated_at": None,
                    }
                )
                queued_pairs.add(pair)

                if len(targets) >= limit:
                    return targets[:limit]

        return targets[:limit]

    finally:

        db.close()
