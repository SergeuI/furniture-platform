from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from database.models.fitting_hole_service_rule import FittingHoleServiceRuleModel
from database.models.service_catalog_item import ServiceCatalogItemModel
from database.models.user_service_catalog_price import UserServiceCatalogPriceModel
from database.session import SessionLocal


def _serialize_service_catalog_item(item, user_price=None) -> dict[str, Any] | None:
    if not item:
        return None

    effective_price = (
        user_price.base_price
        if user_price and user_price.base_price is not None
        else item.base_price
    )
    effective_currency = (
        user_price.currency
        if user_price and user_price.currency
        else item.currency
    )

    return {
        "id": item.id,
        "source": item.source,
        "external_code": item.external_code,
        "parent_external_code": item.parent_external_code,
        "owner_user_id": item.owner_user_id,
        "name": item.name,
        "slug": item.slug,
        "item_type": item.item_type,
        "folder_path": item.folder_path,
        "description": item.description,
        "article": item.article,
        "unit": item.unit,
        "base_price": item.base_price,
        "currency": item.currency,
        "source_url": item.source_url,
        "is_calculable": item.is_calculable,
        "sort_order": item.sort_order,
        "is_active": item.is_active,
        "last_synced_at": item.last_synced_at,
        "price_sync_status": item.price_sync_status,
        "price_source_label": item.price_source_label,
        "effective_price": effective_price,
        "effective_currency": effective_currency,
        "user_price": user_price.base_price if user_price else None,
        "user_currency": user_price.currency if user_price else None,
        "user_last_synced_at": user_price.last_synced_at if user_price else None,
        "user_price_sync_status": user_price.price_sync_status if user_price else None,
        "user_price_source_label": user_price.price_source_label if user_price else None,
    }


def _serialize_rule(rule, user_price=None) -> dict[str, Any]:
    service_item = getattr(rule, "service_catalog_item", None)
    return {
        "id": rule.id,
        "operation": rule.operation,
        "diameter_min_mm": rule.diameter_min_mm,
        "diameter_max_mm": rule.diameter_max_mm,
        "depth_min_mm": rule.depth_min_mm,
        "depth_max_mm": rule.depth_max_mm,
        "service_catalog_item_id": rule.service_catalog_item_id,
        "source": rule.source,
        "city": rule.city,
        "is_active": bool(rule.is_active),
        "priority": int(rule.priority or 0),
        "notes": rule.notes,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "service_catalog_item": _serialize_service_catalog_item(service_item, user_price=user_price),
    }


def _matches_optional_range(value: float | None, minimum: float | None, maximum: float | None) -> bool:
    if value is None:
        return True
    if minimum is not None and value < minimum:
        return False
    if maximum is not None and value > maximum:
        return False
    return True


def _build_rule_query(db, include_inactive: bool = False):
    query = (
        db.query(FittingHoleServiceRuleModel)
        .join(ServiceCatalogItemModel, ServiceCatalogItemModel.id == FittingHoleServiceRuleModel.service_catalog_item_id)
        .filter(ServiceCatalogItemModel.item_type == "service")
        .filter(ServiceCatalogItemModel.is_calculable.is_(True))
        .filter(ServiceCatalogItemModel.is_active.is_(True))
    )

    if not include_inactive:
        query = query.filter(FittingHoleServiceRuleModel.is_active.is_(True))

    return query


def _load_user_price_map(db, user_id: str | None) -> dict[str, UserServiceCatalogPriceModel]:
    if not user_id:
        return {}

    user_prices = (
        db.query(UserServiceCatalogPriceModel)
        .filter(UserServiceCatalogPriceModel.user_id == user_id)
        .all()
    )
    return {
        price.service_catalog_item_id: price
        for price in user_prices
    }


def list_fitting_hole_service_rules(
    include_inactive: bool = False,
    operation: str | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        query = _build_rule_query(db, include_inactive=include_inactive)
        if operation:
            query = query.filter(FittingHoleServiceRuleModel.operation == operation)

        user_prices_by_item_id = _load_user_price_map(db, user_id)
        rules = (
            query.order_by(
                FittingHoleServiceRuleModel.priority.asc(),
                FittingHoleServiceRuleModel.id.asc(),
            )
            .all()
        )
        return [
            _serialize_rule(rule, user_price=user_prices_by_item_id.get(rule.service_catalog_item_id))
            for rule in rules
        ]
    finally:
        db.close()


def get_fitting_hole_service_rule(
    rule_id: int,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        user_prices_by_item_id = _load_user_price_map(db, user_id)
        rule = (
            db.query(FittingHoleServiceRuleModel)
            .join(ServiceCatalogItemModel, ServiceCatalogItemModel.id == FittingHoleServiceRuleModel.service_catalog_item_id)
            .filter(FittingHoleServiceRuleModel.id == rule_id)
            .one_or_none()
        )
        return (
            _serialize_rule(rule, user_price=user_prices_by_item_id.get(rule.service_catalog_item_id))
            if rule
            else None
        )
    finally:
        db.close()


def create_fitting_hole_service_rule(payload: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        service_item = (
            db.query(ServiceCatalogItemModel)
            .filter(ServiceCatalogItemModel.id == payload["service_catalog_item_id"])
            .filter(ServiceCatalogItemModel.item_type == "service")
            .filter(ServiceCatalogItemModel.is_calculable.is_(True))
            .filter(ServiceCatalogItemModel.is_active.is_(True))
            .one_or_none()
        )
        if service_item is None:
            raise ValueError("Service catalog item does not exist or is not calculable")

        rule = FittingHoleServiceRuleModel(
            operation=str(payload["operation"]).strip(),
            diameter_min_mm=payload.get("diameter_min_mm"),
            diameter_max_mm=payload.get("diameter_max_mm"),
            depth_min_mm=payload.get("depth_min_mm"),
            depth_max_mm=payload.get("depth_max_mm"),
            service_catalog_item_id=service_item.id,
            source=(str(payload.get("source")).strip() or None) if payload.get("source") is not None else None,
            city=(str(payload.get("city")).strip() or None) if payload.get("city") is not None else None,
            is_active=bool(payload.get("is_active", True)),
            priority=int(payload.get("priority", 0) or 0),
            notes=(str(payload.get("notes")).strip() or None) if payload.get("notes") is not None else None,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return _serialize_rule(rule)
    finally:
        db.close()


def update_fitting_hole_service_rule(rule_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        rule = (
            db.query(FittingHoleServiceRuleModel)
            .filter(FittingHoleServiceRuleModel.id == rule_id)
            .one_or_none()
        )
        if rule is None:
            return None

        if "operation" in payload:
            operation = str(payload.get("operation") or "").strip()
            if not operation:
                raise ValueError("operation is required")
            rule.operation = operation

        for field in ("diameter_min_mm", "diameter_max_mm", "depth_min_mm", "depth_max_mm"):
            if field in payload:
                value = payload.get(field)
                rule_value = None if value in (None, "") else float(value)
                setattr(rule, field, rule_value)

        if "service_catalog_item_id" in payload:
            service_item = (
                db.query(ServiceCatalogItemModel)
                .filter(ServiceCatalogItemModel.id == payload["service_catalog_item_id"])
                .filter(ServiceCatalogItemModel.item_type == "service")
                .filter(ServiceCatalogItemModel.is_calculable.is_(True))
                .filter(ServiceCatalogItemModel.is_active.is_(True))
                .one_or_none()
            )
            if service_item is None:
                raise ValueError("Service catalog item does not exist or is not calculable")
            rule.service_catalog_item_id = service_item.id

        if "source" in payload:
            text = "" if payload.get("source") is None else str(payload.get("source")).strip()
            rule.source = text or None

        if "city" in payload:
            text = "" if payload.get("city") is None else str(payload.get("city")).strip()
            rule.city = text or None

        if "is_active" in payload:
            rule.is_active = bool(payload.get("is_active"))

        if "priority" in payload:
            rule.priority = int(payload.get("priority") or 0)

        if "notes" in payload:
            text = "" if payload.get("notes") is None else str(payload.get("notes")).strip()
            rule.notes = text or None

        db.commit()
        db.refresh(rule)
        return _serialize_rule(rule)
    finally:
        db.close()


def deactivate_fitting_hole_service_rule(rule_id: int) -> dict[str, Any] | None:
    return update_fitting_hole_service_rule(rule_id, {"is_active": False})


def resolve_fitting_hole_service_rule(
    operation: str,
    diameter_mm: float | None = None,
    depth_mm: float | None = None,
    source: str | None = None,
    city: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        query = _build_rule_query(db, include_inactive=False)
        query = query.filter(FittingHoleServiceRuleModel.operation == operation)

        if source:
            query = query.filter(
                or_(
                    FittingHoleServiceRuleModel.source.is_(None),
                    FittingHoleServiceRuleModel.source == "",
                    FittingHoleServiceRuleModel.source == source,
                )
            )

        if city:
            query = query.filter(
                or_(
                    FittingHoleServiceRuleModel.city.is_(None),
                    FittingHoleServiceRuleModel.city == "",
                    FittingHoleServiceRuleModel.city == city,
                )
            )

        rules = (
            query.order_by(
                FittingHoleServiceRuleModel.priority.asc(),
                FittingHoleServiceRuleModel.id.asc(),
            )
            .all()
        )
        user_prices_by_item_id = _load_user_price_map(db, user_id)

        for rule in rules:
            if not _matches_optional_range(diameter_mm, rule.diameter_min_mm, rule.diameter_max_mm):
                continue
            if not _matches_optional_range(depth_mm, rule.depth_min_mm, rule.depth_max_mm):
                continue
            return _serialize_rule(
                rule,
                user_price=user_prices_by_item_id.get(rule.service_catalog_item_id),
            )

        return None
    finally:
        db.close()


__all__ = [
    "create_fitting_hole_service_rule",
    "deactivate_fitting_hole_service_rule",
    "get_fitting_hole_service_rule",
    "list_fitting_hole_service_rules",
    "resolve_fitting_hole_service_rule",
    "update_fitting_hole_service_rule",
]
