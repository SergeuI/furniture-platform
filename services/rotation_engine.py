# =====================================================
# ROTATION ENGINE
# Система обертання
# =====================================================


# =====================================================
# ОБЕРТАННЯ GEOMETRY
# =====================================================

def rotate_geometry(
    geometry
):

    return {

        "length": geometry.get(
            "width",
            geometry.get("length", 0)
        ),

        "width": geometry.get(
            "length",
            geometry.get("width", 0)
        ),

        "thickness": geometry.get(
            "thickness",
            18
        ),

        "grain": rotate_grain(
            geometry.get(
                "grain",
                geometry.get(
                    "grain_direction",
                    "vertical"
                )
            )
        ),

        "material": geometry.get(
            "material",
            "DSP"
        )
    }
# =====================================================
# ОБЕРТАННЯ ТЕКСТУРИ
# =====================================================

def rotate_grain(
    grain
):

    if grain == "vertical":

        return "horizontal"

    if grain == "horizontal":

        return "vertical"

    return grain


# =====================================================
# ОБЕРТАННЯ EDGE MAP
# =====================================================

def rotate_edge_map(
    edge_map
):

    return {

        "top": edge_map["left"],

        "right": edge_map["top"],

        "bottom": edge_map["right"],

        "left": edge_map["bottom"]
    }


# =====================================================
# ОБЕРТАННЯ ОТВОРІВ
# =====================================================

def rotate_drilling(
    drilling,
    geometry
):

    rotated = []

    length = geometry["length"]

    for hole in drilling:

        rotated.append({

            **hole,

            "x": hole["y"],

            "y": (
                length
                - hole["x"]
            )
        })

    return rotated


# =====================================================
# ОБЕРТАННЯ ДЕТАЛІ
# =====================================================

def rotate_part(
    part
):

    # =========================================
    # ROTATION
    # =========================================

    rotation = part.get(
        "rotation",
        0
    )

    rotation += 90

    if rotation >= 360:

        rotation = 0

    part["rotation"] = rotation

    part["rotated"] = (
        rotation != 0
    )

    # =========================================
    # GEOMETRY
    # =========================================

    if "geometry" in part:

        part["geometry"] = rotate_geometry(
            part["geometry"]
        )

    # =========================================
    # WIDTH / HEIGHT
    # =========================================

    if (
        "width" in part
        and
        "height" in part
    ):

        old_width = part["width"]

        part["width"] = part["height"]

        part["height"] = old_width        

    # =========================================
    # EDGE MAP
    # =========================================

    if "edge_map" in part:

        part["edge_map"] = rotate_edge_map(
            part["edge_map"]
        )

    # =========================================
    # DRILLING
    # =========================================

    if (
        "drilling" in part
        and
        "geometry" in part
    ):

        part["drilling"] = rotate_drilling(

            part["drilling"],

            part["geometry"]
        )

    return part