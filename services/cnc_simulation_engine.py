# =====================================================
# CNC SIMULATION ENGINE
# CNC симуляція
# =====================================================
from services.cnc_toolpath_engine import (
    build_toolpath
)

# =====================================================
# SAFE Z HEIGHT
# Безпечна висота переміщення
# =====================================================

SAFE_Z_HEIGHT = 50


# =====================================================
# CREATE SAFE TRAVEL
# Безпечне переміщення
# =====================================================

def create_safe_travel(

    current_position,

    next_position
):

    return {

        "type": "safe_travel",

        "from": {

            "x": current_position["x"],

            "y": current_position["y"],

            "z": SAFE_Z_HEIGHT
        },

        "to": {

            "x": next_position["x"],

            "y": next_position["y"],

            "z": SAFE_Z_HEIGHT
        }
    }


# =====================================================
# REPOSITION CLAMP
# Переміщення прижиму
# =====================================================

def reposition_clamp(

    clamp_zone
):

    return {

        "type": "clamp_reposition",

        "old_zone": clamp_zone,

        "new_zone": {

            "x1": clamp_zone["x1"] + 150,

            "y1": clamp_zone["y1"],

            "x2": clamp_zone["x2"] + 150,

            "y2": clamp_zone["y2"]
        }
    }


# =====================================================
# BUILD CNC SIMULATION
# Побудова симуляції
# =====================================================

def build_cnc_simulation(

    operations,

    collisions
):

    simulation = []

    current_position = {

        "x": 0,

        "y": 0,

        "z": SAFE_Z_HEIGHT
    }

    # =============================================
    # SAFE TRAVEL
    # =============================================

    for operation in operations:

        next_position = operation[
            "global_position"
        ]

        simulation.append(

            create_safe_travel(

                current_position,

                next_position
            )
        )

        simulation.append({

            "type": "machining",

            "operation": operation
        })

        current_position = next_position

    # =============================================
    # COLLISION HANDLING
    # =============================================

    for collision in collisions:

        simulation.append(

            reposition_clamp(

                collision[
                    "collision_zone"
                ]
            )
        )

    toolpath = (
        build_toolpath(
            operations
        )
    )

    return {

        "simulation": simulation,

        "toolpath": toolpath
    }