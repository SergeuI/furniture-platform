# =====================================================
# CNC TOOL ENGINE
# CNC інструменти
# =====================================================


# =====================================================
# TOOL LIBRARY
# Бібліотека інструментів
# =====================================================

TOOL_LIBRARY = {

    3: {

        "tool_id": "T1",

        "type": "drill",

        "diameter": 3,

        "rpm": 18000,

        "feed": 2500
    },

    5: {

        "tool_id": "T2",

        "type": "drill",

        "diameter": 5,

        "rpm": 16000,

        "feed": 2200
    },

    8: {

        "tool_id": "T3",

        "type": "drill",

        "diameter": 8,

        "rpm": 14000,

        "feed": 1800
    },

    10: {

        "tool_id": "T4",

        "type": "drill",

        "diameter": 10,

        "rpm": 12000,

        "feed": 1500
    },

    "groove_4": {

        "tool_id": "T10",

        "type": "mill",

        "diameter": 4,

        "rpm": 18000,

        "feed": 3200
    },

    "groove_6": {

        "tool_id": "T11",

        "type": "mill",

        "diameter": 6,

        "rpm": 16000,

        "feed": 2800
    }
}


# =====================================================
# GET TOOL BY DIAMETER
# Отримання інструмента
# =====================================================

def get_tool_by_diameter(

    diameter
):

    return TOOL_LIBRARY.get(
        diameter
    )


# =====================================================
# GET GROOVE TOOL
# Отримання фрези для пазу
# =====================================================

def get_groove_tool(

    groove_width
):

    if groove_width <= 4:

        return TOOL_LIBRARY[
            "groove_4"
        ]

    return TOOL_LIBRARY[
        "groove_6"
    ]