from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from database.models.fitting import (
    FittingCategoryModel,
    FittingModel,
    FittingManufacturerModel,
    FittingProductModel,
    FittingSeriesModel,
)
from database.session import SessionLocal


def _normalize_text(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_code(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_int(value: int | str | None) -> int | None:
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _serialize_manufacturer(item: FittingManufacturerModel) -> dict:
    return {
        "id": int(item.id),
        "code": item.code,
        "name": item.name,
        "description": item.description,
        "website_url": item.website_url,
        "logo_url": item.logo_url,
        "country_code": item.country_code,
        "is_active": bool(item.is_active),
        "sort_order": int(item.sort_order or 0),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _serialize_series(item: FittingSeriesModel) -> dict:
    return {
        "id": int(item.id),
        "manufacturer_id": int(item.manufacturer_id),
        "code": item.code,
        "name": item.name,
        "description": item.description,
        "is_active": bool(item.is_active),
        "sort_order": int(item.sort_order or 0),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _serialize_category(item: FittingCategoryModel) -> dict:
    return {
        "id": int(item.id),
        "code": item.code,
        "name": item.name,
        "parent_id": int(item.parent_id) if item.parent_id is not None else None,
        "description": item.description,
        "is_active": bool(item.is_active),
        "sort_order": int(item.sort_order or 0),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _serialize_product(item: FittingProductModel) -> dict:
    return {
        "id": int(item.id),
        "article": item.article,
        "code": item.code,
        "name": item.name,
        "brand": item.brand,
        "description": item.description,
        "manufacturer_id": int(item.manufacturer_id) if item.manufacturer_id is not None else None,
        "series_id": int(item.series_id) if item.series_id is not None else None,
        "category_id": int(item.category_id) if item.category_id is not None else None,
        "is_active": bool(item.is_active),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _list_query_filters(active_only: bool):
    return [FittingProductModel.is_active.is_(True)] if active_only else []


def list_fitting_manufacturers(*, active_only: bool = True) -> list[dict]:
    db = SessionLocal()
    try:
        query = db.query(FittingManufacturerModel)
        if active_only:
            query = query.filter(FittingManufacturerModel.is_active.is_(True))
        rows = query.order_by(
            FittingManufacturerModel.sort_order.asc(),
            FittingManufacturerModel.name.asc(),
            FittingManufacturerModel.code.asc(),
            FittingManufacturerModel.id.asc(),
        ).all()
        return [_serialize_manufacturer(item) for item in rows]
    finally:
        db.close()


def get_fitting_manufacturer_by_id(item_id: str | int) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingManufacturerModel, int(item_id))
        return _serialize_manufacturer(item) if item else None
    finally:
        db.close()


def create_fitting_manufacturer(
    *,
    code: str,
    name: str,
    description: str | None = None,
    website_url: str | None = None,
    logo_url: str | None = None,
    country_code: str | None = None,
    is_active: bool = True,
    sort_order: int = 0,
) -> dict | None:
    db = SessionLocal()
    try:
        item = FittingManufacturerModel(
            code=_normalize_code(code),
            name=_normalize_text(name),
            description=_normalize_text(description),
            website_url=_normalize_text(website_url),
            logo_url=_normalize_text(logo_url),
            country_code=_normalize_text(country_code),
            is_active=bool(is_active),
            sort_order=int(sort_order or 0),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return _serialize_manufacturer(item)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def update_fitting_manufacturer(
    item_id: str | int,
    *,
    code: str,
    name: str,
    description: str | None = None,
    website_url: str | None = None,
    logo_url: str | None = None,
    country_code: str | None = None,
    is_active: bool = True,
    sort_order: int = 0,
) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingManufacturerModel, int(item_id))
        if not item:
            return None

        item.code = _normalize_code(code)
        item.name = _normalize_text(name) or item.name
        item.description = _normalize_text(description)
        item.website_url = _normalize_text(website_url)
        item.logo_url = _normalize_text(logo_url)
        item.country_code = _normalize_text(country_code)
        item.is_active = bool(is_active)
        item.sort_order = int(sort_order or 0)
        db.commit()
        db.refresh(item)
        return _serialize_manufacturer(item)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def delete_fitting_manufacturer(item_id: str | int) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingManufacturerModel, int(item_id))
        if not item:
            return None

        serialized = _serialize_manufacturer(item)
        db.delete(item)
        db.commit()
        return serialized
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def list_fitting_series(
    *,
    manufacturer_id: int | None = None,
    active_only: bool = True,
) -> list[dict]:
    db = SessionLocal()
    try:
        query = db.query(FittingSeriesModel)
        if manufacturer_id is not None:
            query = query.filter(FittingSeriesModel.manufacturer_id == int(manufacturer_id))
        if active_only:
            query = query.filter(FittingSeriesModel.is_active.is_(True))
        rows = query.order_by(
            FittingSeriesModel.manufacturer_id.asc(),
            FittingSeriesModel.sort_order.asc(),
            FittingSeriesModel.name.asc(),
            FittingSeriesModel.code.asc(),
            FittingSeriesModel.id.asc(),
        ).all()
        return [_serialize_series(item) for item in rows]
    finally:
        db.close()


def get_fitting_series_by_id(item_id: str | int) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingSeriesModel, int(item_id))
        return _serialize_series(item) if item else None
    finally:
        db.close()


def create_fitting_series(
    *,
    manufacturer_id: int,
    code: str,
    name: str,
    description: str | None = None,
    is_active: bool = True,
    sort_order: int = 0,
) -> dict | None:
    db = SessionLocal()
    try:
        item = FittingSeriesModel(
            manufacturer_id=int(manufacturer_id),
            code=_normalize_code(code),
            name=_normalize_text(name) or "",
            description=_normalize_text(description),
            is_active=bool(is_active),
            sort_order=int(sort_order or 0),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return _serialize_series(item)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def update_fitting_series(
    item_id: str | int,
    *,
    manufacturer_id: int,
    code: str,
    name: str,
    description: str | None = None,
    is_active: bool = True,
    sort_order: int = 0,
) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingSeriesModel, int(item_id))
        if not item:
            return None

        item.manufacturer_id = int(manufacturer_id)
        item.code = _normalize_code(code)
        item.name = _normalize_text(name) or item.name
        item.description = _normalize_text(description)
        item.is_active = bool(is_active)
        item.sort_order = int(sort_order or 0)
        db.commit()
        db.refresh(item)
        return _serialize_series(item)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def delete_fitting_series(item_id: str | int) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingSeriesModel, int(item_id))
        if not item:
            return None

        serialized = _serialize_series(item)
        db.delete(item)
        db.commit()
        return serialized
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def list_fitting_categories(
    *,
    parent_id: int | None = None,
    active_only: bool = True,
) -> list[dict]:
    db = SessionLocal()
    try:
        query = db.query(FittingCategoryModel)
        if parent_id is not None:
            query = query.filter(FittingCategoryModel.parent_id == int(parent_id))
        if active_only:
            query = query.filter(FittingCategoryModel.is_active.is_(True))
        rows = query.order_by(
            FittingCategoryModel.parent_id.asc().nullsfirst(),
            FittingCategoryModel.sort_order.asc(),
            FittingCategoryModel.name.asc(),
            FittingCategoryModel.code.asc(),
            FittingCategoryModel.id.asc(),
        ).all()
        return [_serialize_category(item) for item in rows]
    finally:
        db.close()


def get_fitting_category_by_id(item_id: str | int) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingCategoryModel, int(item_id))
        return _serialize_category(item) if item else None
    finally:
        db.close()


def create_fitting_category(
    *,
    code: str,
    name: str,
    parent_id: int | None = None,
    description: str | None = None,
    is_active: bool = True,
    sort_order: int = 0,
) -> dict | None:
    db = SessionLocal()
    try:
        item = FittingCategoryModel(
            code=_normalize_code(code),
            name=_normalize_text(name) or "",
            parent_id=_normalize_int(parent_id),
            description=_normalize_text(description),
            is_active=bool(is_active),
            sort_order=int(sort_order or 0),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return _serialize_category(item)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def update_fitting_category(
    item_id: str | int,
    *,
    code: str,
    name: str,
    parent_id: int | None = None,
    description: str | None = None,
    is_active: bool = True,
    sort_order: int = 0,
) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingCategoryModel, int(item_id))
        if not item:
            return None

        item.code = _normalize_code(code)
        item.name = _normalize_text(name) or item.name
        item.parent_id = _normalize_int(parent_id)
        item.description = _normalize_text(description)
        item.is_active = bool(is_active)
        item.sort_order = int(sort_order or 0)
        db.commit()
        db.refresh(item)
        return _serialize_category(item)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def delete_fitting_category(item_id: str | int) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingCategoryModel, int(item_id))
        if not item:
            return None

        serialized = _serialize_category(item)
        db.delete(item)
        db.commit()
        return serialized
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def list_fitting_products(
    *,
    search: str | None = None,
    manufacturer_id: int | None = None,
    series_id: int | None = None,
    category_id: int | None = None,
    active_only: bool = True,
) -> list[dict]:
    db = SessionLocal()
    try:
        query = db.query(FittingProductModel)
        if search:
            search_value = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    FittingProductModel.name.ilike(search_value),
                    FittingProductModel.article.ilike(search_value),
                    FittingProductModel.code.ilike(search_value),
                    FittingProductModel.brand.ilike(search_value),
                )
            )
        if manufacturer_id is not None:
            query = query.filter(FittingProductModel.manufacturer_id == int(manufacturer_id))
        if series_id is not None:
            query = query.filter(FittingProductModel.series_id == int(series_id))
        if category_id is not None:
            query = query.filter(FittingProductModel.category_id == int(category_id))
        if active_only:
            query = query.filter(FittingProductModel.is_active.is_(True))
        rows = query.order_by(
            FittingProductModel.manufacturer_id.asc().nullsfirst(),
            FittingProductModel.series_id.asc().nullsfirst(),
            FittingProductModel.category_id.asc().nullsfirst(),
            FittingProductModel.name.asc(),
            FittingProductModel.article.asc().nullsfirst(),
            FittingProductModel.code.asc().nullsfirst(),
            FittingProductModel.id.asc(),
        ).all()
        return [_serialize_product(item) for item in rows]
    finally:
        db.close()


def get_fitting_product_by_id(item_id: str | int) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingProductModel, int(item_id))
        if not item:
            return None
        return _serialize_product(item)
    finally:
        db.close()


def delete_fitting_product(item_id: str | int) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingProductModel, int(item_id))
        if not item:
            return None

        serialized = _serialize_product(item)
        db.delete(item)
        db.commit()
        return serialized
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def update_fitting_product_taxonomy(
    item_id: str | int,
    *,
    manufacturer_id: int | None = None,
    series_id: int | None = None,
    category_id: int | None = None,
    is_active: bool | None = None,
) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(FittingProductModel, int(item_id))
        if not item:
            return None

        item.manufacturer_id = _normalize_int(manufacturer_id)
        item.series_id = _normalize_int(series_id)
        item.category_id = _normalize_int(category_id)
        if is_active is not None:
            item.is_active = bool(is_active)
        db.commit()
        db.refresh(item)
        return _serialize_product(item)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()
