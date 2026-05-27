# =====================================================
# CNC MACHINE PROFILE ENGINE
# CNC профілі верстатів
# =====================================================


# =====================================================
# MACHINE PROFILES
# Профілі CNC
# =====================================================

MACHINE_PROFILES = {

    "SCM": {

        "max_rpm": 24000,

        "max_feed": 25000,

        "acceleration": 1.2,

        "position_tolerance": 0.02
    },

    "BIESSE": {

        "max_rpm": 22000,

        "max_feed": 22000,

        "acceleration": 1.1,

        "position_tolerance": 0.03
    },

    "HOMAG": {

        "max_rpm": 18000,

        "max_feed": 18000,

        "acceleration": 0.9,

        "position_tolerance": 0.05
    }
}


# =====================================================
# APPLY MACHINE PROFILE
# Застосування профілю CNC
# =====================================================

def apply_machine_profile(

    tool,

    machine="SCM"
):

    profile = MACHINE_PROFILES.get(

        machine,

        MACHINE_PROFILES["SCM"]
    )

    updated_tool = {

        **tool,

        "rpm": min(

            tool["rpm"],

            profile["max_rpm"]
        ),

        "feed": min(

            tool["feed"],

            profile["max_feed"]
        ),

        "machine_profile": machine,

        "acceleration": profile[
            "acceleration"
        ],

        "position_tolerance": profile[
            "position_tolerance"
        ]
    }

    return updated_tool