from aiogram.fsm.context import FSMContext


# =========================================================
# BUILD PROJECT PARAMS
# =========================================================

from aiogram.fsm.context import FSMContext


# =========================================================
# BUILD PROJECT PARAMS
# =========================================================

async def build_project_params(
    state: FSMContext
):

    data = await state.get_data()

    params = {

        # =================================================
        # BASIC
        # =================================================

        "width": data.get("width"),

        "height": data.get("height"),

        "depth": data.get("depth"),

        # =================================================
        # MATERIALS
        # =================================================

        "selected_material": data.get(
            "selected_material"
        ),

        "inside_material": data.get(
            "inside_material"
        ),

        "facade_material": data.get(
            "facade_material"
        ),

        # =================================================
        # CONSTRUCTION
        # =================================================

        "drawers_config": data.get(
            "drawers_config",
            []
        ),

        "doors_count": data.get(
            "doors_count",
            0
        ),

        "shelves_count": data.get(
            "shelves_count",
            0
        ),

        # =================================================
        # FITTINGS
        # =================================================

        "selected_fitting": data.get(
            "selected_fitting"
        ),

        "slide_type": (
            data.get(
                "selected_fitting",
                {}
            ).get(
                "code",
                ""
            ).lower()
        ),

        "bottom_type": data.get(
            "bottom_type"
        ),

        # =================================================
        # USER
        # =================================================

        "city": data.get("city"),

        "user_id": data.get("user_id"),

        # =================================================
        # EXTRA
        # =================================================

        "project_name": data.get(
            "project_name",
            "Без назви"
        ),

        # =================================================
        # SECTIONS
        # =================================================

        "sections": data.get(
            "sections_count",
            1
        ),

        "sections_config": data.get(
            "sections_config",
            []
        ),
    }

    selected_material = data.get(
        "selected_material"
    )

    facade_material = data.get(
        "facade_material"
    )

    inside_material = data.get(
        "inside_material"
    )

    # ==========================================
    # ONE COLOR
    # ==========================================

    if selected_material:

        params["selected_material"] = (
            selected_material
        )

        params["facade_material"] = (
            selected_material
        )

        params["inside_material"] = (
            selected_material
        )

    # ==========================================
    # TWO COLORS
    # ==========================================

    else:

        params["facade_material"] = (
            facade_material
        )

        params["inside_material"] = (
            inside_material
        )

        params["selected_material"] = (
            facade_material
        )

    return params