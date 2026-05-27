import uuid


# =====================================================
# ASSEMBLY ENGINE
# Система збірок
# =====================================================


# =====================================================
# ID
# =====================================================

def create_id():

    return str(
        uuid.uuid4()
    )


# =====================================================
# СТВОРЕННЯ ASSEMBLY
# =====================================================

VALID_ASSEMBLY_TYPES = {

    "cabinet",

    "drawer",

    "section",

    "module"
}


def create_assembly(

    name,

    assembly_type
):

    if assembly_type not in VALID_ASSEMBLY_TYPES:

        raise ValueError(

            f"Invalid assembly type: "
            f"{assembly_type}"
        )

    return {

        "id": create_id(),

        "name": name,

        "type": assembly_type,

        "children": [],

        "origin": {

            "x": 0,
            "y": 0,
            "z": 0
        },

        "axis": {

            "x": [1, 0, 0],

            "y": [0, 1, 0],

            "z": [0, 0, 1]
        }
    }


# =====================================================
# ДОДАТИ ДЕТАЛЬ В ASSEMBLY
# =====================================================

def add_part_to_assembly(

    assembly,

    part
):

    if not isinstance(

        part,

        dict
    ):

        raise ValueError(

            "Part must be dict"
        )

    if "id" not in part:

        part["id"] = create_id()

    existing_ids = {

        child.get("part_id")

        for child in assembly["children"]

        if isinstance(child, dict)
    }

    if part["id"] in existing_ids:

        return assembly

    assembly["children"].append({

        "part_id": part["id"],

        "name": part.get("name"),

        "type": part.get("type"),

        "qty": part.get("qty", 1),

        "position": part.get("position"),

        "rotation": part.get("rotation"),

        "plane": part.get("plane"),

        "connections": []
    })

    return assembly
# =====================================================
# ДОДАТИ SUB-ASSEMBLY
# =====================================================

def add_subassembly(

    assembly,

    subassembly
):

    if not isinstance(

        subassembly,

        dict
    ):

        raise ValueError(

            "Subassembly must be dict"
        )

    if "id" not in subassembly:

        raise ValueError(

            "Subassembly missing id"
        )

    assembly["children"].append(
        subassembly
    )

    return assembly


# =====================================================
# ROOT CABINET
# =====================================================

def create_cabinet_assembly():

    return create_assembly(
        "Корпус",
        "cabinet"
    )


# =====================================================
# DRAWER ASSEMBLY
# =====================================================

def create_drawer_assembly(
        
    drawer_index
):

    return create_assembly(

        f"Шухляда {drawer_index}",

        "drawer"
    )


def build_global_drilling(

    part
):

    global_drilling = []

    position = part.get(
        "position",
        {}
    )

    pos_x = position.get(
        "x",
        0
    )

    pos_y = position.get(
        "y",
        0
    )

    pos_z = position.get(
        "z",
        0
    )

    for hole in part.get(
        "drilling",
        []
    ):

        global_hole = hole.copy()

        global_hole[
            "global_position"
        ] = {

            "x": hole.get(
                "x",
                0
            ) + pos_x,

            "y": hole.get(
                "y",
                0
            ) + pos_y,

            "z": hole.get(
                "z",
                0
            ) + pos_z
        }

        global_drilling.append(
            global_hole
        )

    return global_drilling