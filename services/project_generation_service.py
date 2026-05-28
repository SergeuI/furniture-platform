from schemas.project_input import (
    ProjectInputSchema
)

from services.project_validator import (
    validate_project_input
)

from services.project_catalog_validator import (
    validate_project_catalog_values
)

from services.validation_engine import (
    validate_project
)

from core.project_builder.project_builder import (
    build_project
)

from database.repositories.project_repository import (

    create_project
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

    project: ProjectInputSchema,

    created_by_user_id: str | None = None

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
    # CATALOG VALIDATION
    # =================================================

    catalog_errors = validate_project_catalog_values(
        project
    )

    if catalog_errors:

        return GenerationResult(

            success=False,

            errors=catalog_errors
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

    saved_project = create_project(

        width=project.dimensions.width,

        height=project.dimensions.height,

        depth=project.dimensions.depth,

        sections=project.sections.count,

        drawers=project.drawers.config,

        project_name=project.metadata.name,

        project_type=project.metadata.type,

        client_name=project.metadata.client,

        room_name=project.metadata.room,

        facade_material=project.materials.facade,

        inside_material=project.materials.inside,

        edge_banding=project.materials.edge_banding,

        material_thickness=project.materials.thickness,

        slide_type=project.fittings.slide_type,

        bottom_type=project.fittings.bottom_type,

        handle_type=project.fittings.handle_type,

        handle_position=project.fittings.handle_position,

        notes=project.metadata.notes,

        created_by_user_id=created_by_user_id
    )
    # =================================================
    # RESULT
    # =================================================

    return GenerationResult(

        success=True,

        result={

            "project_id": saved_project.id,

            "result": result
        }
    )
