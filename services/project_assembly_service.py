def _normalize_project_type(project_type: str | None) -> str:

    normalized = str(project_type or "").strip().lower()

    if not normalized:

        return "dresser"

    if (
        "wardrobe" in normalized
        or "closet" in normalized
        or "шаф" in normalized
    ):

        return "wardrobe"

    if (
        "kitchen" in normalized
        or "кух" in normalized
    ):

        return "kitchen"

    if (
        "cabinet" in normalized
        or "pedestal" in normalized
        or "nightstand" in normalized
        or "тумб" in normalized
        or "пенал" in normalized
    ):

        return "cabinet"

    if (
        "dresser" in normalized
        or "комод" in normalized
    ):

        return "dresser"

    return "dresser"


def _safe_positive_int(value, fallback: int) -> int:

    try:

        numeric = int(value)

    except (
        TypeError,
        ValueError
    ):

        return fallback

    return (
        numeric
        if numeric > 0
        else fallback
    )


def _count_drawer_units(drawers) -> int:

    if not isinstance(drawers, list):

        return 0

    total = 0

    for item in drawers:

        try:

            value = int(item)

        except (
            TypeError,
            ValueError
        ):

            continue

        if value > 0:

            total += value

    return total


def _build_grid_slots(
    columns: int,
    rows: int,
    fill_direction: str = "top-down"
) -> list[dict]:

    safe_columns = max(columns, 1)
    safe_rows = max(rows, 1)
    slots = []

    for row in range(safe_rows):

        for column in range(safe_columns):

            visual_row = (
                safe_rows - 1 - row
                if fill_direction == "bottom-up"
                else row
            )

            slots.append({
                "column": column,
                "row": visual_row,
                "x_ratio": (column + 0.5) / safe_columns,
                "y_ratio": (visual_row + 0.5) / safe_rows
            })

    return slots


def _build_linear_slots(count: int, inset_ratio: float = 0.06) -> list[dict]:

    safe_count = max(count, 1)
    usable = max(1.0 - inset_ratio * 2, 0.42)

    return [
        {
            "index": index,
            "x_ratio": inset_ratio + usable * ((index + 1) / (safe_count + 1))
        }
        for index in range(safe_count)
    ]


def _build_vertical_slots(
    count: int,
    top_inset: float,
    bottom_inset: float
) -> list[dict]:

    safe_count = max(count, 1)
    usable = max(1.0 - top_inset - bottom_inset, 0.34)

    return [
        {
            "index": index,
            "y_ratio": top_inset + usable * ((index + 1) / (safe_count + 1))
        }
        for index in range(safe_count)
    ]


def _normalize_drawer_columns(
    drawers,
    columns: int
) -> list[int]:

    normalized = []

    if isinstance(drawers, list):

        for value in drawers[:columns]:

            try:

                numeric = int(value)

            except (
                TypeError,
                ValueError
            ):

                numeric = 0

            normalized.append(
                max(
                    numeric,
                    0
                )
            )

    while len(normalized) < columns:

        normalized.append(0)

    return normalized


def _build_column_drawer_slots(
    drawer_columns: list[int],
    top_inset: float,
    bottom_inset: float
) -> list[dict]:

    total_columns = max(
        len(drawer_columns),
        1
    )
    column_width_ratio = 1 / total_columns
    usable_height_ratio = max(
        1.0 - top_inset - bottom_inset,
        0.34
    )
    slots = []

    for column_index, drawer_count in enumerate(drawer_columns):

        if drawer_count <= 0:

            continue

        drawer_height_ratio = usable_height_ratio / drawer_count

        for row_index in range(drawer_count):

            slots.append({
                "column": column_index,
                "height_ratio": drawer_height_ratio,
                "row": row_index,
                "width_ratio": column_width_ratio,
                "x_ratio": column_width_ratio * (column_index + 0.5),
                "y_ratio": top_inset + drawer_height_ratio * (row_index + 0.5)
            })

    return slots


def _classify_cutting_instance(
    export_code: str | None,
    part_name: str | None,
    copy_index: int
) -> str:

    normalized_code = str(export_code or "").strip().upper()
    normalized_name = str(part_name or "").strip().lower()

    if normalized_code == "CAB-SIDE":

        return (
            "side-left"
            if copy_index % 2 == 0
            else "side-right"
        )

    if normalized_code == "CAB-TOP-BOTTOM":

        return (
            "top"
            if copy_index % 2 == 0
            else "bottom"
        )

    if normalized_code == "CAB-DIVIDER":

        return "divider-vertical"

    if normalized_code == "CAB-BACK":

        return "back"

    if normalized_code == "DRW-FRONT":

        return "facade"

    if normalized_code == "DRW-SIDE":

        return (
            "drawer-side-left"
            if copy_index % 2 == 0
            else "drawer-side-right"
        )

    if normalized_code == "DRW-FRONT-BACK":

        return (
            "drawer-front-rail"
            if copy_index % 2 == 0
            else "drawer-back-rail"
        )

    if normalized_code == "DRW-BOTTOM":

        return "drawer-bottom"

    if "facade" in normalized_name or "front" in normalized_name:

        return "facade"

    if "drawer" in normalized_name and "side" in normalized_name:

        return (
            "drawer-side-left"
            if copy_index % 2 == 0
            else "drawer-side-right"
        )

    if "drawer" in normalized_name and "bottom" in normalized_name:

        return "drawer-bottom"

    if "drawer" in normalized_name:

        return "drawer"

    if "back" in normalized_name:

        return "back"

    if "divider" in normalized_name or "partition" in normalized_name:

        return "divider-vertical"

    if "shelf" in normalized_name:

        return "shelf"

    if "rail" in normalized_name or "stretcher" in normalized_name:

        return "support-rail"

    if "top" in normalized_name or "upper" in normalized_name or "roof" in normalized_name:

        return "top"

    if "bottom" in normalized_name or "base" in normalized_name or "lower" in normalized_name:

        return "bottom"

    return "other"


def build_project_assembly_mapping(
    project,
    cutting_items: list[dict],
    assembly_layout: dict | None = None
) -> dict:

    layout = (
        assembly_layout
        if isinstance(assembly_layout, dict) and assembly_layout
        else build_project_assembly_layout(project)
    )

    placements = []
    facade_slot_count = max(
        len(layout.get("facade_slots") or []),
        1
    )
    drawer_slot_count = max(
        len(layout.get("drawer_slots") or []),
        1
    )
    divider_slot_count = max(
        len(layout.get("divider_slots") or []),
        1
    )
    shelf_slot_count = max(
        len(layout.get("shelf_slots") or []),
        1
    )
    support_rail_slot_count = max(
        len(layout.get("support_rail_slots") or []),
        1
    )

    facade_index = 0
    drawer_index = 0
    divider_index = 0
    shelf_index = 0
    support_rail_index = 0
    other_index = 0

    for item in cutting_items:

        quantity = max(
            int(item.get("quantity") or 0),
            0
        )

        for copy_index in range(quantity):

            kind = _classify_cutting_instance(
                item.get("export_code"),
                item.get("part_name"),
                copy_index
            )
            slot_type = None
            slot_index = None
            drawer_unit_index = None

            if kind == "facade":

                slot_type = "facade"
                slot_index = facade_index % facade_slot_count
                facade_index += 1

            elif kind in (
                "drawer",
                "drawer-bottom"
            ):

                slot_type = "drawer"
                slot_index = drawer_index % drawer_slot_count
                drawer_unit_index = slot_index
                drawer_index += 1

            elif kind in (
                "drawer-side-left",
                "drawer-side-right",
                "drawer-front-rail",
                "drawer-back-rail"
            ):

                slot_type = "drawer"
                slot_index = (copy_index // 2) % drawer_slot_count
                drawer_unit_index = slot_index

            elif kind == "divider-vertical":

                slot_type = "divider"
                slot_index = divider_index % divider_slot_count
                divider_index += 1

            elif kind == "shelf":

                slot_type = "shelf"
                slot_index = shelf_index % shelf_slot_count
                shelf_index += 1

            elif kind == "support-rail":

                slot_type = "support-rail"
                slot_index = support_rail_index % support_rail_slot_count
                support_rail_index += 1

            else:

                slot_type = "other"
                slot_index = other_index
                other_index += 1

            placements.append({
                "copy_index": copy_index,
                "drawer_unit_index": drawer_unit_index,
                "export_code": item.get("export_code"),
                "kind": kind,
                "slot_index": slot_index,
                "slot_type": slot_type
            })

    return {
        "layout_project_type": layout.get(
            "project_type"
        ),
        "placements": placements
    }


def build_project_assembly_layout(project) -> dict:

    project_type = _normalize_project_type(
        getattr(
            project,
            "project_type",
            None
        )
    )

    sections = _safe_positive_int(
        getattr(
            project,
            "sections",
            1
        ),
        1
    )

    drawer_units = _count_drawer_units(
        getattr(
            project,
            "drawers",
            []
        )
    )
    drawer_columns_config = _normalize_drawer_columns(
        getattr(
            project,
            "drawers",
            []
        ),
        sections
    )

    if project_type == "wardrobe":

        columns = max(
            2,
            min(
                4,
                sections
            )
        )

        facade_rows = 2 if drawer_units else 1
        drawer_rows = max(1, min(drawer_units or 1, 2))

        return {

            "project_type": project_type,

            "columns": columns,

            "facade_columns": min(
                max(
                    2,
                    sections
                ),
                columns
            ),

            "facade_rows": facade_rows,

            "facade_slots": _build_grid_slots(
                min(
                    max(
                        2,
                        sections
                    ),
                    columns
                ),
                facade_rows,
                "top-down"
            ),

            "drawer_columns": min(
                max(
                    1,
                    2 if drawer_units else 1
                ),
                columns
            ),

            "drawer_rows": drawer_rows,

            "drawer_slots": _build_grid_slots(
                min(
                    max(
                        1,
                        2 if drawer_units else 1
                    ),
                    columns
                ),
                drawer_rows,
                "bottom-up"
            ),

            "drawer_fill_direction": "bottom-up",

            "drawer_depth_ratio": 0.68,

            "drawer_gap": 0.11,

            "drawer_setback": 0.10,

            "drawer_top_inset": 0.56,

            "drawer_bottom_inset": 0.08,

            "facade_fill_direction": "top-down",

            "facade_front_offset": 0.01,

            "facade_gap": 0.08,

            "facade_top_inset": 0.05,

            "facade_bottom_inset": 0.06,

            "shelf_top_inset": 0.16,

            "shelf_bottom_inset": 0.18,

            "support_rail_front_inset": 0.05,

            "support_rail_top_inset": 0.12,

            "vertical_inset_ratio": 0.05,

            "divider_slots": _build_linear_slots(
                max(columns - 1, 0),
                0.05
            ),

            "shelf_slots": _build_vertical_slots(
                max(sections - 1, 1),
                0.16,
                0.18
            ),

            "support_rail_slots": _build_vertical_slots(
                max(1, min(columns, 2)),
                0.12,
                0.72
            )
        }

    if project_type == "kitchen":

        columns = max(
            2,
            min(
                5,
                sections
            )
        )

        facade_rows = max(1, 2 if drawer_units else 1)
        drawer_rows = max(1, min(drawer_units or 1, 2))

        return {

            "project_type": project_type,

            "columns": columns,

            "facade_columns": min(
                max(
                    2,
                    sections
                ),
                columns
            ),

            "facade_rows": facade_rows,

            "facade_slots": _build_grid_slots(
                min(
                    max(
                        2,
                        sections
                    ),
                    columns
                ),
                facade_rows,
                "top-down"
            ),

            "drawer_columns": min(
                max(
                    2,
                    sections
                ),
                columns
            ),

            "drawer_rows": drawer_rows,

            "drawer_slots": _build_grid_slots(
                min(
                    max(
                        2,
                        sections
                    ),
                    columns
                ),
                drawer_rows,
                "top-down"
            ),

            "drawer_fill_direction": "top-down",

            "drawer_depth_ratio": 0.62,

            "drawer_gap": 0.09,

            "drawer_setback": 0.08,

            "drawer_top_inset": 0.46,

            "drawer_bottom_inset": 0.10,

            "facade_fill_direction": "top-down",

            "facade_front_offset": 0.03,

            "facade_gap": 0.07,

            "facade_top_inset": 0.08,

            "facade_bottom_inset": 0.08,

            "shelf_top_inset": 0.22,

            "shelf_bottom_inset": 0.22,

            "support_rail_front_inset": 0.04,

            "support_rail_top_inset": 0.14,

            "vertical_inset_ratio": 0.05,

            "divider_slots": _build_linear_slots(
                max(columns - 1, 0),
                0.05
            ),

            "shelf_slots": _build_vertical_slots(
                max(sections - 1, 1),
                0.22,
                0.22
            ),

            "support_rail_slots": _build_vertical_slots(
                max(1, min(columns, 2)),
                0.14,
                0.72
            )
        }

    if project_type == "cabinet":

        columns = max(
            1,
            min(
                2,
                sections
            )
        )

        facade_rows = max(1, 2 if drawer_units else 1)
        drawer_rows = max(1, drawer_units or 1)

        return {

            "project_type": project_type,

            "columns": columns,

            "facade_columns": min(
                max(
                    1,
                    sections
                ),
                columns
            ),

            "facade_rows": facade_rows,

            "facade_slots": _build_grid_slots(
                min(
                    max(
                        1,
                        sections
                    ),
                    columns
                ),
                facade_rows,
                "top-down"
            ),

            "drawer_columns": min(
                max(
                    1,
                    drawer_units or 1
                ),
                columns
            ),

            "drawer_rows": drawer_rows,

            "drawer_slots": _build_grid_slots(
                min(
                    max(
                        1,
                        drawer_units or 1
                    ),
                    columns
                ),
                drawer_rows,
                "bottom-up"
            ),

            "drawer_fill_direction": "bottom-up",

            "drawer_depth_ratio": 0.74,

            "drawer_gap": 0.10,

            "drawer_setback": 0.09,

            "drawer_top_inset": 0.48,

            "drawer_bottom_inset": 0.10,

            "facade_fill_direction": "top-down",

            "facade_front_offset": 0.015,

            "facade_gap": 0.08,

            "facade_top_inset": 0.08,

            "facade_bottom_inset": 0.08,

            "shelf_top_inset": 0.20,

            "shelf_bottom_inset": 0.24,

            "support_rail_front_inset": 0.05,

            "support_rail_top_inset": 0.14,

            "vertical_inset_ratio": 0.06,

            "divider_slots": _build_linear_slots(
                max(columns - 1, 0),
                0.06
            ),

            "shelf_slots": _build_vertical_slots(
                max(sections - 1, 1),
                0.20,
                0.24
            ),

            "support_rail_slots": _build_vertical_slots(
                max(1, min(columns, 2)),
                0.14,
                0.72
            )
        }

    columns = max(
        1,
        min(
            3,
            sections
        )
    )

    dresser_drawer_columns = drawer_columns_config[:columns]
    facade_slots = _build_column_drawer_slots(
        dresser_drawer_columns,
        0.06,
        0.06
    )
    drawer_slots = _build_column_drawer_slots(
        dresser_drawer_columns,
        0.38,
        0.08
    )
    facade_rows = max(
        (
            max(dresser_drawer_columns)
            if any(dresser_drawer_columns)
            else 1
        ),
        1
    )

    drawer_rows = max(
        (
            max(dresser_drawer_columns)
            if any(dresser_drawer_columns)
            else 1
        ),
        1
    )

    return {

        "project_type": "dresser",

        "columns": columns,

        "facade_columns": min(
            max(
                1,
                sections
            ),
            columns
        ),

        "facade_rows": facade_rows,

        "facade_slots": (
            facade_slots
            if facade_slots
            else _build_grid_slots(
                min(
                    max(
                        1,
                        sections
                    ),
                    columns
                ),
                facade_rows,
                "top-down"
            )
        ),

        "drawer_columns": min(
            max(
                1,
                sections
            ),
            columns
        ),

        "drawer_rows": drawer_rows,

        "drawer_slots": (
            drawer_slots
            if drawer_slots
            else _build_grid_slots(
                min(
                    max(
                        1,
                        sections
                    ),
                    columns
                ),
                drawer_rows,
                "top-down"
            )
        ),

        "drawer_fill_direction": "top-down",

        "drawer_depth_ratio": 0.88,

        "drawer_gap": 0.04,

        "drawer_setback": 0.03,

        "drawer_top_inset": 0.10,

        "drawer_bottom_inset": 0.10,

        "facade_fill_direction": "top-down",

        "facade_front_offset": 0.012,

        "facade_gap": 0.03,

        "facade_top_inset": 0.06,

        "facade_bottom_inset": 0.06,

        "shelf_top_inset": 0.18,

        "shelf_bottom_inset": 0.24,

        "support_rail_front_inset": 0.04,

        "support_rail_top_inset": 0.13,

        "vertical_inset_ratio": 0.05,

        "back_panel_inset": 0.0,

        "back_panel_thickness_ratio": 1.0,

        "drawer_front_clearance": 0.045,

        "drawer_visual_mode": "box",

        "divider_slots": _build_linear_slots(
            max(columns - 1, 0),
            0.05
        ),

        "shelf_slots": [],

        "support_rail_slots": []
    }
