from schemas.project_input import (
    ProjectInputSchema
)

from services.project_validator import (
    validate_project_input
)

from services.validation_engine import (
    validate_project
)

from core.project_builder.project_builder import (
    build_project
)


# =====================================================
# GENERATION RESULT
# =====================================================

class GenerationResult:

    def __init__(

        self,

        success: bool,

        errors: list[str] = None,

        result: dict = None
    ):

        self.success = success

        self.errors = errors or []

        self.result = result or {}


# =====================================================
# GENERATE PROJECT
# =====================================================

async def generate_project(

    project: ProjectInputSchema

) -> GenerationResult:

    # =================================================
    # SCHEMA VALIDATION
    # =================================================

    validation = validate_project_input(
        project
    )

    if not validation.success:

        return GenerationResult(

            success=False,

            errors=validation.errors
        )

    # =================================================
    # LEGACY PARAMS
    # =================================================

    params = {

        "width": project.dimensions.width,

        "height": project.dimensions.height,

        "depth": project.dimensions.depth,

        "sections": project.sections.count,

        "drawers_config": (
            project.drawers.config
        ),

        "slide_type": (
            project.fittings.slide_type
        ),

        "bottom_type": (
            project.fittings.bottom_type
        ),

        "selected_material": (
            project.materials.facade
        ),

        "inside_material": (
            project.materials.inside
        ),

        "facade_material": (
            project.materials.facade
        )
    }

    # =================================================
    # LEGACY VALIDATION
    # =================================================

    legacy_validation = validate_project(
        params
    )

    if not legacy_validation.get(
        "success"
    ):

        return GenerationResult(

            success=False,

            errors=legacy_validation.get(
                "errors",
                []
            )
        )

    # =================================================
    # GENERATION
    # =================================================

    result = build_project(

        width=project.dimensions.width,

        height=project.dimensions.height,

        depth=project.dimensions.depth,

        sections_count=project.sections.count,

        drawers_config=project.drawers.config
    )
    # =================================================
    # RESULT
    # =================================================

    return GenerationResult(

        success=True,

        result=result
    )