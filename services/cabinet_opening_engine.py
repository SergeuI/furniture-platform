THICKNESS = 18


# =====================================================
# ВНУТРІШНЯ ШИРИНА
# =====================================================

def get_inner_width(
    cabinet_width
):

    return (
        cabinet_width
        - THICKNESS * 2
    )


# =====================================================
# ВНУТРІШНЯ ВИСОТА
# =====================================================

def get_inner_height(
    cabinet_height
):

    return (
        cabinet_height
        - THICKNESS * 2
    )


# =====================================================
# КОРИСНА ШИРИНА
# =====================================================

def get_usable_width(
    cabinet_width,
    sections
):

    inner_width = get_inner_width(
        cabinet_width
    )

    partitions = sections - 1

    usable_width = (

        inner_width

        - (
            partitions
            * THICKNESS
        )
    )

    return usable_width


# =====================================================
# ШИРИНА ВІДКРИТТЯ СЕКЦІЇ
# =====================================================

def get_section_opening_width(
    cabinet_width,
    sections
):

    usable_width = get_usable_width(
        cabinet_width,
        sections
    )

    return (
        usable_width / sections
    )


# =====================================================
# ВИСОТА ВІДКРИТТЯ ШАФИ
# =====================================================

def get_cabinet_opening_height(
    cabinet_height,
    plinth_height=0,
    top_rail_height=0
):

    inner_height = get_inner_height(
        cabinet_height
    )

    return (

        inner_height

        - plinth_height

        - top_rail_height
    )


# =====================================================
# ВИСОТА ВІДКРИТТЯ ШКАФІВ
# =====================================================

def get_drawer_stack_opening_height(
    cabinet_height,
    drawers_count,
    plinth_height=0,
    top_rail_height=0
):

    opening_height = (
        get_cabinet_opening_height(
            cabinet_height,
            plinth_height,
            top_rail_height
        )
    )

    return (
        opening_height / drawers_count
    )