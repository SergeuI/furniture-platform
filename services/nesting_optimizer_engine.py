# =====================================================
# NESTING OPTIMIZER ENGINE
# Оптимізація розкладки
# =====================================================
from services.rotation_engine import (
    rotate_part
)

# =====================================================
# SAW KERF
# Товщина різу
# =====================================================

SAW_KERF = 4


# =====================================================
# CAN ROTATE
# Перевірка повороту
# =====================================================

def can_rotate(

    part
):

    return part.get(
        "allow_rotate",
        True
    )



# =====================================================
# APPLY KERF
# Компенсація різу
# =====================================================

def apply_kerf(

    value
):

    return value + SAW_KERF


# =====================================================
# OPTIMIZE PART
# Оптимізація деталі
# =====================================================

def optimize_part(

    part,

    sheet_width
):

    width = apply_kerf(
        part["width"]
    )

    height = apply_kerf(
        part["height"]
    )

    # =============================================
    # ROTATION
    # =============================================

    if can_rotate(part):

        rotated = rotate_part(
            part.copy()
        )

        rotated_width = apply_kerf(
            rotated["width"]
        )

        rotated_height = apply_kerf(
            rotated["height"]
        )

        # =========================================
        # USE ROTATED VERSION IF BETTER
        # =========================================

        if (

            rotated_width <= sheet_width

            and

            rotated_width < width
        ):

            rotated["rotated"] = True
            rotated["optimized"] = True
            rotated["rotation"] = 90

            return rotated

    part["rotated"] = False
    part["optimized"] = True
    part["rotation"] = 0

    return part


# =====================================================
# OPTIMIZE NESTING
# Оптимізація розкладки
# =====================================================

def optimize_nesting(

    parts,

    sheet_width
):

    optimized = []

    for part in parts:

        optimized.append(

            optimize_part(

                part,

                sheet_width
            )
        )

    return optimized