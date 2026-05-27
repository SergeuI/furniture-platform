# =====================================================
# LOCAL COORDINATE ENGINE
# Локальна система координат
# =====================================================


# =====================================================
# СТВОРЕННЯ ЛОКАЛЬНОЇ СИСТЕМИ
# =====================================================

def create_local_coordinate_system(

    origin_x=0,
    origin_y=0,
    origin_z=0
):

    return {

        "origin": {

            "x": origin_x,

            "y": origin_y,

            "z": origin_z
        },

        "axis": {

            "x": [1, 0, 0],

            "y": [0, 1, 0],

            "z": [0, 0, 1]
        }
    }


# =====================================================
# ДОДАТИ LOCAL SYSTEM ДО ДЕТАЛІ
# =====================================================

def apply_local_coordinates(
    part,
    local_system
):

    part["local_coordinates"] = local_system

    return part


# =====================================================
# ПЕРЕТВОРЕННЯ LOCAL -> GLOBAL
# =====================================================

def local_to_global(

    local_x,
    local_y,
    local_z,

    position
):

    return {

        "x": round(
            position["x"] + local_x,
            2
        ),

        "y": round(
            position["y"] + local_y,
            2
        ),

        "z": round(
            position["z"] + local_z,
            2
        )
    }


# =====================================================
# GLOBAL -> LOCAL
# =====================================================

def global_to_local(

    global_x,
    global_y,
    global_z,

    position
):

    return {

        "x": round(
            global_x - position["x"],
            2
        ),

        "y": round(
            global_y - position["y"],
            2
        ),

        "z": round(
            global_z - position["z"],
            2
        )
    }


# =====================================================
# ЛОКАЛЬНИЙ ОТВІР
# =====================================================

def create_local_hole(

    local_x,
    local_y,
    local_z,

    diameter,
    depth,

    axis="Z",

    face="front"
):

    return {

        "local_position": {

            "x": local_x,

            "y": local_y,

            "z": local_z
        },

        "diameter": diameter,

        "depth": depth,

        "axis": axis,

        "face": face
    }