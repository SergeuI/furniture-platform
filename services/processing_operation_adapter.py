from __future__ import annotations

from collections import OrderedDict
from typing import Any

from services.fitting_hole_service_preview import build_fitting_hole_service_preview


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _group_key(operation: str, diameter_mm: float | None, depth_mm: float | None) -> str:
    diameter_part = "" if diameter_mm is None else f"{diameter_mm:.3f}"
    depth_part = "" if depth_mm is None else f"{depth_mm:.3f}"
    return f"{operation}|{diameter_part}|{depth_part}"


class ProcessingOperationAdapter:
    def build_operations(
        self,
        template,
        points: list[Any] | None,
        current_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        preview = build_fitting_hole_service_preview(
            template,
            points,
            current_user_id=current_user_id,
        )

        service_mapping_by_group: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for group in preview.get("groups", []):
            group_key = _group_key(
                str(group.get("operation") or "drill").strip() or "drill",
                _safe_float(group.get("diameter_mm")),
                _safe_float(group.get("depth_mm")),
            )
            service_mapping_by_group[group_key] = {
                "service_drilling_rule_id": None,
                "resolved_service_catalog_item_id": group.get("matched_service_id"),
                "resolution_source": group.get("match_source"),
                "found": bool(group.get("matched_service_id")),
            }

        operations: list[dict[str, Any]] = []
        for point in sorted(
            points or [],
            key=lambda item: (
                _safe_int(getattr(item, "order_index", 0), 0),
                _safe_int(getattr(item, "id", 0), 0),
            ),
        ):
            operation = str(getattr(point, "operation", None) or "drill").strip() or "drill"
            diameter_mm = _safe_float(getattr(point, "diameter_mm", None))
            depth_mm = _safe_float(getattr(point, "depth_mm", None))
            point_group_key = _group_key(operation, diameter_mm, depth_mm)
            service_mapping = service_mapping_by_group.get(
                point_group_key,
                {
                    "service_drilling_rule_id": None,
                    "resolved_service_catalog_item_id": None,
                    "resolution_source": "none",
                    "found": False,
                },
            )

            resolved_service_catalog_item_id = service_mapping.get("resolved_service_catalog_item_id")
            resolution_source = service_mapping.get("resolution_source") or "none"

            placement = {
                "x_mm": getattr(point, "x_mm", None),
                "y_mm": getattr(point, "y_mm", None),
                "z_mm": getattr(point, "z_mm", None),
                "target_panel": getattr(point, "target_panel", None),
                "target_surface": getattr(point, "target_surface", None),
                "target_side": getattr(point, "target_side", None),
                "side": getattr(point, "side", None),
                "coordinate_system": getattr(template, "coordinate_system", None),
                "mounting_variant_key": getattr(template, "mounting_variant_key", None),
            }

            geometry = {
                "diameter_mm": diameter_mm,
                "depth_mm": depth_mm,
                "is_through": bool(operation == "through_drill" or depth_mm is None),
                "operation": operation,
            }

            metadata = {
                "source_label": getattr(point, "label", None),
                "template_notes": getattr(template, "notes", None),
                "point_notes": getattr(point, "notes", None),
                "fitting_code": getattr(getattr(template, "fitting", None), "code", None),
                "fitting_article": getattr(getattr(template, "fitting", None), "article", None),
                "fitting_category_code": getattr(getattr(template, "fitting", None), "fitting_type", None)
                or getattr(getattr(template, "fitting", None), "fitting_group", None),
                "bundle_key": getattr(template, "bundle_key", None),
                "bundle_name": getattr(template, "bundle_name", None),
                "target_panel": getattr(point, "target_panel", None),
                "target_surface": getattr(point, "target_surface", None),
                "target_side": getattr(point, "target_side", None),
                "source_data": {
                    "point_operation": getattr(point, "operation", None),
                    "point_side": getattr(point, "side", None),
                    "point_service_drilling_rule_id": getattr(point, "service_drilling_rule_id", None),
                },
            }

            operations.append(
                {
                    "id": getattr(point, "id", None),
                    "operation_type": "hole",
                    "source_type": "fitting_hole_point",
                    "source_id": getattr(point, "id", None),
                    "template_id": getattr(point, "template_id", None),
                    "label": getattr(point, "label", None),
                    "placement": placement,
                    "geometry": geometry,
                    "quantity": max(_safe_int(getattr(point, "quantity", 1), 1), 1),
                    "mirrored": bool(getattr(point, "mirrored", False)),
                    "order_index": _safe_int(getattr(point, "order_index", 0), 0),
                    "service_mapping": {
                        "service_drilling_rule_id": getattr(point, "service_drilling_rule_id", None),
                        "resolved_service_catalog_item_id": resolved_service_catalog_item_id,
                        "resolution_source": resolution_source,
                        "found": bool(service_mapping.get("found")),
                    },
                    "production_effects": {
                        "affects_cutting": False,
                        "affects_finished_contour": False,
                        "affects_edge_banding": False,
                        "requires_cnc": False,
                        "include_in_estimate": True,
                    },
                    "metadata": metadata,
                }
            )

        operations.sort(
            key=lambda item: (
                _safe_int(item.get("order_index"), 0),
                _safe_int(item.get("id"), 0),
            )
        )
        return operations
