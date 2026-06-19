from services.project_assembly_service import (
    build_project_assembly_layout,
    build_project_assembly_mapping
)


def _safe_text(value, fallback="not_set"):

    if value is None:

        return fallback

    if isinstance(value, str) and not value.strip():

        return fallback

    return value


def _drawer_count(project):

    drawers = project.drawers or []

    return sum(
        int(value)
        for value in drawers
        if isinstance(value, int)
    )


def _edge_map(edge_banding, top=False, bottom=False, left=False, right=False):

    edge = _safe_text(
        edge_banding
    )

    return {
        "top": edge if top else None,
        "bottom": edge if bottom else None,
        "left": edge if left else None,
        "right": edge if right else None
    }


def _cutting_item(
    export_code,
    part_name,
    category,
    width,
    height,
    quantity,
    material,
    thickness,
    edges,
    grain_direction="none",
    notes=None
):

    return {
        "export_code": export_code,
        "part_name": part_name,
        "category": category,
        "width": max(
            int(width),
            0
        ),
        "height": max(
            int(height),
            0
        ),
        "quantity": max(
            int(quantity),
            0
        ),
        "material": _safe_text(
            material
        ),
        "thickness": thickness,
        "edge_top": edges.get(
            "top"
        ),
        "edge_bottom": edges.get(
            "bottom"
        ),
        "edge_left": edges.get(
            "left"
        ),
        "edge_right": edges.get(
            "right"
        ),
        "grain_direction": grain_direction,
        "notes": notes
    }


def _area_m2(item):

    return (
        item["width"]
        * item["height"]
        * item["quantity"]
    ) / 1000000


def _cut_length_m(item):

    return (
        (
            item["width"]
            + item["height"]
        )
        * 2
        * item["quantity"]
    ) / 1000


def _edge_length_m(item):

    total = 0

    if item["edge_top"]:

        total += item["width"]

    if item["edge_bottom"]:

        total += item["width"]

    if item["edge_left"]:

        total += item["height"]

    if item["edge_right"]:

        total += item["height"]

    return (
        total
        * item["quantity"]
    ) / 1000


def _normalize_edge_override(value):

    if value in (
        None,
        "",
        "not_set"
    ):

        return None

    return value


def _apply_edge_overrides(items, edge_overrides):

    if not isinstance(edge_overrides, dict):

        return items

    for item in items:

        override = edge_overrides.get(
            item["export_code"]
        )

        if not isinstance(override, dict):

            continue

        for side in (
            "top",
            "bottom",
            "left",
            "right"
        ):

            if side in override:

                item[f"edge_{side}"] = _normalize_edge_override(
                    override.get(
                        side
                    )
                )

    return items


def build_project_cutting(project):

    width = int(project.width or 0)
    height = int(project.height or 0)
    depth = int(project.depth or 0)
    sections = max(
        int(project.sections or 0),
        0
    )
    drawer_count = _drawer_count(
        project
    )

    inside_thickness = project.inside_thickness or project.material_thickness or 18
    facade_thickness = project.facade_thickness or inside_thickness
    inside_edge_banding = project.inside_edge_banding or project.edge_banding
    facade_edge_banding = project.facade_edge_banding or inside_edge_banding
    inside_material = _safe_text(
        project.inside_material
    )
    facade_material = _safe_text(
        project.facade_material,
        inside_material
    )
    bottom_material = _safe_text(
        project.bottom_type,
        "hdf"
    )

    divider_count = max(
        sections - 1,
        0
    )

    inner_width = max(
        width - (inside_thickness * 2),
        0
    )
    inner_height = max(
        height - (inside_thickness * 2),
        0
    )
    drawer_front_width = (
        max(
            inner_width // sections,
            0
        )
        if sections
        else inner_width
    )
    drawer_front_height = (
        max(
            inner_height // max(drawer_count, 1),
            0
        )
        if drawer_count
        else 0
    )

    items = [
        _cutting_item(
            "CAB-SIDE",
            "Side panel",
            "cabinet",
            depth,
            height,
            2,
            inside_material,
            inside_thickness,
            _edge_map(
                inside_edge_banding,
                top=True,
                bottom=True,
                left=True
            ),
            "vertical"
        ),
        _cutting_item(
            "CAB-TOP-BOTTOM",
            "Top and bottom panel",
            "cabinet",
            width,
            depth,
            2,
            inside_material,
            inside_thickness,
            _edge_map(
                inside_edge_banding,
                top=True,
                left=True,
                right=True
            ),
            "horizontal"
        ),
        _cutting_item(
            "CAB-DIVIDER",
            "Vertical divider",
            "cabinet",
            depth,
            inner_height,
            divider_count,
            inside_material,
            inside_thickness,
            _edge_map(
                inside_edge_banding,
                top=True
            ),
            "vertical"
        ),
        _cutting_item(
            "CAB-BACK",
            "Back panel",
            "cabinet",
            width,
            height,
            1,
            bottom_material,
            None,
            _edge_map(
                None
            ),
            "none"
        ),
        _cutting_item(
            "DRW-FRONT",
            "Drawer front",
            "facades",
            drawer_front_width,
            drawer_front_height,
            drawer_count,
            facade_material,
            facade_thickness,
            _edge_map(
                facade_edge_banding,
                top=True,
                bottom=True,
                left=True,
                right=True
            ),
            "horizontal"
        ),
        _cutting_item(
            "DRW-SIDE",
            "Drawer side",
            "drawers",
            max(
                depth - 80,
                0
            ),
            120,
            drawer_count * 2,
            inside_material,
            inside_thickness,
            _edge_map(
                inside_edge_banding,
                top=True
            ),
            "horizontal"
        ),
        _cutting_item(
            "DRW-FRONT-BACK",
            "Drawer front/back rail",
            "drawers",
            max(
                drawer_front_width - 40,
                0
            ),
            120,
            drawer_count * 2,
            inside_material,
            inside_thickness,
            _edge_map(
                inside_edge_banding,
                top=True
            ),
            "horizontal"
        ),
        _cutting_item(
            "DRW-BOTTOM",
            "Drawer bottom",
            "drawers",
            max(
                drawer_front_width - 40,
                0
            ),
            max(
                depth - 80,
                0
            ),
            drawer_count,
            bottom_material,
            None,
            _edge_map(
                None
            ),
            "none"
        )
    ]

    items = [
        item
        for item in items
        if (
            item["quantity"] > 0
            and item["width"] > 0
            and item["height"] > 0
        )
    ]

    items = _apply_edge_overrides(
        items,
        project.edge_overrides
    )
    assembly_layout = build_project_assembly_layout(
        project
    )

    return {
        "items": items,
        "assembly": build_project_assembly_mapping(
            project,
            items,
            assembly_layout
        ),
        "summary": {
            "total_parts": sum(
                item["quantity"]
                for item in items
            ),
            "total_area_m2": round(
                sum(
                    _area_m2(
                        item
                    )
                    for item in items
                ),
                3
            ),
            "total_cut_length_m": round(
                sum(
                    _cut_length_m(
                        item
                    )
                    for item in items
                ),
                3
            ),
            "total_edge_length_m": round(
                sum(
                    _edge_length_m(
                        item
                    )
                    for item in items
                ),
                3
            )
        }
    }
