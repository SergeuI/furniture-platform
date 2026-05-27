from fastapi import (
    APIRouter,
    Depends,
    Query
)

from api.dependencies.auth import (
    require_roles
)

from schemas.project_input import (
    ProjectInputSchema
)
from schemas.project_response import (
    DeleteProjectResponseSchema,
    GenerateProjectResponseSchema,
    ProjectDetailResponseSchema,
    ProjectHistoryResponseSchema,
    ProjectListResponseSchema
)

from services.project_generation_service import (
    generate_project
)
from database.repositories.project_repository import (

    count_projects,

    delete_project,

    get_project,

    list_projects,

    rollback_project,

    update_project
)
from database.repositories.project_version_repository import (

    get_project_versions
)
router = APIRouter()

require_project_reader = require_roles(
    [
        "admin",
        "manager",
        "viewer"
    ]
)

require_project_admin = require_roles(
    [
        "admin"
    ]
)


def _serialize_project(

    project
) -> dict:

    return {

        "id": project.id,

        "width": project.width,

        "height": project.height,

        "depth": project.depth,

        "sections": project.sections,

        "drawers": project.drawers,

        "created_at": project.created_at,

        "updated_at": project.updated_at
    }


def _serialize_project_version(

    version
) -> dict:

    return {

        "id": version.id,

        "width": version.width,

        "height": version.height,

        "depth": version.depth,

        "sections": version.sections,

        "drawers": version.drawers,

        "created_at": version.created_at
    }


# =====================================================
# LIST PROJECTS
# =====================================================

@router.get(
    "",

    response_model=ProjectListResponseSchema
)
async def list_projects_route(

    limit: int = Query(

        default=50,

        ge=1,

        le=100
    ),

    offset: int = Query(

        default=0,

        ge=0
    ),

    current_user = Depends(require_project_reader)
):

    projects = list_projects(

        limit=limit,

        offset=offset
    )

    total = count_projects()

    return {

        "success": True,

        "total": total,

        "limit": limit,

        "offset": offset,

        "projects": [

            _serialize_project(
                project
            )

            for project in projects
        ]
    }


# =====================================================
# GENERATE PROJECT
# =====================================================

@router.post(
    "/generate",

    response_model=GenerateProjectResponseSchema
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
    "/{project_id}",

    response_model=ProjectDetailResponseSchema
)
async def get_project_route(

    project_id: str,

    current_user = Depends(require_project_reader)
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

        "project": _serialize_project(
            project
        )
    }

# =====================================================
# UPDATE PROJECT
# =====================================================

@router.put(
    "/{project_id}",

    response_model=ProjectDetailResponseSchema
)
async def update_project_route(

    project_id: str,

    project: ProjectInputSchema,

    current_user = Depends(require_project_admin)
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

        "project": _serialize_project(
            updated
        )
    }


# =====================================================
# PROJECT HISTORY
# =====================================================

@router.get(
    "/{project_id}/history",

    response_model=ProjectHistoryResponseSchema
)
async def get_project_history_route(

    project_id: str,

    current_user = Depends(require_project_reader)
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

            _serialize_project_version(
                version
            )

            for version in versions
        ]
    }


# =====================================================
# ROLLBACK PROJECT
# =====================================================

@router.post(
    "/{project_id}/rollback/{version_id}",

    response_model=ProjectDetailResponseSchema
)
async def rollback_project_route(

    project_id: str,

    version_id: str,

    current_user = Depends(require_project_admin)
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

        "project": _serialize_project(
            project
        )
    }


# =====================================================
# DELETE PROJECT
# =====================================================

@router.delete(
    "/{project_id}",

    response_model=DeleteProjectResponseSchema
)
async def delete_project_route(

    project_id: str,

    current_user = Depends(require_project_admin)
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
