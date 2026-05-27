# =====================================================
# CUTTING OPTIMIZATION ENGINE
# Оптимізація розкрою
# =====================================================


# =====================================================
# SORT VERTICAL FIRST
# Спочатку вертикальні різи
# =====================================================

def sort_vertical_first(

    cuts
):

    return sorted(

        cuts,

        key=lambda cut: (

            0

            if cut[
                "direction"
            ] == "vertical"

            else 1
        )
    )


# =====================================================
# SORT BY POSITION
# Сортування по позиції
# =====================================================

def sort_by_position(

    cuts
):

    return sorted(

        cuts,

        key=lambda cut: (

            cut[
                "start"
            ][
                "x"
            ],

            cut[
                "start"
            ][
                "y"
            ]
        )
    )


# =====================================================
# APPLY GRAIN DIRECTION
# Напрям текстури
# =====================================================

def apply_grain_direction(

    cuts,

    grain_direction="vertical"
):

    if grain_direction == "horizontal":

        return sorted(

            cuts,

            key=lambda cut: (

                cut[
                    "start"
                ][
                    "y"
                ]
            )
        )

    return sorted(

        cuts,

        key=lambda cut: (

            cut[
                "start"
            ][
                "x"
            ]
        )
    )


# =====================================================
# OPTIMIZE CUTTING MAP
# Оптимізація карти розкрою
# =====================================================

def optimize_cutting_map(

    cutting_map,

    grain_direction="vertical"
):

    cuts = cutting_map.get(
        "cuts",
        []
    )

    # =============================================
    # VERTICAL FIRST
    # =============================================

    cuts = sort_vertical_first(
        cuts
    )

    # =============================================
    # GRAIN
    # =============================================

    cuts = apply_grain_direction(

        cuts,

        grain_direction
    )

    # =============================================
    # POSITION
    # =============================================

    cuts = sort_by_position(
        cuts
    )

    return {

        **cutting_map,

        "cuts": cuts,

        "optimized": True,

        "grain_direction": grain_direction
    }