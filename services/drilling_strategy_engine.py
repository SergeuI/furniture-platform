from services.drilling_engine import (
    create_hole
)


# =====================================================
# DRILLING STRATEGY ENGINE
# Стратегії свердління
# =====================================================


# =====================================================
# CONFIRMAT
# TOP -> SIDE
# =====================================================

def create_confirmat_top_to_side(

    top_part,

    side_part,

    offset=50
):

    top_drilling = []

    side_drilling = []

    top_geometry = top_part[
        "geometry"
    ]

    side_geometry = side_part[
        "geometry"
    ]

    # =================================================
    # TOP PART
    # face drilling
    # =================================================

    top_drilling.append(

        create_hole(

            x=offset,

            y=top_geometry[
                "thickness"
            ] / 2,

            z=0,

            diameter=7,

            depth=top_geometry["thickness"],

            axis="Y",

            face="bottom",

            hole_type="confirmat_face"
        )
    )

    top_drilling.append(

        create_hole(

            x=(
                top_geometry["length"]
                - offset
            ),

            y=top_geometry[
                "thickness"
            ] / 2,

            z=0,

            diameter=7,

            depth=top_geometry["thickness"],

            axis="Y",

            face="bottom",

            hole_type="confirmat_face"
        )
    )

    # =================================================
    # SIDE PART
    # edge drilling
    # =================================================

    side_drilling.append(

        create_hole(

            x=0,
            y=offset,

            z=side_geometry[
                "thickness"
            ] / 2,

            diameter=5,

            depth=side_geometry["thickness"],

            axis="X",

            face="top_edge",

            hole_type="confirmat_edge"
        )
    )

    side_drilling.append(

        create_hole(

            x=0,

            y=(
                side_geometry["length"]
                - offset
            ),

            z=side_geometry[
                "thickness"
            ] / 2,

            diameter=5,

            depth=side_geometry["thickness"],

            axis="X",

            face="top_edge",

            hole_type="confirmat_edge"
        )
    )

    def normalize_float(value):

          return round(float(value), 3)

    unique = []

    seen = set()

    for hole in side_drilling:

        

        key = (
            normalize_float(hole["x"]),
            normalize_float(hole["y"]),
            normalize_float(hole["z"]),

            hole.get("diameter"),
            hole.get("depth"),

            hole.get("axis"),
            hole.get("face"),

            hole.get("hole_type"),

            hole.get("part"),
            hole.get("operation")
        )

        if key not in seen:

            seen.add(key)

            unique.append(hole)

    side_drilling = unique


    return {

        "parent_drilling": top_drilling,

        "child_drilling": side_drilling
    }