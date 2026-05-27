from services.plane_transform_engine import (
    transform_to_global
)


# =====================================================
# MACHINING TRANSFORM ENGINE
# Трансформація machining координат
# =====================================================


# =====================================================
# LOCAL HOLE -> GLOBAL HOLE
# =====================================================

def transform_hole_to_global(

    hole,

    part
):

    position = part[
        "position"
    ]

    plane = part.get(
        "plane",
        "XY"
    )

    local = transform_to_global(

        local_x=hole["x"],

        local_y=hole["y"],

        local_z=hole["z"],

        plane=plane
    )

    return {

        **hole,

        "global_position": {

            "x": round(
                position["x"] + local["x"],
                2
            ),

            "y": round(
                position["y"] + local["y"],
                2
            ),

            "z": round(
                position["z"] + local["z"],
                2
            )
        }
    }


# =====================================================
# ВСІ ОТВОРИ ДЕТАЛІ
# =====================================================

def transform_part_drilling(
    part
):

    drilling = part.get(
        "drilling",
        []
    )

    transformed = []

    for hole in drilling:

        transformed.append(

            transform_hole_to_global(

                hole,

                part
            )
        )

    part["global_drilling"] = (
        transformed
    )

    return part