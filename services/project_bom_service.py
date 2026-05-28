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


def _bom_item(
    part_name,
    category,
    quantity,
    material=None,
    thickness=None,
    edge_banding=None,
    notes=None
):

    return {
        "part_name": part_name,
        "category": category,
        "quantity": max(
            int(quantity),
            0
        ),
        "material": _safe_text(
            material
        ),
        "thickness": thickness,
        "edge_banding": _safe_text(
            edge_banding
        ),
        "notes": notes
    }


def build_project_bom(project):

    drawer_count = _drawer_count(
        project
    )

    section_count = max(
        int(project.sections or 0),
        0
    )

    inside_material = _safe_text(
        project.inside_material
    )
    facade_material = _safe_text(
        project.facade_material,
        inside_material
    )

    material_thickness = project.material_thickness or 18

    items = [
        _bom_item(
            "Side panels",
            "cabinet",
            2,
            inside_material,
            material_thickness,
            project.edge_banding
        ),
        _bom_item(
            "Top and bottom panels",
            "cabinet",
            2,
            inside_material,
            material_thickness,
            project.edge_banding
        ),
        _bom_item(
            "Vertical dividers",
            "cabinet",
            max(
                section_count - 1,
                0
            ),
            inside_material,
            material_thickness,
            project.edge_banding
        ),
        _bom_item(
            "Back panel",
            "cabinet",
            1,
            project.bottom_type or "hdf",
            None,
            None
        ),
        _bom_item(
            "Drawer boxes",
            "drawers",
            drawer_count,
            inside_material,
            material_thickness,
            project.edge_banding
        ),
        _bom_item(
            "Drawer fronts",
            "facades",
            drawer_count,
            facade_material,
            material_thickness,
            project.edge_banding
        ),
        _bom_item(
            "Drawer slides",
            "fittings",
            drawer_count,
            project.slide_type,
            None,
            None
        ),
        _bom_item(
            "Drawer bottoms",
            "drawers",
            drawer_count,
            project.bottom_type,
            None,
            None
        )
    ]

    if project.handle_type or project.handle_position:

        items.append(
            _bom_item(
                "Handles",
                "fittings",
                drawer_count,
                project.handle_type or project.handle_position,
                None,
                None,
                project.handle_position
            )
        )

    return [
        item
        for item in items
        if item["quantity"] > 0
    ]
