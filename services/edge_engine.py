# =====================================================
# EDGE ENGINE
# Система крайки
# =====================================================


# =====================================================
# СТВОРЕННЯ КАРТИ КРАЙКИ
# =====================================================

def create_edge_map(

    top=None,
    bottom=None,
    left=None,
    right=None
):

    return {

        "top": top,

        "bottom": bottom,

        "left": left,

        "right": right
    }


# =====================================================
# ДОДАТИ КРАЙКУ ДО ДЕТАЛІ
# =====================================================

def apply_edge_map(
    part,
    edge_map
):

    part["edge_map"] = edge_map

    part["edges"] = edge_map

    return part


# =====================================================
# ОБЕРТАННЯ КРАЙКИ
# =====================================================



# =====================================================
# ПІДРАХУНОК КРАЙКИ
# =====================================================

def calculate_edge_length(
    geometry,
    edge_map
):

    result = {

        "0.4": 0,

        "0.8": 0,

        "2.0": 0
    }

    length = geometry["length"]

    width = geometry["width"]

    # Верх
    if edge_map["top"]:

        result[
            edge_map["top"]
        ] += length

    # Низ
    if edge_map["bottom"]:

        result[
            edge_map["bottom"]
        ] += length

    # Ліво
    if edge_map["left"]:

        result[
            edge_map["left"]
        ] += width

    # Право
    if edge_map["right"]:

        result[
            edge_map["right"]
        ] += width

    return result