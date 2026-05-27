# =====================================================
# GCODE POSTPROCESSOR ENGINE
# Генерація G-code
# =====================================================
from services.machine_post_engine import (
    generate_machine_tool_change
)

# =====================================================
# HEADER
# Початок програми
# =====================================================

def generate_header():

    return [

        "%",
        "G90",
        "G21",
        "G17",
        "M3 S18000"
    ]


# =====================================================
# FOOTER
# Кінець програми
# =====================================================

def generate_footer():

    return [

        "M5",
        "G0 Z50",
        "M30",
        "%"
    ]


# =====================================================
# TOOL CHANGE
# Заміна інструмента
# =====================================================

def generate_tool_change(

    tool_id
):

    return [

        f"M6 {tool_id}"
    ]


# =====================================================
# MOTION → GCODE
# Конвертація руху
# =====================================================

def motion_to_gcode(

    motion
):

    gcode = motion.get(
        "gcode",
        "G1"
    )

    line = f"{gcode}"

    if "x" in motion:

        line += (
            f" X{motion['x']}"
        )

    if "y" in motion:

        line += (
            f" Y{motion['y']}"
        )

    if "z" in motion:

        line += (
            f" Z{motion['z']}"
        )

    if "feed" in motion:

        line += (
            f" F{motion['feed']}"
        )

    if "radius" in motion:

        line += (
            f" R{motion['radius']}"
        )

    return line


# =====================================================
# BUILD GCODE
# Побудова G-code
# =====================================================

def build_gcode(

    toolpath,

    machine="SCM"
):

    gcode = []

    # =============================================
    # HEADER
    # =============================================

    gcode.extend(
        generate_header()
    )

    current_tool = None

    # =============================================
    # TOOLPATH
    # =============================================

    for motion in toolpath:

        tool_id = motion.get(
            "tool_id"
        )

        # =========================================
        # TOOL CHANGE
        # =========================================

        if tool_id != current_tool:

            current_tool = tool_id

            if current_tool:

                gcode.extend(

                    [
                        generate_machine_tool_change(

                            current_tool,

                            machine
                        )
                    ]
                )

        # =========================================
        # GCODE LINE
        # =========================================

        gcode.append(

            motion_to_gcode(
                motion
            )
        )

    # =============================================
    # FOOTER
    # =============================================

    gcode.extend(
        generate_footer()
    )

    return gcode