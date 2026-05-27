# =====================================================
# MATERIAL MACHINING ENGINE
# Налаштування обробки матеріалів
# =====================================================


# =====================================================
# MATERIAL PRESETS
# Пресети матеріалів
# =====================================================

MATERIAL_PRESETS = {

    "DSP": {

        "rpm_multiplier": 0.9,

        "feed_multiplier": 0.85,

        "chip_load": 0.22
    },

    "MDF": {

        "rpm_multiplier": 1.1,

        "feed_multiplier": 1.0,

        "chip_load": 0.18
    },

    "HDF": {

        "rpm_multiplier": 0.8,

        "feed_multiplier": 0.7,

        "chip_load": 0.12
    }
}


# =====================================================
# APPLY MATERIAL PRESET
# Застосування матеріалу
# =====================================================

def apply_material_preset(

    tool,

    material
):

    preset = MATERIAL_PRESETS.get(

        material,

        MATERIAL_PRESETS["DSP"]
    )

    updated_tool = {

        **tool,

        "rpm": int(

            tool["rpm"]

            * preset[
                "rpm_multiplier"
            ]
        ),

        "feed": int(

            tool["feed"]

            * preset[
                "feed_multiplier"
            ]
        ),

        "chip_load": preset[
            "chip_load"
        ],

        "material": material
    }

    return updated_tool