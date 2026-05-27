import copy


# =====================================================
# PART REGISTRY ENGINE
# Реєстр деталей
# =====================================================


# =====================================================
# CREATE REGISTRY
# =====================================================

def create_part_registry():

    return {

        "parts": {}
    }


# =====================================================
# REGISTER PART
# =====================================================

def register_part(

    registry,

    part
):

    if "id" not in part:

        raise ValueError(
            "Part must have id"
        )

    registry["parts"][
        part["id"]
    ] = copy.deepcopy(part)

    return registry


# =====================================================
# UPDATE PART
# =====================================================

def update_part(

    registry,

    part
):

    if "id" not in part:

        raise ValueError(
            "Part must have id"
        )

    registry["parts"][
        part["id"]
    ] = copy.deepcopy(part)

    return registry


# =====================================================
# GET PART
# =====================================================

def get_part(

    registry,

    part_id
):

    return registry[
        "parts"
    ].get(part_id)


# =====================================================
# GET ALL PARTS
# =====================================================

def get_all_parts(
    registry
):

    return list(

        registry[
            "parts"
        ].values()
    )