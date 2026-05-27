# =====================================================
# OVERLAY ENGINE
# Логіка фасадів
# =====================================================


# =====================================================
# INSET
# =====================================================

def calculate_inset_facade(

    opening_width,

    opening_height,

    gaps
):

    return {

        "width": (

            opening_width

            - gaps["left"]

            - gaps["right"]
        ),

        "height": (

            opening_height

            - gaps["top"]

            - gaps["bottom"]
        ),

        "type": "inset"
    }


# =====================================================
# FULL OVERLAY
# =====================================================

def calculate_full_overlay_facade(

    opening_width,

    opening_height,

    overlay
):

    return {

        "width": (
            opening_width
            + overlay * 2
        ),

        "height": (
            opening_height
            + overlay * 2
        ),

        "type": "full_overlay"
    }


# =====================================================
# HALF OVERLAY
# =====================================================

def calculate_half_overlay_facade(

    opening_width,

    opening_height,

    overlay
):

    return {

        "width": (
            opening_width
            + overlay
        ),

        "height": (
            opening_height
            + overlay
        ),

        "type": "half_overlay"
    }