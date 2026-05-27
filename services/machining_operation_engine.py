# =====================================================
# MACHINING OPERATION ENGINE
# CNC операції
# =====================================================
from services.cnc_tool_engine import (

    get_tool_by_diameter,

    get_groove_tool
)
from services.material_machining_engine import (
    apply_material_preset
)
from services.cnc_machine_profile_engine import (
    apply_machine_profile
)
# =====================================================
# THROUGH DRILLING
# Наскрізне свердління
# =====================================================

def create_through_drilling_operation(

    diameter,

    material="DSP",

    machine="SCM"
):
    tool = (
        get_tool_by_diameter(
            diameter
        )
    )

    tool = apply_material_preset(

        tool,

        material
    )

    tool = apply_machine_profile(

        tool,

        machine
    )

    return {

        "operation": "through_drilling",

        "tool_type": "drill",

        "diameter": diameter,

        "depth": "through",

        "tool": tool
    }


# =====================================================
# BLIND DRILLING
# Глухе свердління
# =====================================================

def create_blind_drilling_operation(

    diameter,

    depth,

    material="DSP",

    machine="SCM"
):
    tool = (
        get_tool_by_diameter(
            diameter
        )
    )

    tool = apply_material_preset(

        tool,

        material
    )

    tool = apply_machine_profile(

        tool,

        machine
    )

    return {

        "operation": "blind_drilling",

        "tool_type": "drill",

        "diameter": diameter,

        "depth": depth,

        "tool": tool
    }


# =====================================================
# GROOVE OPERATION
# Паз
# =====================================================

def create_groove_operation(

    width,

    depth,

    material="DSP",

    machine="SCM"
):
    tool = (
        get_groove_tool(
            width
        )
    )

    tool = apply_material_preset(

        tool,

        material
    )

    tool = apply_machine_profile(

        tool,

        machine
    )

    return {

        "operation": "groove",

        "tool_type": "mill",

        "width": width,

        "depth": depth,

        "tool": tool
    }