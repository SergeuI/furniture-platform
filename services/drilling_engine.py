import copy


# =====================================================
# DRILLING ENGINE
# Система свердління
# =====================================================

from services.plane_transform_engine import (
    get_plane_normal
)
from core.machining.drilling import (

    build_confirmat_positions,

    calculate_panel_center
)
# =====================================================
# СТВОРЕННЯ ОТВОРУ
# =====================================================

def create_hole(

    x,
    y,
    z,

    diameter,
    depth,

    axis="Z",

    face="front",

    hole_type="confirmat"
):

    return {

        # Координати
        "x": round(x, 2),

        "y": round(y, 2),

        "z": round(z, 2),

        # Геометрія
        "diameter": diameter,

        "depth": depth,

        # Вісь свердління
        "axis": axis,

        # Площина
        "face": face,

        # Тип отвору
        "type": hole_type
    }

# =====================================================
# VALIDATE HOLE POSITION
# Перевірка координат свердління
# =====================================================

def validate_hole(part, hole):

    width = part.get("width", 0)
    height = part.get("height", 0)

    x = hole.get("x", 0)
    y = hole.get("y", 0)

    if x < 0 or x > width:

        raise ValueError(

            f"Hole X out of bounds: {x} > {width} | part: {part.get('name')}"
        )

    if y < 0 or y > height:

        raise ValueError(

            f"Hole Y out of bounds: {y} > {height} | part: {part.get('name')}"
        )
# =====================================================
# ДОДАТИ СВЕРДЛІННЯ ДО ДЕТАЛІ
# =====================================================

def apply_drilling(

    part,
    holes
):

    updated_part = copy.deepcopy(
        part
    )

    if "drilling" not in updated_part:

        updated_part["drilling"] = []

    for hole in holes:

        validate_hole(
            updated_part,
            hole
        )

    updated_part["drilling"].extend(
        copy.deepcopy(holes)
    )

    return updated_part


# =====================================================
# CONFIRMAT
# =====================================================

def create_confirmat_drilling(

    length,
    thickness,

    offset=50,

    diameter=5,

    depth=50
):

    holes = []

    positions = build_confirmat_positions(

    length=length,

    offset=offset
)

    # Верхній отвір
    holes.append(

        create_hole(

            x=positions[0],

            y=thickness / 2,

            z=0,

            diameter=diameter,

            depth=depth,

            axis=get_plane_normal("XZ"),

            face="edge",

            hole_type="confirmat"
        )
    )

    # Нижній отвір
    holes.append(

        create_hole(

            x=positions[1],

            y=thickness / 2,

            z=0,

            diameter=diameter,

            depth=depth,

            axis=get_plane_normal("XZ"),

            face="edge",

            hole_type="confirmat"
        )
    )

    return holes


# =====================================================
# MINIFIX
# =====================================================

def create_minifix_drilling(

    length,
    thickness,

    offset=34
):

    holes = []

    holes.append(

        create_hole(

            x=offset,

            y=thickness / 2,

            z=0,

            diameter=15,

            depth=12,

            axis="Z",

            face="front",

            hole_type="minifix"
        )
    )

    holes.append(

        create_hole(

            x=length - offset,

            y=thickness / 2,

            z=0,

            diameter=15,

            depth=12,

            axis="Z",

            face="front",

            hole_type="minifix"
        )
    )

    return holes



# =====================================================
# SINGLE CONFIRMAT
# =====================================================



def create_single_confirmat(

    x,
    thickness,

    diameter=5,
    depth=50
):

    return [

        create_hole(

            x=x,

            y=thickness / 2,

            z=0,

            diameter=diameter,

            depth=depth,

            axis=get_plane_normal("XZ"),

            face="edge",

            hole_type="confirmat"
        )
    ]