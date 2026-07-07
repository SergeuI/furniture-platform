from __future__ import annotations

from collections import OrderedDict
from typing import Any

from database.repositories.fitting_hole_service_rule_repository import (
    resolve_fitting_hole_service_rule,
)
from database.repositories.service_catalog_repository import (
    list_calculable_service_catalog_items,
)


_OPERATION_PRESETS = {
    "blind_drill": {
        "label": "Свердління глухого отвору",
        "is_calculable": True,
    },
    "drill": {
        "label": "Свердління",
        "is_calculable": True,
    },
    "mark": {
        "label": "Мітка",
        "is_calculable": False,
        "note": "Не додається до кошторису",
    },
    "milling": {
        "label": "Фрезерування",
        "is_calculable": True,
    },
    "slot": {
        "label": "Паз / фрезерування паза",
        "is_calculable": True,
    },
    "through_drill": {
        "label": "Свердління наскрізного отвору",
        "is_calculable": True,
    },
}

_SERVICE_MATCH_TERMS = {
    "blind_drill": ["свердління", "присадка", "drilling", "prisadka", "drill"],
    "through_drill": ["свердління", "присадка", "drilling", "prisadka", "drill"],
    "drill": ["свердління", "присадка", "drilling", "prisadka", "drill"],
    "milling": ["фрезерування", "milling"],
    "slot": ["паз", "фрезерування", "milling", "groove", "slot"],
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _group_key(operation: str, diameter_mm: float | None, depth_mm: float | None) -> str:
    diameter_part = "" if diameter_mm is None else f"{diameter_mm:.3f}"
    depth_part = "" if depth_mm is None else f"{depth_mm:.3f}"
    return f"{operation}|{diameter_part}|{depth_part}"


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _build_service_haystack(service_item: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in (
            service_item.get("name"),
            service_item.get("slug"),
            service_item.get("folder_path"),
            service_item.get("source"),
            service_item.get("article"),
        )
        if part
    ).lower()


def _score_service_candidate(service_item: dict[str, Any], terms: list[str]) -> int:
    haystack = _build_service_haystack(service_item)
    if not haystack:
        return 0

    score = 0
    slug = _normalize_text(service_item.get("slug"))
    folder_path = _normalize_text(service_item.get("folder_path"))
    name = _normalize_text(service_item.get("name"))
    source = _normalize_text(service_item.get("source"))

    for term in terms:
        normalized_term = _normalize_text(term)
        if not normalized_term:
            continue

        if normalized_term == slug or normalized_term == folder_path:
            score += 100
        elif normalized_term in slug or normalized_term in folder_path:
            score += 60
        elif normalized_term in name:
            score += 40
        elif normalized_term in source:
            score += 20
        elif normalized_term in haystack:
            score += 10

    return score


def _find_auto_service(operation: str, services: list[dict[str, Any]]) -> dict[str, Any] | None:
    if operation == "mark":
        return None

    terms = _SERVICE_MATCH_TERMS.get(operation, _SERVICE_MATCH_TERMS["drill"])
    best_service: dict[str, Any] | None = None
    best_score = 0

    for service_item in services:
        if service_item.get("item_type") != "service":
            continue
        if not service_item.get("is_active"):
            continue
        if not service_item.get("is_calculable"):
            continue

        score = _score_service_candidate(service_item, terms)
        if score > best_score:
            best_service = service_item
            best_score = score

    if best_service is None or best_score <= 0:
        return None

    return best_service


def _select_service_match(
    operation: str,
    diameter_mm: float | None,
    depth_mm: float | None,
    services: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    if operation == "mark":
        return None, "none"

    rule = resolve_fitting_hole_service_rule(
        operation=operation,
        diameter_mm=diameter_mm,
        depth_mm=depth_mm,
    )
    if rule:
        service_item = rule.get("service_catalog_item")
        if service_item and service_item.get("is_active") and service_item.get("is_calculable"):
            return service_item, "rule"

    auto_service = _find_auto_service(operation, services)
    if auto_service:
        return auto_service, "auto"

    return None, "none"


def build_fitting_hole_service_preview(
    template,
    points: list[Any] | None,
    current_user_id: str | None = None,
) -> dict[str, Any]:
    calculable_services = [
        *list_calculable_service_catalog_items(
            source="viyar",
            user_id=current_user_id,
        ),
        *list_calculable_service_catalog_items(
            source="manual",
            user_id=current_user_id,
            owner_user_id=current_user_id,
        ),
    ]

    grouped_points: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for point in points or []:
        operation = str(getattr(point, "operation", None) or "drill").strip() or "drill"
        preset = _OPERATION_PRESETS.get(
            operation,
            {
                "label": "Операція",
                "is_calculable": True,
            },
        )

        diameter_mm = _safe_float(getattr(point, "diameter_mm", None))
        depth_mm = _safe_float(getattr(point, "depth_mm", None))
        if operation == "mark":
            diameter_mm = None
            depth_mm = None

        group_key = _group_key(operation, diameter_mm, depth_mm)
        group = grouped_points.get(group_key)
        if group is None:
            matched_service, match_source = _select_service_match(
                operation,
                diameter_mm,
                depth_mm,
                calculable_services,
            )
            match_status = "not_calculable" if operation == "mark" else ("matched" if matched_service else "not_found")
            group = {
                "operation": operation,
                "label": preset.get("label") or "Операція",
                "diameter_mm": diameter_mm,
                "depth_mm": depth_mm,
                "quantity": 0,
                "unit": "шт.",
                "point_count": 0,
                "is_calculable": bool(preset.get("is_calculable", True)),
                "note": preset.get("note"),
                "matched_service_id": None,
                "matched_service_name": None,
                "matched_service_unit": None,
                "matched_service_price": None,
                "matched_service_currency": None,
                "matched_service_source": None,
                "match_status": match_status,
                "match_source": match_source,
            }
            if matched_service:
                group["matched_service_id"] = matched_service.get("id")
                group["matched_service_name"] = matched_service.get("name")
                group["matched_service_unit"] = matched_service.get("unit")
                group["matched_service_price"] = matched_service.get("effective_price")
                group["matched_service_currency"] = matched_service.get("effective_currency")
                group["matched_service_source"] = matched_service.get("source")
            grouped_points[group_key] = group

        group["quantity"] += max(_safe_int(getattr(point, "quantity", 1), 1), 1)
        group["point_count"] += 1

    groups = list(grouped_points.values())
    groups.sort(
        key=lambda item: (
            0 if item.get("is_calculable") else 1,
            item.get("operation") or "",
            item.get("diameter_mm") is None,
            float(item.get("diameter_mm") or 0),
            item.get("depth_mm") is None,
            float(item.get("depth_mm") or 0),
        )
    )

    summary = {
        "groups_count": len(groups),
        "calculable_groups_count": sum(1 for item in groups if item.get("is_calculable")),
        "point_count": sum(int(item.get("point_count") or 0) for item in groups),
        "calculable_point_count": sum(
            int(item.get("point_count") or 0)
            for item in groups
            if item.get("is_calculable")
        ),
    }

    fitting = getattr(template, "fitting", None)
    category_code = getattr(fitting, "fitting_type", None) or getattr(fitting, "fitting_group", None)

    return {
        "template_id": getattr(template, "id", None),
        "bundle_key": getattr(template, "bundle_key", None),
        "bundle_name": getattr(template, "bundle_name", None),
        "mounting_variant_key": getattr(template, "mounting_variant_key", None),
        "category_code": category_code,
        "groups": groups,
        "summary": summary,
    }
