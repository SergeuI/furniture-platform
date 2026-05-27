from aiogram.fsm.context import FSMContext

from schemas.project_input import (

    ProjectInputSchema,

    DimensionsSchema,

    SectionsSchema,

    DrawersSchema,

    MaterialsSchema,

    FittingsSchema
)


# =====================================================
# BUILD PROJECT INPUT
# =====================================================

async def build_project_input(
    state: FSMContext
) -> ProjectInputSchema:

    data = await state.get_data()

    # =================================================
    # DIMENSIONS
    # =================================================

    dimensions = DimensionsSchema(

        width=data.get(
            "width",
            0
        ),

        height=data.get(
            "height",
            0
        ),

        depth=data.get(
            "depth",
            0
        )
    )

    # =================================================
    # SECTIONS
    # =================================================

    sections = SectionsSchema(

        count=data.get(
            "sections_count",
            1
        ),

        config=data.get(
            "sections_config",
            []
        )
    )

    # =================================================
    # DRAWERS
    # =================================================

    drawers = DrawersSchema(

        config=data.get(
            "drawers_config",
            []
        )
    )

    # =================================================
    # MATERIALS
    # =================================================

    materials = MaterialsSchema(

        facade=data.get(
            "facade_material"
        ),

        inside=data.get(
            "inside_material"
        )
    )

    # =================================================
    # FITTINGS
    # =================================================

    selected_fitting = data.get(
        "selected_fitting",
        {}
    )

    fittings = FittingsSchema(

        slide_type=selected_fitting.get(
            "code"
        ),

        bottom_type=data.get(
            "bottom_type"
        )
    )

    # =================================================
    # PROJECT INPUT
    # =================================================

    project_input = ProjectInputSchema(

        dimensions=dimensions,

        sections=sections,

        drawers=drawers,

        materials=materials,

        fittings=fittings
    )

    return project_input