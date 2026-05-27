# =====================================================
# DRAWER GEOMETRY
# =====================================================

def calculate_drawer_geometry(

    cabinet_height: int,

    drawers_count: int,

    top_offset: int = 50,

    bottom_offset: int = 50

) -> dict:

    usable_height = (

        cabinet_height
        - top_offset
        - bottom_offset
    )

    drawer_height = (

        usable_height
        / max(drawers_count, 1)
    )

    return {

        "usable_height": usable_height,

        "drawer_height": int(drawer_height),

        "drawers_count": drawers_count
    }


# =====================================================
# TOTAL DRAWERS
# =====================================================

def calculate_total_drawers(

    drawers_config: list[int]
) -> int:

    return sum(drawers_config)


# =====================================================
# DRAWER POSITIONS
# =====================================================

def build_drawer_positions(

    cabinet_height: int,

    drawers_count: int

) -> list[dict]:

    geometry = calculate_drawer_geometry(

        cabinet_height,

        drawers_count
    )

    drawer_height = geometry[
        "drawer_height"
    ]

    positions = []

    current_y = 50

    for index in range(drawers_count):

        positions.append({

            "index": index + 1,

            "y": current_y,

            "height": drawer_height
        })

        current_y += drawer_height

    return positions