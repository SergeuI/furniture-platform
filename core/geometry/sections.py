# =====================================================
# SECTION GEOMETRY
# =====================================================

def build_sections_geometry(

    total_width: int,

    sections_count: int,

    material_thickness: int = 18

) -> dict:

    usable_width = (

        total_width
        - material_thickness * 2
    )

    section_width = (

        usable_width
        / max(sections_count, 1)
    )

    return {

        "usable_width": usable_width,

        "section_width": section_width,

        "sections_count": sections_count
    }


# =====================================================
# DRAWERS PER SECTION
# =====================================================

def calculate_drawers_per_section(

    drawers_config: list[int]
) -> list[dict]:

    result = []

    for index, drawers in enumerate(
        drawers_config
    ):

        result.append({

            "section_index": index + 1,

            "drawers": drawers
        })

    return result