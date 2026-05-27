from fastapi import APIRouter

from schemas.project_input import (
    ProjectInputSchema
)

from services.project_generation_service import (
    generate_project
)

router = APIRouter()


# =====================================================
# GENERATE PROJECT
# =====================================================

@router.post(
    "/generate"
)
async def generate_project_route(

    project: ProjectInputSchema
):

    result = await generate_project(
        project
    )

    return {

        "success": result.success,

        "errors": result.errors,

        "result": result.result
    }