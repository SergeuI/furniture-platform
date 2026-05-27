import uuid


# =====================================================
# JOINT ENGINE
# Система з'єднань
# =====================================================


# =====================================================
# ID
# =====================================================

def create_joint_id():

    return str(
        uuid.uuid4()
    )


# =====================================================
# СТВОРЕННЯ JOINT
# =====================================================

def create_joint(

    joint_type,

    parent_part,

    child_part,

    hardware=None
):

    return {

        "id": create_joint_id(),

        # Тип
        "type": joint_type,

        # Основна деталь
        "parent": parent_part,

        # Приєднувана деталь
        "child": child_part,

        # Hardware
        "hardware": hardware,

        # Drilling
        "drilling": []
    }


# =====================================================
# ДОДАТИ СВЕРДЛІННЯ
# =====================================================

def add_joint_drilling(

    joint,

    drilling
):

    joint["drilling"].extend(
        drilling
    )

    return joint


# =====================================================
# CONFIRMAT JOINT
# =====================================================

def create_confirmat_joint(

    parent_part,

    child_part
):

    return create_joint(

        joint_type="confirmat",

        parent_part=parent_part,

        child_part=child_part,

        hardware={

            "name": "Confirmat 7x50",

            "diameter": 7,

            "length": 50
        }
    )


# =====================================================
# MINIFIX JOINT
# =====================================================

def create_minifix_joint(

    parent_part,

    child_part
):

    return create_joint(

        joint_type="minifix",

        parent_part=parent_part,

        child_part=child_part,

        hardware={

            "name": "Minifix",

            "diameter": 15
        }
    )