from collections import defaultdict

from services.project_cutting_service import (
    build_project_cutting,
)
from services.project_part_detail_service import (
    build_project_part_detail,
)


def _round_metric(value):

    return round(float(value or 0), 3)


def _append_requirement(items, **payload):

    items.append(
        {
            "category": payload.get("category"),
            "code": payload.get("code"),
            "name": payload.get("name"),
            "unit": payload.get("unit"),
            "quantity": payload.get("quantity"),
            "meta": payload.get("meta") or {},
            "match_terms": payload.get("match_terms") or [],
        }
    )


def build_project_service_requirements(project):

    cutting = build_project_cutting(project)
    cutting_items = cutting["items"]
    summary = cutting["summary"]

    operations: list[dict] = []
    fittings: list[dict] = []

    if summary.get("total_area_m2"):
        _append_requirement(
            operations,
            category="operation",
            code="cutting_area",
            name="Порізка плитного матеріалу",
            unit="m2",
            quantity=_round_metric(summary["total_area_m2"]),
            meta={
                "total_parts": summary.get("total_parts", 0),
                "total_cut_length_m": _round_metric(summary.get("total_cut_length_m", 0)),
            },
            match_terms=["порізка", "розпил", "cutting"],
        )

    edge_length_by_material = defaultdict(float)
    edge_count_by_material = defaultdict(int)
    holes_by_type = defaultdict(int)
    grooves_by_type = defaultdict(lambda: {"count": 0, "length_m": 0.0})
    quarters_by_type = defaultdict(lambda: {"count": 0, "length_m": 0.0})

    for part in cutting_items:
        quantity = max(int(part.get("quantity") or 0), 0)

        if not quantity:
            continue

        for side in ("top", "bottom", "left", "right"):
            material = part.get(f"edge_{side}")

            if not material or material == "not_set":
                continue

            edge_length_mm = part["width"] if side in ("top", "bottom") else part["height"]
            edge_length_by_material[material] += (edge_length_mm * quantity) / 1000
            edge_count_by_material[material] += quantity

        detail = build_project_part_detail(project, part["export_code"])

        if not detail:
            continue

        for hole in detail.get("holes", []):
            hole_type = hole.get("type") or "drilling"
            holes_by_type[hole_type] += quantity

        for groove in detail.get("grooves", []):
            groove_type = groove.get("type") or "groove"
            grooves_by_type[groove_type]["count"] += quantity
            grooves_by_type[groove_type]["length_m"] += (
                float(groove.get("length") or 0) * quantity
            ) / 1000

        for quarter in detail.get("quarters", []):
            quarter_type = quarter.get("type") or "quarter"
            quarters_by_type[quarter_type]["count"] += quantity
            quarters_by_type[quarter_type]["length_m"] += (
                float(quarter.get("length") or 0) * quantity
            ) / 1000

    for material, length_m in sorted(edge_length_by_material.items()):
        _append_requirement(
            operations,
            category="operation",
            code=f"edge_{material}",
            name=f"Кромкування {material}",
            unit="m",
            quantity=_round_metric(length_m),
            meta={
                "edge_material": material,
                "operations_count": edge_count_by_material[material],
            },
            match_terms=["кромка", "кромкування", "поклейка", material],
        )

    for hole_type, count in sorted(holes_by_type.items()):
        _append_requirement(
            operations,
            category="operation",
            code=f"drilling_{hole_type}",
            name=f"Свердління {hole_type}",
            unit="pcs",
            quantity=int(count),
            meta={
                "hole_type": hole_type,
            },
            match_terms=["свердління", "присадка", hole_type],
        )

    for groove_type, data in sorted(grooves_by_type.items()):
        _append_requirement(
            operations,
            category="operation",
            code=f"groove_{groove_type}",
            name=f"Пазування {groove_type}",
            unit="pcs",
            quantity=int(data["count"]),
            meta={
                "length_m": _round_metric(data["length_m"]),
                "groove_type": groove_type,
            },
            match_terms=["паз", "фрезерування", groove_type],
        )

    for quarter_type, data in sorted(quarters_by_type.items()):
        _append_requirement(
            operations,
            category="operation",
            code=f"quarter_{quarter_type}",
            name=f"Чверть {quarter_type}",
            unit="pcs",
            quantity=int(data["count"]),
            meta={
                "length_m": _round_metric(data["length_m"]),
                "quarter_type": quarter_type,
            },
            match_terms=["чверть", "фрезерування", quarter_type],
        )

    drawer_count = sum(int(value) for value in (project.drawers or []) if isinstance(value, int))

    if project.slide_type and drawer_count:
        _append_requirement(
            fittings,
            category="fitting",
            code="drawer_slides",
            name=f"Направляючі {project.slide_type}",
            unit="set",
            quantity=drawer_count,
            meta={
                "slide_type": project.slide_type,
            },
            match_terms=["направляючі", "slide", project.slide_type],
        )

    if project.handle_type and drawer_count:
        _append_requirement(
            fittings,
            category="fitting",
            code="handles",
            name=f"Ручки {project.handle_type}",
            unit="pcs",
            quantity=drawer_count,
            meta={
                "handle_type": project.handle_type,
                "handle_position": project.handle_position,
            },
            match_terms=["ручка", "handle", project.handle_type],
        )

    if project.bottom_type:
        _append_requirement(
            fittings,
            category="fitting",
            code="drawer_bottom_material",
            name=f"Матеріал дна {project.bottom_type}",
            unit="type",
            quantity=1,
            meta={
                "bottom_type": project.bottom_type,
            },
            match_terms=["дно", "bottom", project.bottom_type],
        )

    return {
        "operations": operations,
        "fittings": fittings,
        "summary": {
            "operations_count": len(operations),
            "fittings_count": len(fittings),
            "total_cut_area_m2": _round_metric(summary.get("total_area_m2", 0)),
            "total_cut_length_m": _round_metric(summary.get("total_cut_length_m", 0)),
            "total_edge_length_m": _round_metric(summary.get("total_edge_length_m", 0)),
            "total_parts": int(summary.get("total_parts", 0)),
        },
    }
