from services.get_slide_rules import (
    get_slide_rules
)
from services.cabinet_opening_engine import (
    get_section_opening_width,
    get_cabinet_opening_height
)

from services.gap_engine import (
    get_facade_gap
)

# =====================================================
# OPENING WIDTH
# =====================================================


# =====================================================
# OPENING HEIGHT
# =====================================================



# =====================================================
# INSET FACADE WIDTH
# =====================================================

def get_inset_facade_width(
    section_opening_width,
    slide_type
):

    rules = get_slide_rules(
        slide_type
    )
    gaps = get_facade_gap()
    return (

        section_opening_width

        - gaps["left"]

        - gaps["right"]
    )


# =====================================================
# INSET FACADE HEIGHT
# =====================================================

def get_inset_facade_height(
    cabinet_opening_height,
    drawers_count,
    slide_type
):

    rules = get_slide_rules(
        slide_type
    )
    gaps = get_facade_gap()
    total_gaps = (

        gaps["top"]

        + gaps["bottom"]

        + (
            (drawers_count - 1)
            * gaps["between_facades"]
        )
    )
    return (
        cabinet_opening_height
        - total_gaps
    ) / drawers_count


# =====================================================
# OVERLAY FACADE WIDTH
# =====================================================

def get_overlay_facade_width(
    opening_width,
    reveal=2
):

    return (
        opening_width
        + reveal * 2
    )


# =====================================================
# OVERLAY FACADE HEIGHT
# =====================================================

def get_overlay_facade_height(
    opening_height,
    drawers_count,
    reveal=2
):

    total_reveal = (
        (drawers_count + 1)
        * reveal
    )

    return (
        opening_height
        - total_reveal
    ) / drawers_count