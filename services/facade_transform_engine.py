# =====================================================
# FACADE TRANSFORM ENGINE
# Трансформація фасадів
# =====================================================

from services.plane_transform_engine import (
    transform_to_global
)

from services.machining_sequence_engine import (
    build_machining_sequence
)

from services.cnc_collision_engine import (
    filter_safe_operations
)

from services.cnc_simulation_engine import (
    build_cnc_simulation
)

from services.gcode_postprocessor_engine import (
    build_gcode
)

from models.machining_model import (

    ToolModel,

    MachinePosition,

    MachiningOperation
)


# =====================================================
# DEFAULT TOOL
# Стандартний CNC інструмент
# =====================================================

DEFAULT_DRILL_TOOL = ToolModel(

    tool_id="T1",

    name="Drill 5mm",

    diameter=5,

    depth=15,

    feed=3000,

    rpm=18000,

    tool_type="drill"
).to_dict()


# =====================================================
# TRANSFORM FACADE DRILLING
# =====================================================

def transform_facade_drilling(

    facade
):

    position = facade.get(

        "position",

        {
            "x": 0,
            "y": 0,
            "z": 0
        }
    )

    drilling = facade.get(

        "drilling",

        []
    )

    transformed = []

    # =================================================
    # DRILLING TRANSFORM
    # =================================================

    for hole in drilling:

        local = transform_to_global(

            local_x=hole["x"],

            local_y=hole["y"],

            local_z=hole.get(
                "z",
                0
            ),

            plane="XY"
        )

        global_position = MachinePosition(

            x=round(

                position["x"]
                + local["x"],

                2
            ),

            y=round(

                position["y"]
                + local["y"],

                2
            ),

            z=round(

                position["z"]
                + local["z"],

                2
            )
        )

        # =============================================
        # TOOL
        # =============================================

        tool = ToolModel(

            tool_id="T1",

            name=hole.get(

                "tool_name",

                "Drill 5mm"
            ),

            diameter=hole.get(
                "diameter",
                5
            ),

            depth=hole.get(
                "depth",
                15
            ),

            feed=3000,

            rpm=18000,

            tool_type="drill"
        ).to_dict()

        # =============================================
        # MACHINING OPERATION
        # =============================================

        operation = MachiningOperation(

            operation_type="drilling",

            position=global_position.to_dict(),

            tool=tool,

            depth=hole.get(
                "depth",
                15
            ),

            direction=hole.get(
                "direction",
                {}
            ),

            metadata={

                "source": "facade",

                "original_hole": hole
            }
        )

        transformed.append(
            operation.to_dict()
        )

    # =================================================
    # MACHINING SEQUENCE
    # =================================================

    transformed = (
        build_machining_sequence(
            transformed
        )
    )

    # =================================================
    # COLLISION DETECTION
    # =================================================

    collision_result = (
        filter_safe_operations(
            transformed
        )
    )

    transformed = collision_result[
        "safe_operations"
    ]

    facade[
        "collisions"
    ] = collision_result[
        "collisions"
    ]

    # =================================================
    # CNC SIMULATION
    # =================================================

    simulation_data = (
        build_cnc_simulation(

            transformed,

            collision_result[
                "collisions"
            ]
        )
    )

    facade[
        "simulation"
    ] = simulation_data[
        "simulation"
    ]

    # =================================================
    # TOOLPATH
    # =================================================

    facade[
        "toolpath"
    ] = simulation_data[
        "toolpath"
    ]

    # =================================================
    # GCODE
    # =================================================

    facade[
        "gcode"
    ] = build_gcode(

        simulation_data[
            "toolpath"
        ],

        machine="SCM"
    )

    # =================================================
    # GLOBAL DRILLING
    # =================================================

    facade[
        "global_drilling"
    ] = transformed

    return facade