# =====================================================
# DRAWER VALIDATION
# =====================================================

def validate_drawer_height(

    drawer_height: int,

    minimum_height: int = 120

) -> bool:

    return drawer_height >= minimum_height


# =====================================================
# DRAWERS VALIDATION
# =====================================================

def validate_drawers_configuration(

    cabinet_height: int,

    drawers_count: int

) -> dict:

    usable_height = cabinet_height - 100

    drawer_height = (

        usable_height
        / max(drawers_count, 1)
    )

    valid = drawer_height >= 120

    return {

        "success": valid,

        "drawer_height": int(drawer_height),

        "minimum_height": 120,

        "drawers_count": drawers_count
    }