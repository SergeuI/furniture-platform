from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from database.models.service_catalog_item import ServiceCatalogItemModel
from database.models.service_drilling_rule import ServiceDrillingRuleModel
from database.session import SessionLocal
from services.viyar_service_catalog_service import _extract_viyar_service_category


def _coerce_number_list(value: Any) -> list[float]:
    if value is None:
        return []

    if isinstance(value, str):
        raw_items = [item.strip() for item in value.split(",")]
        return [float(item) for item in raw_items if item]

    if isinstance(value, (int, float)):
        return [float(value)]

    if isinstance(value, list):
        normalized: list[float] = []
        for item in value:
            if item in (None, ""):
                continue
            normalized.append(float(item))
        return normalized

    raise ValueError("Expected a list of numbers")


def _serialize_service_catalog_item(item) -> dict[str, Any] | None:
    if not item:
        return None

    return {
        "id": item.id,
        "canonical_service_catalog_item_id": item.id,
        "source": item.source,
        "external_code": item.external_code,
        "parent_external_code": item.parent_external_code,
        "name": item.name,
        "article": item.article,
        "folder_path": item.folder_path,
        "base_price": item.base_price,
        "currency": item.currency,
        "is_active": bool(item.is_active),
    }


def _serialize_rule(rule) -> dict[str, Any]:
    service_item = getattr(rule, "service_catalog_item", None)
    return {
        "id": rule.id,
        "service_catalog_item_id": rule.service_catalog_item_id,
        "rule_name": rule.rule_name,
        "operation_type": rule.operation_type,
        "hole_type": rule.hole_type,
        "allowed_diameters": list(rule.allowed_diameters or []),
        "allowed_depths": list(rule.allowed_depths or []),
        "material_thickness_min": rule.material_thickness_min,
        "material_thickness_max": rule.material_thickness_max,
        "max_blind_depth_formula": rule.max_blind_depth_formula,
        "max_blind_depth_mm": rule.max_blind_depth_mm,
        "min_edge_offset_mm": rule.min_edge_offset_mm,
        "notes": rule.notes,
        "source": rule.source,
        "is_active": bool(rule.is_active),
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "service_catalog_item": _serialize_service_catalog_item(service_item),
    }


def _resolve_service_item(db, service_catalog_item_id: str):
    return (
        db.query(ServiceCatalogItemModel)
        .filter(ServiceCatalogItemModel.id == service_catalog_item_id)
        .filter(ServiceCatalogItemModel.source == "viyar")
        .filter(ServiceCatalogItemModel.item_type == "service")
        .filter(ServiceCatalogItemModel.is_active.is_(True))
        .one_or_none()
    )


def _build_rule_query(db, include_inactive: bool = False):
    query = (
        db.query(ServiceDrillingRuleModel)
        .join(ServiceCatalogItemModel, ServiceCatalogItemModel.id == ServiceDrillingRuleModel.service_catalog_item_id)
        .filter(ServiceCatalogItemModel.source == "viyar")
        .filter(ServiceCatalogItemModel.item_type == "service")
        .filter(ServiceCatalogItemModel.is_active.is_(True))
    )

    if not include_inactive:
        query = query.filter(ServiceDrillingRuleModel.is_active.is_(True))

    return query


def list_service_drilling_rules(
    include_inactive: bool = False,
    service_catalog_item_id: str | None = None,
) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        query = _build_rule_query(db, include_inactive=include_inactive)
        if service_catalog_item_id:
            query = query.filter(
                ServiceDrillingRuleModel.service_catalog_item_id == service_catalog_item_id,
            )

        rules = query.order_by(
            ServiceDrillingRuleModel.rule_name.asc(),
            ServiceDrillingRuleModel.id.asc(),
        ).all()
        return [_serialize_rule(rule) for rule in rules]
    finally:
        db.close()


def get_service_drilling_rule(rule_id: int) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        rule = (
            db.query(ServiceDrillingRuleModel)
            .join(ServiceCatalogItemModel, ServiceCatalogItemModel.id == ServiceDrillingRuleModel.service_catalog_item_id)
            .filter(ServiceDrillingRuleModel.id == rule_id)
            .one_or_none()
        )
        return _serialize_rule(rule) if rule else None
    finally:
        db.close()


def create_service_drilling_rule(payload: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        service_item = _resolve_service_item(db, payload["service_catalog_item_id"])
        if service_item is None:
            raise ValueError("Service catalog item does not exist or is not active")

        rule = ServiceDrillingRuleModel(
            service_catalog_item_id=service_item.id,
            rule_name=str(payload["rule_name"]).strip(),
            operation_type=str(payload["operation_type"]).strip(),
            hole_type=str(payload["hole_type"]).strip(),
            allowed_diameters=_coerce_number_list(payload.get("allowed_diameters")),
            allowed_depths=_coerce_number_list(payload.get("allowed_depths")),
            material_thickness_min=payload.get("material_thickness_min"),
            material_thickness_max=payload.get("material_thickness_max"),
            max_blind_depth_formula=(
                str(payload.get("max_blind_depth_formula")).strip() or None
                if payload.get("max_blind_depth_formula") is not None
                else None
            ),
            max_blind_depth_mm=payload.get("max_blind_depth_mm"),
            min_edge_offset_mm=payload.get("min_edge_offset_mm"),
            notes=(
                str(payload.get("notes")).strip() or None
                if payload.get("notes") is not None
                else None
            ),
            source=(
                str(payload.get("source")).strip() or None
                if payload.get("source") is not None
                else None
            ),
            is_active=bool(payload.get("is_active", True)),
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return _serialize_rule(rule)
    finally:
        db.close()


def update_service_drilling_rule(rule_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        rule = (
            db.query(ServiceDrillingRuleModel)
            .filter(ServiceDrillingRuleModel.id == rule_id)
            .one_or_none()
        )
        if rule is None:
            return None

        if "service_catalog_item_id" in payload:
            service_item = _resolve_service_item(db, payload["service_catalog_item_id"])
            if service_item is None:
                raise ValueError("Service catalog item does not exist or is not active")
            rule.service_catalog_item_id = service_item.id

        if "rule_name" in payload:
            rule_name = str(payload.get("rule_name") or "").strip()
            if not rule_name:
                raise ValueError("rule_name is required")
            rule.rule_name = rule_name

        if "operation_type" in payload:
            operation_type = str(payload.get("operation_type") or "").strip()
            if not operation_type:
                raise ValueError("operation_type is required")
            rule.operation_type = operation_type

        if "hole_type" in payload:
            hole_type = str(payload.get("hole_type") or "").strip()
            if not hole_type:
                raise ValueError("hole_type is required")
            rule.hole_type = hole_type

        if "allowed_diameters" in payload:
            rule.allowed_diameters = _coerce_number_list(payload.get("allowed_diameters"))

        if "allowed_depths" in payload:
            rule.allowed_depths = _coerce_number_list(payload.get("allowed_depths"))

        for field in (
            "material_thickness_min",
            "material_thickness_max",
            "max_blind_depth_mm",
            "min_edge_offset_mm",
        ):
            if field in payload:
                value = payload.get(field)
                setattr(rule, field, None if value in (None, "") else float(value))

        if "max_blind_depth_formula" in payload:
            text = "" if payload.get("max_blind_depth_formula") is None else str(payload.get("max_blind_depth_formula")).strip()
            rule.max_blind_depth_formula = text or None

        if "notes" in payload:
            text = "" if payload.get("notes") is None else str(payload.get("notes")).strip()
            rule.notes = text or None

        if "source" in payload:
            text = "" if payload.get("source") is None else str(payload.get("source")).strip()
            rule.source = text or None

        if "is_active" in payload:
            rule.is_active = bool(payload.get("is_active"))

        db.commit()
        db.refresh(rule)
        return _serialize_rule(rule)
    finally:
        db.close()


def deactivate_service_drilling_rule(rule_id: int) -> dict[str, Any] | None:
    return update_service_drilling_rule(rule_id, {"is_active": False})


def list_available_viyar_drilling_services(
    category: str | None = "drilling",
    search: str | None = None,
) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        query = (
            db.query(ServiceCatalogItemModel)
            .filter(ServiceCatalogItemModel.source == "viyar")
            .filter(ServiceCatalogItemModel.item_type == "service")
            .filter(ServiceCatalogItemModel.is_active.is_(True))
        )

        items = query.order_by(
            ServiceCatalogItemModel.folder_path.asc(),
            ServiceCatalogItemModel.sort_order.asc(),
            ServiceCatalogItemModel.name.asc(),
        ).all()

        normalized_category = str(category or "").strip().lower()
        normalized_search = str(search or "").strip().lower()

        def matches_category(item) -> bool:
            if not normalized_category or normalized_category in {"all", "*"}:
                return True
            extracted = _extract_viyar_service_category(item.folder_path)
            if normalized_category in {"drilling", "свердління", "сverdlinnya"}:
                return extracted == "drilling"
            return extracted == normalized_category

        def matches_search(item) -> bool:
            if not normalized_search:
                return True
            haystack = " ".join(
                str(value)
                for value in (
                    item.name,
                    item.article,
                    item.folder_path,
                    item.external_code,
                    item.source_url,
                )
                if value
            ).lower()
            return normalized_search in haystack

        filtered = [
            item
            for item in items
            if matches_category(item) and matches_search(item)
        ]

        return [
            _serialize_service_catalog_item(item)
            for item in filtered
        ]
    finally:
        db.close()


__all__ = [
    "create_service_drilling_rule",
    "deactivate_service_drilling_rule",
    "get_service_drilling_rule",
    "list_available_viyar_drilling_services",
    "list_service_drilling_rules",
    "update_service_drilling_rule",
]
