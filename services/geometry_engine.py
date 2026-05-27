from services.get_slide_rules import (
    get_slide_rules
)

THICKNESS = 18


# =====================================================
# INNER WIDTH
# =====================================================

def get_inner_width(width):

    return width - THICKNESS * 2


# =====================================================
# INNER HEIGHT
# =====================================================

def get_inner_height(height):

    return height - THICKNESS * 2


# =====================================================
# SECTION WIDTH
# =====================================================

def get_section_width(
    width,
    sections
):

    inner_width = get_inner_width(
        width
    )

    partitions = sections - 1

    usable_width = (
        inner_width
        - partitions * THICKNESS
    )

    return usable_width / sections


# =====================================================
# DRAWER WIDTH
# =====================================================

def get_drawer_width(
    opening_width,
    slide_type
):

    rules = get_slide_rules(
        slide_type
    )

    return (
        opening_width
        - rules["side_gap"] * 2
    )


# =====================================================
# DRAWER DEPTH
# =====================================================

def get_drawer_depth(
    cabinet_depth,
    slide_type
):

    rules = get_slide_rules(
        slide_type
    )

    return (
        cabinet_depth
        - rules["rear_gap"]
    )


# =====================================================
# FACADE HEIGHT
# =====================================================

def get_facade_height(
    opening_height,
    drawers_count,
    slide_type
):

    rules = get_slide_rules(
        slide_type
    )

    total_gaps = (

        rules["top_gap"]

        + rules["bottom_gap"]

        + (
            (drawers_count - 1)
            * rules["top_gap"]
        )
    )

    return (
        opening_height
        - total_gaps
    ) / drawers_count


# =====================================================
# DRAWER HEIGHT
# =====================================================

def get_drawer_height(
    facade_height,
    slide_type
):

    rules = get_slide_rules(
        slide_type
    )

    return (
        facade_height
        - rules["inner_top_gap"]
    )