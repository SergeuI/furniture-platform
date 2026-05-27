# =====================================================
# DRAWER GEOMETRY ENGINE
# Геометрія шухляд
# =====================================================


# =====================================================
# ВИСОТА ЗАДНЬОЇ СТІНКИ
# =====================================================

def calculate_back_height(

    drawer_height,

    groove
):

    return (

        drawer_height

        - groove["offset"]
    )


# =====================================================
# ВИСОТА ПЕРЕДУ
# =====================================================

def calculate_front_height(

    drawer_height,

    groove
):

    return (

        drawer_height

        - groove["offset"]
    )


# =====================================================
# ВНУТРІШНЯ ШИРИНА ДНА
# =====================================================

def calculate_bottom_inner_width(

    drawer_width,

    groove
):

    return (

        drawer_width

        - groove["depth"] * 2
    )


# =====================================================
# ВНУТРІШНЯ ГЛИБИНА ДНА
# =====================================================

def calculate_bottom_inner_depth(

    drawer_depth,

    groove
):

    return (

        drawer_depth

        - groove["depth"] * 2
    )