# =====================================================
# FACADE POSITION ENGINE
# Позиція фасадів
# =====================================================


# =====================================================
# GENERIC POSITION
# Базова позиція
# =====================================================

def calculate_facade_position(

    x=0,

    y=0,

    z=0
):

    return {

        "x": x,

        "y": y,

        "z": z
    }


# =====================================================
# INSET POSITION
# Позиція вкладного фасаду
# =====================================================

def calculate_inset_position(

    opening_x=0,

    opening_y=0,

    facade_gap=2
):

    return {

        "x": opening_x + facade_gap,

        "y": opening_y + facade_gap,

        "z": 0
    }


# =====================================================
# OVERLAY POSITION
# Позиція накладного фасаду
# =====================================================

def calculate_overlay_position(

    opening_x=0,

    opening_y=0
):

    return {

        "x": opening_x,

        "y": opening_y,

        "z": 0
    }


# =====================================================
# FULL OVERLAY POSITION
# Позиція повної накладки
# =====================================================

def calculate_full_overlay_position(

    opening_x=0,

    opening_y=0,

    overlay=18
):

    return {

        "x": opening_x - overlay,

        "y": opening_y - overlay,

        "z": 0
    }

# =====================================================
# HALF OVERLAY POSITION
# Позиція напівнакладки
# =====================================================

def calculate_half_overlay_position(

    opening_x=0,

    opening_y=0,

    overlay=9
):

    return {

        "x": opening_x - overlay,

        "y": opening_y - overlay,

        "z": 0
    }