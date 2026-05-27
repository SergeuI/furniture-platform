# =====================================================
# CNC COLLISION ENGINE
# CNC безпечна обробка
# =====================================================


# =====================================================
# DEFAULT CLAMP ZONES
# Стандартні зони прижимів
# =====================================================

DEFAULT_CLAMP_ZONES = [

    {
        "x1": 0,
        "y1": 0,
        "x2": 80,
        "y2": 80
    },

    {
        "x1": 0,
        "y1": 1200,
        "x2": 80,
        "y2": 1280
    },

    {
        "x1": 2700,
        "y1": 0,
        "x2": 2800,
        "y2": 80
    },

    {
        "x1": 2700,
        "y1": 1200,
        "x2": 2800,
        "y2": 1280
    }
]


# =====================================================
# CHECK POINT INSIDE ZONE
# Перевірка попадання в зону
# =====================================================

def point_inside_zone(

    x,

    y,

    zone
):

    return (

        zone["x1"]

        <= x

        <= zone["x2"]

        and

        zone["y1"]

        <= y

        <= zone["y2"]
    )


# =====================================================
# CHECK COLLISION
# Перевірка зіткнення
# =====================================================

def check_collision(

    operation,

    clamp_zones=None
):

    if clamp_zones is None:

        clamp_zones = (
            DEFAULT_CLAMP_ZONES
        )

    position = operation.get(
        "global_position",
        {}
    )

    x = position.get(
        "x",
        0
    )

    y = position.get(
        "y",
        0
    )

    for zone in clamp_zones:

        if point_inside_zone(

            x,

            y,

            zone
        ):

            return {

                "collision": True,

                "zone": zone
            }

    return {

        "collision": False
    }


# =====================================================
# FILTER SAFE OPERATIONS
# Фільтрація безпечних операцій
# =====================================================

def filter_safe_operations(

    operations,

    clamp_zones=None
):

    safe_operations = []

    collisions = []

    for operation in operations:

        result = check_collision(

            operation,

            clamp_zones
        )

        if result["collision"]:

            collisions.append({

                "operation": operation,

                "collision_zone": result[
                    "zone"
                ]
            })

        else:

            safe_operations.append(
                operation
            )

    return {

        "safe_operations": safe_operations,

        "collisions": collisions
    }