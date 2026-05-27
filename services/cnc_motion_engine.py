# =====================================================
# CNC MOTION ENGINE
# CNC рухи
# =====================================================


# =====================================================
# RAPID MOVE
# Швидке переміщення (G0)
# =====================================================

def create_rapid_move(

    x,

    y,

    z
):

    return {

        "gcode": "G0",

        "x": x,

        "y": y,

        "z": z
    }


# =====================================================
# LINEAR MOVE
# Робочий рух (G1)
# =====================================================

def create_linear_move(

    x,

    y,

    z,

    feed
):

    return {

        "gcode": "G1",

        "x": x,

        "y": y,

        "z": z,

        "feed": feed
    }


# =====================================================
# CLOCKWISE ARC
# Дуга G2
# =====================================================

def create_arc_cw(

    x,

    y,

    z,

    radius,

    feed
):

    return {

        "gcode": "G2",

        "x": x,

        "y": y,

        "z": z,

        "radius": radius,

        "feed": feed
    }


# =====================================================
# COUNTER CLOCKWISE ARC
# Дуга G3
# =====================================================

def create_arc_ccw(

    x,

    y,

    z,

    radius,

    feed
):

    return {

        "gcode": "G3",

        "x": x,

        "y": y,

        "z": z,

        "radius": radius,

        "feed": feed
    }


# =====================================================
# CUTTER COMPENSATION
# Компенсація фрези
# =====================================================

def apply_cutter_compensation(

    move,

    tool_radius
):

    compensated = {

        **move,

        "tool_radius": tool_radius,

        "compensation": "G41"
    }

    return compensated