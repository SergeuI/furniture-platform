# =====================================================
# SAFE INNER DIMENSIONS
# =====================================================

def calculate_inner_dimensions(

    width: int,

    height: int,

    depth: int,

    material_thickness: int = 18

) -> dict:

    inner_width = (

        width
        - material_thickness * 2
    )

    inner_height = (

        height
        - material_thickness * 2
    )

    inner_depth = depth - 3

    return {

        "inner_width": inner_width,

        "inner_height": inner_height,

        "inner_depth": inner_depth
    }


# =====================================================
# SECTION WIDTH
# =====================================================

def calculate_section_width(

    width: int,

    sections: int,

    material_thickness: int = 18

) -> float:

    usable_width = (

        width
        - material_thickness * 2
    )

    return usable_width / max(
        sections,
        1
    )


# =====================================================
# DRAWER HEIGHT
# =====================================================

def calculate_drawer_height(

    height: int,

    drawers: int

) -> float:

    usable_height = height - 100

    return usable_height / max(
        drawers,
        1
    )