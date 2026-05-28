from services.project_cutting_service import (
    build_project_cutting
)


def _edge_operations(part):

    return [
        {
            "side": "top",
            "material": part.get("edge_top"),
            "length": part["width"]
        },
        {
            "side": "bottom",
            "material": part.get("edge_bottom"),
            "length": part["width"]
        },
        {
            "side": "left",
            "material": part.get("edge_left"),
            "length": part["height"]
        },
        {
            "side": "right",
            "material": part.get("edge_right"),
            "length": part["height"]
        }
    ]


def _has_real_edge(edge):

    return bool(edge["material"]) and edge["material"] != "not_set"


def _cabinet_side_holes(part):

    width = part["width"]
    height = part["height"]

    positions = [
        (50, 21),
        (max(width - 50, 0), 21),
        (50, max(height - 21, 0)),
        (max(width - 50, 0), max(height - 21, 0))
    ]

    return [
        {
            "number": index + 1,
            "side": "back",
            "origin": "left_bottom",
            "x": x,
            "y": y,
            "z": 0,
            "diameter": 5,
            "depth": 12,
            "type": "confirmat_face"
        }
        for index, (x, y) in enumerate(
            positions
        )
    ]


def _drawer_front_holes(part, project):

    if not project.handle_type and not project.handle_position:

        return []

    width = part["width"]
    height = part["height"]
    center = width / 2
    spacing = min(
        128,
        max(width - 80, 0)
    )
    y = min(
        40,
        max(height / 2, 0)
    )

    return [
        {
            "number": 1,
            "side": "front",
            "origin": "left_bottom",
            "x": round(center - spacing / 2, 2),
            "y": round(y, 2),
            "z": 0,
            "diameter": 5,
            "depth": part.get("thickness") or 18,
            "type": "handle"
        },
        {
            "number": 2,
            "side": "front",
            "origin": "left_bottom",
            "x": round(center + spacing / 2, 2),
            "y": round(y, 2),
            "z": 0,
            "diameter": 5,
            "depth": part.get("thickness") or 18,
            "type": "handle"
        }
    ]


def _grooves(part):

    if part["export_code"] not in (
        "DRW-SIDE",
        "DRW-FRONT-BACK"
    ):

        return []

    return [
        {
            "number": 1,
            "side": "front",
            "origin": "left_bottom",
            "x": 0,
            "y": 12,
            "depth": 8,
            "width": 4,
            "length": part["width"],
            "type": "bottom_groove"
        }
    ]


def _quarters(part, project):

    if part["export_code"] != "DRW-BOTTOM":

        return []

    if not project.bottom_type or "dsp" not in project.bottom_type:

        return []

    return [
        {
            "number": 1,
            "side": "bottom",
            "origin": "left_bottom",
            "x": 0,
            "y": 0,
            "depth": 12,
            "width": 2,
            "length": part["width"],
            "radius": 0,
            "type": "bottom_quarter"
        }
    ]


def _holes(part, project):

    if part["export_code"] == "CAB-SIDE":

        return _cabinet_side_holes(
            part
        )

    if part["export_code"] == "DRW-FRONT":

        return _drawer_front_holes(
            part,
            project
        )

    return []


def build_project_part_detail(project, part_code):

    cutting = build_project_cutting(
        project
    )

    part = next(
        (
            item
            for item in cutting["items"]
            if item["export_code"] == part_code
        ),
        None
    )

    if not part:

        return None

    return {
        "part": part,
        "edges": [
            edge
            for edge in _edge_operations(
                part
            )
            if _has_real_edge(
                edge
            )
        ],
        "holes": _holes(
            part,
            project
        ),
        "grooves": _grooves(
            part
        ),
        "quarters": _quarters(
            part,
            project
        )
    }
