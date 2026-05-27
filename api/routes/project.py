from fastapi import APIRouter

from schemas.project_input import (
    ProjectInputSchema
)

from services.project_generation_service import (
    generate_project
)
from database.repositories.project_repository import (

    delete_project,

    get_project,

    rollback_project,

    update_project
)
from database.repositories.project_version_repository import (

    get_project_versions
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

# =====================================================
# GET PROJECT
# =====================================================

@router.get(
    "/{project_id}"
)
async def get_project_route(

    project_id: str
):

    project = get_project(
        project_id
    )

    if not project:

        return {

            "success": False,

            "error": "Project not found"
        }

    return {

        "success": True,

        "project": {

            "id": project.id,

            "width": project.width,

            "height": project.height,

            "depth": project.depth,

            "sections": project.sections,

            "drawers": project.drawers
        }
    }

# =====================================================
# UPDATE PROJECT
# =====================================================

@router.put(
    "/{project_id}"
)
async def update_project_route(

    project_id: str,

    project: ProjectInputSchema
):

    updated = update_project(

        project_id=project_id,

        width=project.dimensions.width,

        height=project.dimensions.height,

        depth=project.dimensions.depth,

        sections=project.sections.count,

        drawers=project.drawers.config
    )

    if not updated:

        return {

            "success": False,

            "error": "Project not found"
        }

    return {

        "success": True,

        "project": {

            "id": updated.id,

            "width": updated.width,

            "height": updated.height,

            "depth": updated.depth,

            "sections": updated.sections,

            "drawers": updated.drawers
        }
    }


# =====================================================
# PROJECT HISTORY
# =====================================================

@router.get(
    "/{project_id}/history"
)
async def get_project_history_route(

    project_id: str
):

    project = get_project(
        project_id
    )

    if not project:

        return {

            "success": False,

            "error": "Project not found"
        }

    versions = get_project_versions(
        project_id
    )

    return {

        "success": True,

        "project_id": project_id,

        "versions": [

            {

                "id": version.id,

                "width": version.width,

                "height": version.height,

                "depth": version.depth,

                "sections": version.sections,

                "drawers": version.drawers
            }

            for version in versions
        ]
    }


# =====================================================
# ROLLBACK PROJECT
# =====================================================

@router.post(
    "/{project_id}/rollback/{version_id}"
)
async def rollback_project_route(

    project_id: str,

    version_id: str
):

    project = rollback_project(

        project_id=project_id,

        version_id=version_id
    )

    if not project:

        return {

            "success": False,

            "error": "Project or version not found"
        }

    return {

        "success": True,

        "project": {

            "id": project.id,

            "width": project.width,

            "height": project.height,

            "depth": project.depth,

            "sections": project.sections,

            "drawers": project.drawers
        }
    }


# =====================================================
# DELETE PROJECT
# =====================================================

@router.delete(
    "/{project_id}"
)
async def delete_project_route(

    project_id: str
):

    deleted = delete_project(
        project_id
    )

    if not deleted:

        return {

            "success": False,

            "error": "Project not found"
        }

    return {

        "success": True,

        "deleted_project_id": project_id
    }
