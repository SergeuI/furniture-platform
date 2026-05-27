# =====================================================
# CABINET CONTEXT ENGINE
# Контекст меблів
# =====================================================


# =====================================================
# СТВОРЕННЯ КОНТЕКСТУ
# =====================================================

def create_cabinet_context(

    left_wall=False,
    right_wall=False,

    left_section=False,
    right_section=False,

    cabinet_type="base"
):

    return {

        # Стіни
        "left_wall": left_wall,

        "right_wall": right_wall,

        # Сусідні секції
        "left_section": left_section,

        "right_section": right_section,

        # Тип корпуса
        "cabinet_type": cabinet_type
    }


# =====================================================
# ЛІВА БОКОВИНА ВИДИМА
# =====================================================

def is_left_side_visible(
    context
):

    # Біля стіни
    if context["left_wall"]:

        return False

    # Є сусідня секція
    if context["left_section"]:

        return False

    return True


# =====================================================
# ПРАВА БОКОВИНА ВИДИМА
# =====================================================

def is_right_side_visible(
    context
):

    if context["right_wall"]:

        return False

    if context["right_section"]:

        return False

    return True


# =====================================================
# ВИДИМІ ТОРЦІ БОКОВИНИ
# =====================================================

def get_side_visibility(

    side,

    context
):

    result = []

    # =========================================
    # LEFT
    # =========================================

    if side == "left":

        if is_left_side_visible(
            context
        ):

            result.append(
                "left"
            )

    # =========================================
    # RIGHT
    # =========================================

    if side == "right":

        if is_right_side_visible(
            context
        ):

            result.append(
                "right"
            )

    # Перед завжди видимий
    result.append(
        "front"
    )

    return result