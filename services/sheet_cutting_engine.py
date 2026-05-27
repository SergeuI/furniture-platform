# =====================================================
# SHEET CUTTING ENGINE
# Карта розпилу листа
# =====================================================
from models.nesting_model import (
    CutLine
)

# =====================================================
# CREATE CUT
# Створення різу
# =====================================================

def create_cut(

    start_x,

    start_y,

    end_x,

    end_y,

    direction
):

    cut = CutLine(

        start_x=start_x,

        start_y=start_y,

        end_x=end_x,

        end_y=end_y,

        direction=direction
    )

    return cut.to_dict()


# =====================================================
# VERTICAL CUT
# Вертикальний різ
# =====================================================

def create_vertical_cut(

    x,

    y1,

    y2
):

    return create_cut(

        x,

        y1,

        x,

        y2,

        "vertical"
    )


# =====================================================
# HORIZONTAL CUT
# Горизонтальний різ
# =====================================================

def create_horizontal_cut(

    y,

    x1,

    x2
):

    return create_cut(

        x1,

        y,

        x2,

        y,

        "horizontal"
    )


# =====================================================
# BUILD CUTTING MAP
# Побудова карти розпилу
# =====================================================

def build_cutting_map(

    nesting
):

    cuts = []

    parts = nesting.get(
        "parts",
        []
    )

    for part in parts:

        if part.get(
            "unplaced"
        ):

            continue

        position = part[
            "sheet_position"
        ]

        x = position["x"]

        y = position["y"]

        width = part["width"]

        height = part["height"]

        # =========================================
        # LEFT
        # =========================================

        cuts.append(

            create_vertical_cut(

                x,

                y,

                y + height
            )
        )

        # =========================================
        # RIGHT
        # =========================================

        cuts.append(

            create_vertical_cut(

                x + width,

                y,

                y + height
            )
        )

        # =========================================
        # TOP
        # =========================================

        cuts.append(

            create_horizontal_cut(

                y,

                x,

                x + width
            )
        )

        # =========================================
        # BOTTOM
        # =========================================

        cuts.append(

            create_horizontal_cut(

                y + height,

                x,

                x + width
            )
        )

    return {

        "sheet": nesting[
            "sheet"
        ],

        "cuts": cuts,

        "parts": parts,

        "utilization": nesting.get(
            "utilization",
            0
        )
    }