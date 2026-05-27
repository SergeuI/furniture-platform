from services.geometry_engine import (
    get_section_width,
    get_drawer_depth,
    get_facade_height,
    get_drawer_height
)

from services.gap_engine import (
    get_movento_side_gap,
    get_tandem_side_gap,
    get_facade_gap,
    get_facade_overlay
)

from services.drawer_bottom_engine import (

    calculate_dsp_bottom,

    calculate_hdf_bottom,

    calculate_telescopic_hdf_bottom,
    calculate_tandem_hdf_bottom,
    calculate_movento_dsp_bottom,
    calculate_movento_hdf_bottom
)

from services.groove_engine import (

    create_hdf_bottom_groove,

    create_dsp_bottom_groove,

    
)
from services.drawer_geometry_engine import (

    calculate_back_height,

    calculate_front_height,

    calculate_bottom_inner_width,

    calculate_bottom_inner_depth
)
from services.drawer_front_engine import (

    create_inner_front,

    create_outer_facade
)
from services.overlay_engine import (

    calculate_inset_facade,

    calculate_full_overlay_facade,

    calculate_half_overlay_facade
)
from services.facade_position_engine import (

    calculate_inset_position,

    calculate_full_overlay_position,

    calculate_half_overlay_position
)
from services.facade_drilling_engine import (

    create_handle_drilling,

    create_tipon_drilling,

    create_front_fixing_drilling
)
from services.facade_transform_engine import (
    transform_facade_drilling
)
from services.nesting_engine import (
    build_simple_nesting
)
from services.production_tracking_engine import (
    apply_tracking
)
from models.geometry_model import (
    PartGeometry
)
from models.facade_model import (
    FacadeModel
)
import uuid
# =====================================================
# GENERATE DRAWERS
# =====================================================

def generate_drawers(data):

    params = data

    # =================================================
    # ОСНОВНІ ПАРАМЕТРИ
    # =================================================

    width = params.get("width")

    depth = params.get("depth")

    height = params.get("height")

    sections = params.get(
        "sections",
        1
    )

    drawers_config = params.get(
        "drawers_config",
        []
    )

    slide_type = params.get(
        "slide_type",
        "tandem"
    )

    if "movento" in slide_type:

        slide_type = "movento"

    elif "tandem" in slide_type:

        slide_type = "tandem"

    elif "telescopic" in slide_type:

        slide_type = "telescopic"


    bottom_type = params.get(
        "bottom_type",
        "hdf_3"
    )

    print("\n========== DRAWER DEBUG ==========")
    print("SLIDE TYPE =", slide_type)
    print("BOTTOM TYPE =", bottom_type)
    print("==================================\n")

    facade_type = params.get(
        "facade_type",
        "inset"
    )

    handle_type = params.get(
        "handle_type",
        "handle"
    )
    # =================================================
    # ПАЗ
    # =================================================

    if bottom_type in ["dsp", "dsp_18"]:

        groove = (
            create_dsp_bottom_groove()
        )

    else:

        groove = (
            create_hdf_bottom_groove()
        )

    # =================================================
    # РЕЗУЛЬТАТ
    # =================================================

    details = []

    # =================================================
    # ВНУТРІШНЯ ШИРИНА СЕКЦІЇ
    # =================================================

    inner_width = get_section_width(
        width,
        sections
    )

    # =================================================
    # БОКОВІ ЗАЗОРИ
    # =================================================

    if slide_type == "movento":

        drawer_gap = (
            get_movento_side_gap() * 2
        )

    else:

        drawer_gap = (
            get_tandem_side_gap() * 2
        )

    # =================================================
    # ШИРИНА ШУХЛЯДИ
    # =================================================

    drawer_width = int(

        inner_width
        - drawer_gap
    )

    # =================================================
    # ГЛИБИНА ШУХЛЯДИ
    # =================================================

    drawer_depth = int(

        get_drawer_depth(
            depth,
            slide_type
        )
    )

    # =================================================
    # СЕКЦІЇ
    # =================================================

    for section_index, drawers_count in enumerate(
        drawers_config
    ):

        # =============================================
        # ВИСОТА ФАСАДУ
        # =============================================

        facade_height = int(

            get_facade_height(

                height,

                drawers_count,

                slide_type
            )
        )
        opening_width = int(
            inner_width
        )

        opening_height = int(
            height / drawers_count
        )
        # =============================================
        # ВИСОТА КОРОБА
        # =============================================

        drawer_height = int(

            get_drawer_height(

                facade_height,

                slide_type
            )
        )

        front_height = int(

            calculate_front_height(

                drawer_height,

                groove
            )
        )

        back_height = int(

            calculate_back_height(

                drawer_height,

                groove
            )
        )

        if bottom_type == "dsp_18":

            back_height -= 15

        # =============================================
        # ШУХЛЯДИ
        # =============================================

        for i in range(drawers_count):

            drawer_name = (
                f"S{section_index+1}-{i+1}"
            )

            # =========================================
            # ДНО
            # =========================================

            if slide_type == "movento":

                if bottom_type in ["hdf", "hdf_3"]:

                    bottom = calculate_movento_hdf_bottom(

                        calculate_bottom_inner_width(
                            drawer_width,
                            groove
                        ),

                        calculate_bottom_inner_depth(
                            drawer_depth,
                            groove
                        )
                    )

                else:

                    bottom = calculate_movento_dsp_bottom(

                        drawer_width - 36,

                        drawer_depth - 4
                    )

                bottom["quarter"] = {

                    "enabled": True,

                    "depth": 12,

                    "height": 2
                }    

                bottom["machining"] = [

                    {
                        "type": "quarter",

                        "depth": 12,

                        "height": 2,

                        "side": "left_side"
                    },

                    {
                        "type": "quarter",

                        "depth": 12,

                        "height": 2,

                        "side": "right_side"
                    }
                ]

            elif slide_type == "telescopic":

                if bottom_type in ["dsp", "dsp_18"]:

                    bottom = calculate_dsp_bottom(

                        calculate_bottom_inner_width(
                            drawer_width,
                            groove
                        ),

                        calculate_bottom_inner_depth(
                            drawer_depth,
                            groove
                        )
                    )

                else:

                    bottom = calculate_telescopic_hdf_bottom(

                        calculate_bottom_inner_width(
                            drawer_width,
                            groove
                        ),

                        calculate_bottom_inner_depth(
                            drawer_depth,
                            groove
                        )
                    )

            elif slide_type == "tandem":

                if bottom_type in ["dsp", "dsp_18"]:

                    bottom = calculate_dsp_bottom(

                        calculate_bottom_inner_width(
                            drawer_width,
                            groove
                        ),

                        calculate_bottom_inner_depth(
                            drawer_depth,
                            groove
                        )
                    )

                else:

                    bottom = calculate_tandem_hdf_bottom(

                        calculate_bottom_inner_width(
                            drawer_width,
                            groove
                        ),

                        calculate_bottom_inner_depth(
                            drawer_depth,
                            groove
                        )
                    )
            # =========================================
            # ЛІВА БОКОВИНА
            # =========================================

            part = PartGeometry(

                name=f"{drawer_name} ліва боковина",

                width=drawer_depth,

                height=drawer_height,

                thickness=18,
                material="dsp_18",

                qty=1,

                metadata={

                    "quarter": (

                        bottom.get("quarter")

                        if slide_type == "movento"

                        else None
                    ),

                    "machining": (

                        bottom.get("machining", [])

                        if slide_type == "movento"

                        else []
                    )
                },
            )

            details.append(
                part.to_dict()
            )

            # =========================================
            # ПРАВА БОКОВИНА
            # =========================================

            part = PartGeometry(

                name=f"{drawer_name} права боковина",

                width=drawer_depth,

                height=drawer_height,

                thickness=18,
                material="dsp_18",

                qty=1,

                metadata={

                    "quarter": (

                        bottom.get("quarter")

                        if slide_type == "movento"

                        else None
                    ),

                    "machining": (

                        bottom.get("machining", [])

                        if slide_type == "movento"

                        else []
                    )
                },
            )

            details.append(
                part.to_dict()
            )

            # =========================================
            # ПЕРЕД
            # =========================================

            # =========================================
            # ВНУТРІШНІЙ ПЕРЕД
            # =========================================

            inner_front = create_inner_front(

                drawer_width,

                front_height
            )

            part = PartGeometry(

                name=f"{drawer_name} внутрішній перед",

                width=inner_front["width"],

                height=inner_front["height"],

                thickness=18,
                material="dsp_18",

                qty=1
            )

            details.append(
                part.to_dict()
            )


            # =========================================
            # ЗОВНІШНІЙ ФАСАД
            # =========================================

            

            facade_gaps = (
                get_facade_gap()
            )

            overlay = (
                get_facade_overlay()
            )

            if facade_type == "inset":

                facade_geometry = (
                    calculate_inset_facade(

                        opening_width,

                        opening_height,

                        facade_gaps
                    )
                )

                facade_position = (
                    calculate_inset_position()
                )

            elif facade_type == "half_overlay":

                facade_geometry = (
                    calculate_half_overlay_facade(

                        opening_width,

                        opening_height,

                        overlay
                    )
                )

                facade_position = (
                    calculate_half_overlay_position()
                )

            else:

                facade_geometry = (
                    calculate_full_overlay_facade(

                        opening_width,

                        opening_height,

                        overlay
                    )
                )

                facade_position = (
                    calculate_full_overlay_position()
                )

            # =============================================
            # DRILLING
            # =============================================

            if handle_type == "tipon":

                facade_drilling = (
                    create_tipon_drilling()
                )

            else:

                facade_drilling = (
                    create_handle_drilling(

                        facade_geometry[
                            "width"
                        ],

                        facade_geometry[
                            "height"
                        ]
                    )
                )

            front_fixing = (
                create_front_fixing_drilling(

                    facade_geometry[
                        "width"
                    ],

                    facade_geometry[
                        "height"
                    ]
                )
            )

            facade_drilling.extend(
                front_fixing
            )

            outer_facade = create_outer_facade(

                facade_geometry[
                    "width"
                ],

                facade_geometry[
                    "height"
                ]
            )

            
            facade_part = FacadeModel(

                name=(
                    f"Шухляда {drawer_name} фасад"
                ),

                width=outer_facade[
                    "width"
                ],

                height=outer_facade[
                    "height"
                ],

                thickness=18,

                facade_type=facade_geometry[
                    "type"
                ],

                system=slide_type,

                qty=1,

                drilling=facade_drilling,

                position=facade_position
            ).to_dict()

            facade_part = (
                transform_facade_drilling(
                    facade_part
                )
            )

            facade_part["edges"] = {

                "top": "0.8",

                "bottom": "0.8",

                "left": "0.8",

                "right": "0.8"
            }

            facade_part["id"] = str(uuid.uuid4())

            details.append(
                facade_part
            )

      

            # =========================================
            # ЗАД
            # =========================================

            back_width = drawer_width

            if slide_type == "movento":

                back_width -= 36

            part = PartGeometry(

                name=f"{drawer_name} зад",

                width=back_width,

                height=back_height,

                thickness=18,
                material="dsp_18",

                qty=1
            )

            details.append(
                part.to_dict()
            )

            # =========================================
            # ДНО
            # =========================================

            part = PartGeometry(

                name=f"{drawer_name} дно",

                width=bottom["width"],

                height=bottom["depth"],

                thickness=bottom["thickness"],

                material=bottom["type"],

                qty=1,

                metadata={

                    "bottom_offset":
                        bottom.get("bottom_offset", 12),

                }
                )

            details.append(
                part.to_dict()
            )

          

    details = apply_tracking(
        details
    )

    # =========================================
    # FORCE ID FOR ALL PARTS
    # =========================================

    for item in details:

        if "id" not in item:

            item["id"] = str(uuid.uuid4())


    # =========================================
    # DEBUG PART IDS
    # =========================================

    for i, item in enumerate(details):

        if not isinstance(item, dict):

            print("\nINVALID TYPE:")
            print(type(item))
            print(item)

            continue

        if "id" not in item:

            print("\nMISSING ID:")
            print(f"INDEX: {i}")
            print(item)

        else:

            print(
                f"OK ID: {item['id']} | "
                f"{item.get('name')}"
            )


    nesting_result = (
        build_simple_nesting(
            details
        )
    )

    optimized_details = details

    if (
        isinstance(
            nesting_result["nesting"],
            list
        )
    ):

        collected_parts = []

        for nesting_group in nesting_result[
            "nesting"
        ]:

            if isinstance(
                nesting_group,
                dict
            ):

                collected_parts.extend(
                    nesting_group.get(
                        "parts",
                        []
                    )
                )

        if collected_parts:

            optimized_details = (
                collected_parts
            )

    return {

        "details": optimized_details,

        "nesting": nesting_result[
            "nesting"
        ],

        "cutting_maps": nesting_result[
            "cutting_maps"
        ]
    }