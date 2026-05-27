from core.geometry.sections import (
    build_sections_geometry
)

from core.geometry.drawers import (
    calculate_drawer_geometry
)

from core.validation.drawers import (
    validate_drawers_configuration
)

from core.bom.materials import (
    calculate_material_area
)

from core.machining.drilling import (
    build_confirmat_positions
)


# =====================================================
# BUILD PROJECT
# =====================================================

def build_project(

    width: int,

    height: int,

    depth: int,

    sections_count: int,

    drawers_config: list[int]
) -> dict:

    # =========================================
    # SECTIONS
    # =========================================

    sections_geometry = (

        build_sections_geometry(

            total_width=width,

            sections_count=sections_count
        )
    )

    # =========================================
    # DRAWERS
    # =========================================

    drawers_result = []

    for drawers in drawers_config:

        geometry = calculate_drawer_geometry(

            cabinet_height=height,

            drawers_count=drawers
        )

        validation = (

            validate_drawers_configuration(

                cabinet_height=height,

                drawers_count=drawers
            )
        )

        drawers_result.append({

            "drawers": drawers,

            "geometry": geometry,

            "validation": validation
        })

    # =========================================
    # MATERIAL AREA
    # =========================================

    total_area = calculate_material_area(
        width,
        height
    )

    # =========================================
    # DRILLING
    # =========================================

    drilling = build_confirmat_positions(
        width
    )

    # =========================================
    # RESULT
    # =========================================

    return {

        "sections": sections_geometry,

        "drawers": drawers_result,

        "material_area": total_area,

        "drilling": drilling
    }