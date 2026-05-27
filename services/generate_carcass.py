from services.connections_logic import (calculate_connections)
from services.carcass_config import (CARCASS_CONFIG)
from services.coordinate_engine import (
    add_part_coordinates,
    get_left_side_position,
    get_right_side_position,
    get_bottom_position,
    get_top_position
)
from services.part_geometry_engine import (
    create_part_geometry,
    apply_geometry,
    vertical_grain,
    horizontal_grain
)
from services.edge_engine import (
    apply_edge_map, 
    create_edge_map
)
from services.drilling_engine import (
    apply_drilling,
    create_confirmat_drilling,
    create_single_confirmat
)
from services.local_coordinate_engine import (create_local_coordinate_system, apply_local_coordinates)
from services.visibility_engine import (create_visible_edge_map)
from services.cabinet_context_engine import (create_cabinet_context)
from services.assembly_engine import (create_cabinet_assembly, add_part_to_assembly)
from services.joint_engine import (create_confirmat_joint, add_joint_drilling)
from services.machining_transform_engine import (
    transform_part_drilling
)

from services.part_registry_engine import (

    create_part_registry,

    register_part,

    update_part,

    get_all_parts
)
import uuid


THICKNESS = 18


# =====================================================
# GENERATE CARCASS
# =====================================================

def generate_carcass(data):

    params = data

    width = params.get("width")
    height = params.get("height")
    socle_height = CARCASS_CONFIG["socle_height"]

    body_height = (
        height - socle_height
    )
    depth = params.get("depth")
    
    

    sections = params.get("sections", 1)

    part_registry = (
        create_part_registry()
    )

    cabinet_assembly = (
        create_cabinet_assembly()
    )

    context = create_cabinet_context()

    connections = []

    joints = []
    # =====================================================
    # З'ЄДНАННЯ КРИШКА -> БОКИ
    # =====================================================

    connections.append(

        calculate_connections(

            joint_length=depth,

            connection_type="confirmat"
        )
    )

    connections.append(

        calculate_connections(

            joint_length=depth,

            connection_type="confirmat"
        )
    )

    # =====================================================
    # З'ЄДНАННЯ ДНО -> БОКИ
    # =====================================================

    connections.append(

        calculate_connections(

            joint_length=depth,

            connection_type="confirmat"
        )
    )

    connections.append(

        calculate_connections(

            joint_length=depth,

            connection_type="confirmat"
        )
    )

    # =================================================
    # ВНУТРІШНЯ ШИРИНА
    # =================================================

    inner_width = width - (THICKNESS * 2)

   
    # =================================================
    # БОК ЛІВИЙ
    # =================================================

    left_side = {

        "id": str(uuid.uuid4()),

        "type": "side",

        "name": "Бок лівий",

        "width": depth,

        "height": body_height,

        "qty": 1,

       
    }

    left_pos = get_left_side_position()

    left_side = add_part_coordinates(

        left_side,

        x=left_pos["x"],

        y=left_pos["y"],

        z=left_pos["z"],

        rotation=0,

        # YZ:
        # Y -> висота
        # Z -> глибина
        # X -> товщина

        plane="YZ"
    )

    from services.edge_engine import (
        create_edge_map
    )

    left_edges = create_edge_map(

        top="0.4",

        bottom="0.4",

        left="0.8",

        right=None
    )



    left_side = apply_edge_map(
        left_side,
        left_edges
    )

    left_geometry = create_part_geometry(

        length=body_height,

        width=depth,

        thickness=THICKNESS,

        grain=vertical_grain()
    )

    left_side = apply_geometry(
        left_side,
        left_geometry
    )

    left_local = create_local_coordinate_system()

    left_side = apply_local_coordinates(
        left_side,
        left_local
    )



    part_registry = register_part(

        part_registry,

        left_side
    )

    cabinet_assembly = add_part_to_assembly(

        cabinet_assembly,

        left_side
    )
    # =================================================
    # БОК ПРАВИЙ
    # =================================================

    right_side = {

        "id": str(uuid.uuid4()),

        "type": "side",

        "name": "Бок правий",

        "width": depth,

        "height": body_height,

        "qty": 1,

       
    }

    right_pos = get_right_side_position(
        width,
        THICKNESS
    )

    right_side = add_part_coordinates(

        right_side,

        x=right_pos["x"],

        y=right_pos["y"],

        z=right_pos["z"],

        rotation=0,

        # YZ:
        # Y -> висота
        # Z -> глибина
        # X -> товщина

        plane="YZ"
    )

    right_edges = create_edge_map(

        top="0.4",

        bottom="0.4",

        left=None,

        right="0.8"
    )

    right_side = apply_edge_map(
        right_side,
        right_edges
    )


    right_geometry = create_part_geometry(

        length=body_height,

        width=depth,

        thickness=THICKNESS,

        grain=vertical_grain()
    )

    right_side = apply_geometry(
        right_side,
        right_geometry
    )

    right_local = create_local_coordinate_system()

    right_side = apply_local_coordinates(
        right_side,
        right_local
    )

 

    part_registry = register_part(

        part_registry,

        right_side
    )

    cabinet_assembly = add_part_to_assembly(

        cabinet_assembly,

        right_side
    )
    # =================================================
    # ДНО
    # =================================================

    bottom = {

        "id": str(uuid.uuid4()),

        "type": "bottom",

        "name": "Дно",

        "width": inner_width,

        "height": depth,

        "qty": 1,

       
    }

    bottom_pos = get_bottom_position(
        THICKNESS
    )

    bottom = add_part_coordinates(

        bottom,

        x=bottom_pos["x"],

        y=bottom_pos["y"],

        z=bottom_pos["z"],

        rotation=0,

        # XZ:
        # X -> ширина
        # Z -> глибина
        # Y -> товщина

        plane="XZ"
    )

    bottom_edges = create_edge_map(

        top="0.8",

        bottom="0.4",

        left="0.4",

        right="0.4"
    )

    bottom = apply_edge_map(
        bottom,
        bottom_edges
    )


    bottom_geometry = create_part_geometry(

        length=inner_width,

        width=depth,

        thickness=THICKNESS,

        grain=horizontal_grain()
    )

    bottom = apply_geometry(
        bottom,
        bottom_geometry
    )

    bottom_left_holes = create_single_confirmat(

        x=50,

        thickness=THICKNESS
    )


    bottom_left_joint = create_confirmat_joint(

        parent_part=bottom,

        child_part=left_side
    )

    bottom_left_joint = add_joint_drilling(

        bottom_left_joint,

        bottom_left_holes
    )

    joints.append(
        bottom_left_joint
    )

    bottom_right_holes = create_single_confirmat(

        x=bottom["width"] - 50,

        thickness=THICKNESS
    )


    bottom_right_joint = create_confirmat_joint(

        parent_part=bottom,

        child_part=right_side
    )

    bottom_right_joint = add_joint_drilling(

        bottom_right_joint,

        bottom_right_holes
    )

    joints.append(
        bottom_right_joint
    )

    bottom = apply_drilling(
        bottom,
        bottom_left_holes
    )

    bottom = apply_drilling(
        bottom,
        bottom_right_holes
    )



    bottom_local = create_local_coordinate_system()

    bottom = apply_local_coordinates(
        bottom,
        bottom_local
    )

    bottom = transform_part_drilling(
        bottom
    )

    part_registry = update_part(

        part_registry,

        bottom
    )

    part_registry = register_part(

        part_registry,

        bottom
    )

    cabinet_assembly = add_part_to_assembly(

        cabinet_assembly,

        bottom
    )
    # =================================================
    # КРИШКА
    # =================================================

    top = {

        "id": str(uuid.uuid4()),

        "type": "top",

        "name": "Кришка",

        "width": inner_width,

        "height": depth,

        "qty": 1,

       
    }

    top_pos = get_top_position(
        body_height,
        THICKNESS
    )

    top = add_part_coordinates(

        top,

        x=top_pos["x"],

        y=top_pos["y"],

        z=top_pos["z"],

        rotation=0,

        # XZ:
        # X -> ширина
        # Z -> глибина
        # Y -> товщина

        plane="XZ"
    )

    top_edges = create_edge_map(

        top="0.8",

        bottom="0.4",

        left="0.4",

        right="0.4"
    )

    top = apply_edge_map(
        top,
        top_edges
    )



    top_geometry = create_part_geometry(

        length=inner_width,

        width=depth,

        thickness=THICKNESS,

        grain=horizontal_grain()
    )

    top = apply_geometry(
        top,
        top_geometry
    )

    # =================================================
    # TOP -> LEFT SIDE
    # =================================================

    top_left_holes = create_single_confirmat(

        x=50,

        thickness=THICKNESS,

        diameter=7,

        depth=18
    )

    top = apply_drilling(

        top,

        top_left_holes
    )

    # =================================================
    # TOP -> RIGHT SIDE
    # =================================================

    top_right_holes = create_single_confirmat(

        x=top["width"] - 50,

        thickness=THICKNESS,

        diameter=7,

        depth=18
    )

    top = apply_drilling(

        top,

        top_right_holes
    )


    top_left_joint = create_confirmat_joint(

        parent_part=top,

        child_part=left_side
    )

    top_left_joint = add_joint_drilling(

        top_left_joint,

        top_left_holes
    )

    joints.append(
        top_left_joint
    )


    top_right_joint = create_confirmat_joint(

        parent_part=top,

        child_part=right_side
    )

    top_right_joint = add_joint_drilling(

        top_right_joint,

        top_right_holes
    )

    joints.append(
        top_right_joint
    )


    # top = rotate_part(
    #     top
    # )

    top_local = create_local_coordinate_system()

    top = apply_local_coordinates(
        top,
        top_local
    )

    top = transform_part_drilling(
        top
    )

    part_registry = update_part(

        part_registry,

        top
    )

    part_registry = register_part(

        part_registry,

        top
    )

    cabinet_assembly = add_part_to_assembly(

        cabinet_assembly,

        top
    )

    # =================================================
    # ПЕРЕГОРОДКИ
    # =================================================

# =================================================
# ПЕРЕГОРОДКИ
# =================================================

    for i in range(sections - 1):

        divider = {

            "id": f"divider_{i}",

            "type": "divider",

            "name": f"Перегородка {i+1}",

            "width": depth,

            "height": body_height - (THICKNESS * 2),

            "qty": 1
        }

        part_registry = register_part(

            part_registry,

            divider
        )

        cabinet_assembly = add_part_to_assembly(

            cabinet_assembly,

            divider
        )
    # =================================================
    # Передня планка цоколя
    # =================================================

    front_socle = {

        "id": "front_socle",

        "type": "socle",

        "name": "Цоколь перед",

        "width": width - 36,

        "height": socle_height,

        "qty": 1
    }

    part_registry = register_part(

        part_registry,

        front_socle
    )

    cabinet_assembly = add_part_to_assembly(

        cabinet_assembly,

        front_socle
    )

    # =================================================
    # Задня планка цоколь
    # =================================================    

    rear_socle = {

        "id": "rear_socle",

        "type": "socle",

        "name": "Цоколь зад",

        "width": width - 36,

        "height": socle_height,

        "qty": 1
    }

    part_registry = register_part(

        part_registry,

        rear_socle
    )

    cabinet_assembly = add_part_to_assembly(

        cabinet_assembly,

        rear_socle
    )

    # =================================================
    # ЗАДНЯ СТІНКА HDF
    # =================================================

    back_wall = {

        "id": str(uuid.uuid4()),

        "type": "back_wall",

        "name": "Задня стінка ДВП",

        "width": width - 4,

        "height": body_height - 4,

        "qty": 1,

        "material": "hdf_3"
    }

    back_wall_geometry = create_part_geometry(

        length=width - 4,

        width=body_height - 4,

        thickness=3,

        grain=vertical_grain(),

        material="hdf_3"
    )

    back_wall = apply_geometry(

        back_wall,

        back_wall_geometry
    )

    part_registry = register_part(

        part_registry,

        back_wall
    )

    cabinet_assembly = add_part_to_assembly(

        cabinet_assembly,

        back_wall
    )

    return {

        "details": get_all_parts(
            part_registry
        ),

        "connections": connections,

        "assembly": cabinet_assembly,

        "joints": joints
    }


