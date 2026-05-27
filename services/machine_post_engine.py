# =====================================================
# MACHINE POST ENGINE
# CNC dialects
# =====================================================


# =====================================================
# SCM
# =====================================================

def scm_tool_change(

    tool_id
):

    return f"M6 {tool_id}"


# =====================================================
# HOMAG
# =====================================================

def homag_tool_change(

    tool_id
):

    return f"TOOL CALL {tool_id}"


# =====================================================
# BIESSE
# =====================================================

def biesse_tool_change(

    tool_id
):

    return f"BEGIN TOOL {tool_id}"


# =====================================================
# TOOL CHANGE BY MACHINE
# =====================================================

def generate_machine_tool_change(

    tool_id,

    machine="SCM"
):

    if machine == "HOMAG":

        return homag_tool_change(
            tool_id
        )

    if machine == "BIESSE":

        return biesse_tool_change(
            tool_id
        )

    return scm_tool_change(
        tool_id
    )