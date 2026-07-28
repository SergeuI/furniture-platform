from __future__ import annotations

from copy import deepcopy
from typing import Any


def _read_value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


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


def _snapshot_source_data(source: Any) -> dict[str, Any]:
    if isinstance(source, dict):
        return deepcopy(source)

    if hasattr(source, "__dict__"):
        return {
            key: deepcopy(value)
            for key, value in vars(source).items()
            if not key.startswith("_")
        }

    return {"value": deepcopy(source)}


class ProjectProcessingOperationAdapter:
    def build_operations(
        self,
        project_id: str | int | None,
        part_identifier: str | None,
        part_detail: dict[str, Any] | Any,
    ) -> list[dict[str, Any]]:
        part = _read_value(part_detail, "part", {}) or {}

        operations: list[dict[str, Any]] = []
        source_groups = (
            ("holes", "project_part_hole", "hole"),
            ("grooves", "project_part_groove", "groove"),
            ("quarters", "project_part_quarter", "quarter"),
        )

        order_index = 0
        for group_name, source_type, operation_type in source_groups:
            group_items = _read_value(part_detail, group_name, []) or []

            for fallback_index, item in enumerate(group_items, start=1):
                order_index += 1
                source_index = _safe_int(_read_value(item, "number", fallback_index), fallback_index)
                source_type_value = _read_value(item, "type", None)
                source_data = _snapshot_source_data(item)

                placement = {
                    "x_mm": _read_value(item, "x", None),
                    "y_mm": _read_value(item, "y", None),
                    "z_mm": _read_value(item, "z", None),
                    "target_panel": None,
                    "target_surface": None,
                    "target_side": None,
                    "side": _read_value(item, "side", None),
                    "coordinate_system": None,
                    "mounting_variant_key": None,
                }

                geometry = {
                    "diameter_mm": None,
                    "depth_mm": None,
                    "is_through": None,
                    "operation": source_type_value,
                    "length_mm": None,
                    "width_mm": None,
                    "direction": None,
                    "end_radius_mm": None,
                    "edge": None,
                    "start_offset_mm": None,
                    "end_offset_mm": None,
                    "radius_mm": None,
                }

                if operation_type == "hole":
                    geometry["diameter_mm"] = _safe_float(_read_value(item, "diameter", None))
                    geometry["depth_mm"] = _safe_float(_read_value(item, "depth", None))
                elif operation_type == "groove":
                    geometry["depth_mm"] = _safe_float(_read_value(item, "depth", None))
                    geometry["width_mm"] = _safe_float(_read_value(item, "width", None))
                    geometry["length_mm"] = _safe_float(_read_value(item, "length", None))
                elif operation_type == "quarter":
                    geometry["depth_mm"] = _safe_float(_read_value(item, "depth", None))
                    geometry["width_mm"] = _safe_float(_read_value(item, "width", None))
                    geometry["length_mm"] = _safe_float(_read_value(item, "length", None))
                    geometry["radius_mm"] = _safe_float(_read_value(item, "radius", None))
                    geometry["edge"] = _read_value(item, "edge", None)

                operations.append(
                    {
                        "id": None,
                        "operation_type": operation_type,
                        "source_type": source_type,
                        "source_id": None,
                        "template_id": None,
                        "label": source_type_value,
                        "placement": placement,
                        "geometry": geometry,
                        "quantity": 1,
                        "mirrored": False,
                        "order_index": order_index,
                        "service_mapping": {
                            "service_drilling_rule_id": None,
                            "resolved_service_catalog_item_id": None,
                            "resolution_source": "none",
                            "found": False,
                        },
                        "production_effects": {
                            "affects_cutting": False,
                            "affects_finished_contour": False,
                            "affects_edge_banding": False,
                            "requires_cnc": False,
                            "include_in_estimate": False,
                        },
                        "metadata": {
                            "project_id": project_id,
                            "part_identifier": part_identifier,
                            "part_key": _read_value(part, "export_code", None),
                            "part_type": _read_value(part, "category", None),
                            "part_name": _read_value(part, "part_name", None),
                            "source_index": source_index,
                            "source_data": source_data,
                        },
                    }
                )

        return operations
