from __future__ import annotations

import math
from typing import Any, Mapping


ALLOWED_DISTRIBUTION_MODES = {"equal", "fixed_spacing", "centered"}


def _number(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    return float(value)


def _integer(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    return int(value)


def _invalid(reason: str) -> dict[str, Any]:
    return {
        "valid": False,
        "reason": reason,
        "group_count": 0,
        "positions": [],
        "actual_spacing_mm": None,
    }


def _rounded_positions(values: list[float]) -> list[float]:
    return [round(value, 2) for value in values]


def calculate_mounting_scheme_placement(
    joint_length_mm: float,
    rule: Mapping[str, Any],
) -> dict[str, Any]:
    """Calculate mounting-group positions along one joint axis.

    The function is pure: it reads no database state and performs no writes.
    Positions are measured from the start of the joint in millimetres.
    """

    joint_length = float(joint_length_mm)
    if joint_length <= 0:
        return _invalid("joint_length_mm must be greater than 0")

    mode = str(rule.get("distribution_mode") or "").strip()
    if mode not in ALLOWED_DISTRIBUTION_MODES:
        return _invalid("unsupported distribution_mode")

    start_offset = _number(rule.get("start_offset_mm"), 0.0) or 0.0
    end_offset = _number(rule.get("end_offset_mm"), 0.0) or 0.0

    if start_offset < 0 or end_offset < 0:
        return _invalid("offsets cannot be negative")

    start = start_offset
    end = joint_length - end_offset
    usable_length = end - start

    if usable_length < 0:
        return _invalid("offsets exceed joint length")

    min_count = _integer(rule.get("min_group_count"), 1) or 1
    max_count = _integer(rule.get("max_group_count"))
    fixed_count = _integer(rule.get("fixed_group_count"))
    max_spacing = _number(rule.get("max_spacing_mm"))
    fixed_spacing = _number(rule.get("fixed_spacing_mm"))

    if min_count <= 0:
        return _invalid("min_group_count must be greater than 0")
    if max_count is not None and max_count < min_count:
        return _invalid("max_group_count cannot be less than min_group_count")
    if fixed_count is not None and fixed_count <= 0:
        return _invalid("fixed_group_count must be greater than 0")
    if max_spacing is not None and max_spacing <= 0:
        return _invalid("max_spacing_mm must be greater than 0")
    if fixed_spacing is not None and fixed_spacing <= 0:
        return _invalid("fixed_spacing_mm must be greater than 0")

    if fixed_count is not None:
        if fixed_count < min_count:
            return _invalid("fixed_group_count cannot be less than min_group_count")
        if max_count is not None and fixed_count > max_count:
            return _invalid("fixed_group_count exceeds max_group_count")

    if mode == "equal":
        count = fixed_count or min_count

        if count == 1 and max_spacing is not None and usable_length > max_spacing:
            count = 2

        if max_spacing is not None and usable_length > 0:
            required_count = max(1, math.ceil(usable_length / max_spacing) + 1)
            if fixed_count is not None and required_count > fixed_count:
                return _invalid("fixed_group_count violates max_spacing_mm")
            count = max(count, required_count)

        if max_count is not None and count > max_count:
            return _invalid("required group count exceeds max_group_count")

        if count == 1:
            positions = [start + usable_length / 2.0]
            actual_spacing = None
        else:
            actual_spacing = usable_length / (count - 1)
            positions = [start + actual_spacing * index for index in range(count)]

    elif mode == "fixed_spacing":
        if fixed_spacing is None:
            return _invalid("fixed_spacing mode requires fixed_spacing_mm")

        if fixed_count is not None:
            count = fixed_count
        else:
            count = math.floor(usable_length / fixed_spacing) + 1
            count = max(count, min_count)
            if max_count is not None:
                count = min(count, max_count)

        positions = [start + fixed_spacing * index for index in range(count)]
        if positions and positions[-1] > end + 1e-9:
            return _invalid("fixed spacing does not fit inside end offset")

        actual_spacing = fixed_spacing if count > 1 else None

    else:
        count = fixed_count or min_count
        if max_count is not None and count > max_count:
            return _invalid("group count exceeds max_group_count")

        center = start + usable_length / 2.0

        if count == 1:
            positions = [center]
            actual_spacing = None
        else:
            spacing = fixed_spacing
            if spacing is None:
                spacing = max_spacing
            if spacing is None:
                spacing = usable_length / (count - 1)

            total_span = spacing * (count - 1)
            first = center - total_span / 2.0
            last = center + total_span / 2.0

            if first < start - 1e-9 or last > end + 1e-9:
                return _invalid("centered group does not fit inside offsets")

            positions = [first + spacing * index for index in range(count)]
            actual_spacing = spacing

    rounded_positions = _rounded_positions(positions)

    return {
        "valid": True,
        "reason": None,
        "distribution_mode": mode,
        "joint_length_mm": round(joint_length, 2),
        "start_offset_mm": round(start_offset, 2),
        "end_offset_mm": round(end_offset, 2),
        "usable_length_mm": round(usable_length, 2),
        "group_count": len(rounded_positions),
        "positions": rounded_positions,
        "actual_spacing_mm": (
            None if actual_spacing is None else round(actual_spacing, 2)
        ),
    }


__all__ = ["calculate_mounting_scheme_placement"]
