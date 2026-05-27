# =====================================================
# CONFIRMAT POSITIONS
# =====================================================

def build_confirmat_positions(

    length: int,

    offset: int = 50

) -> list[int]:

    return [

        offset,

        length - offset
    ]


# =====================================================
# DRAWER SLIDE DRILLING
# =====================================================

def build_slide_drilling(

    drawer_height: int,

    offset_x: int = 37

) -> dict:

    return {

        "left": {

            "x": offset_x,

            "y": drawer_height / 2
        },

        "right": {

            "x": offset_x,

            "y": drawer_height / 2
        }
    }


# =====================================================
# PANEL CENTER
# =====================================================

def calculate_panel_center(

    width: int,

    height: int

) -> dict:

    return {

        "x": width / 2,

        "y": height / 2
    }