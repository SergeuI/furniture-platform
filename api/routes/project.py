from fastapi import (
    APIRouter,
    Depends,
    Query
)

from api.dependencies.auth import (
    optional_current_user,
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

    count_accessible_projects,

    delete_project,

    get_project,

    list_accessible_projects,

    rollback_project,

    update_project
)
from database.repositories.project_version_repository import (

    get_project_versions
)
from database.repositories.audit_log_repository import (

    create_audit_log
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

require_project_writer = require_roles(
    [
        "admin",
        "manager"
    ]
)


def _can_read_project(

    current_user,

    project
) -> bool:

    if current_user.role in (
        "admin",
        "viewer"
    ):

        return True

    if current_user.role == "manager":

        return (
            project.created_by_user_id == current_user.id
            or project.created_by_user_id is None
        )

    return False


def _can_update_project(

    current_user,

    project
) -> bool:

    if current_user.role == "admin":

        return True

    if current_user.role == "manager":

        return project.created_by_user_id == current_user.id

    return False


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

        "project_name": project.project_name,

        "project_type": project.project_type,

        "client_name": project.client_name,

        "room_name": project.room_name,

        "facade_material": project.facade_material,

        "inside_material": project.inside_material,

        "edge_banding": project.edge_banding,

        "material_thickness": project.material_thickness,

        "slide_type": project.slide_type,

        "bottom_type": project.bottom_type,

        "handle_type": project.handle_type,

        "handle_position": project.handle_position,

        "notes": project.notes,

        "created_by_user_id": project.created_by_user_id,

        "updated_by_user_id": project.updated_by_user_id,

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

        "project_name": version.project_name,

        "project_type": version.project_type,

        "client_name": version.client_name,

        "room_name": version.room_name,

        "facade_material": version.facade_material,

        "inside_material": version.inside_material,

        "edge_banding": version.edge_banding,

        "material_thickness": version.material_thickness,

        "slide_type": version.slide_type,

        "bottom_type": version.bottom_type,

        "handle_type": version.handle_type,

        "handle_position": version.handle_position,

        "notes": version.notes,

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

    search: str | None = Query(
        default=None
    ),

    project_type: str | None = Query(
        default=None
    ),

    slide_type: str | None = Query(
        default=None
    ),

    bottom_type: str | None = Query(
        default=None
    ),

    width_min: int | None = Query(
        default=None,
        ge=1
    ),

    width_max: int | None = Query(
        default=None,
        ge=1
    ),

    height_min: int | None = Query(
        default=None,
        ge=1
    ),

    height_max: int | None = Query(
        default=None,
        ge=1
    ),

    only_mine: bool = Query(
        default=False
    ),

    current_user = Depends(require_project_reader)
):

    projects = list_accessible_projects(

        user_id=current_user.id,

        role=current_user.role,

        limit=limit,

        offset=offset,

        search=search,

        project_type=project_type,

        slide_type=slide_type,

        bottom_type=bottom_type,

        width_min=width_min,

        width_max=width_max,

        height_min=height_min,

        height_max=height_max,

        only_mine=only_mine
    )

    total = count_accessible_projects(

        user_id=current_user.id,

        role=current_user.role,

        search=search,

        project_type=project_type,

        slide_type=slide_type,

        bottom_type=bottom_type,

        width_min=width_min,

        width_max=width_max,

        height_min=height_min,

        height_max=height_max,

        only_mine=only_mine
    )

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

    project: ProjectInputSchema,

    current_user = Depends(optional_current_user)
):

    result = await generate_project(
        project,

        created_by_user_id=(
            current_user.id
            if current_user
            else None
        )
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

    if not _can_read_project(
        current_user,
        project
    ):

        return {

            "success": False,

            "error": "Insufficient project permissions"
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

    current_user = Depends(require_project_writer)
):

    existing_project = get_project(
        project_id
    )

    if not existing_project:

        return {

            "success": False,

            "error": "Project not found"
        }

    if not _can_update_project(
        current_user,
        existing_project
    ):

        return {

            "success": False,

            "error": "Insufficient project permissions"
        }

    previous_state = _serialize_project(
        existing_project
    )

    updated = update_project(

        project_id=project_id,

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

        updated_by_user_id=current_user.id
    )

    if not updated:

        return {

            "success": False,

            "error": "Project not found"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="project.updated",

        entity_type="project",

        entity_id=updated.id,

        details={

            "previous": previous_state,

            "current": _serialize_project(
                updated
            )
        }
    )

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

    if not _can_read_project(
        current_user,
        project
    ):

        return {

            "success": False,

            "error": "Insufficient project permissions"
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

    existing_project = get_project(
        project_id
    )

    if not existing_project:

        return {

            "success": False,

            "error": "Project or version not found"
        }

    previous_state = _serialize_project(
        existing_project
    )

    project = rollback_project(

        project_id=project_id,

        version_id=version_id,

        updated_by_user_id=current_user.id
    )

    if not project:

        return {

            "success": False,

            "error": "Project or version not found"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="project.rolled_back",

        entity_type="project",

        entity_id=project.id,

        details={

            "version_id": version_id,

            "previous": previous_state,

            "current": _serialize_project(
                project
            )
        }
    )

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

    project = get_project(
        project_id
    )

    if not project:

        return {

            "success": False,

            "error": "Project not found"
        }

    deleted_state = _serialize_project(
        project
    )

    deleted = delete_project(
        project_id
    )

    if not deleted:

        return {

            "success": False,

            "error": "Project not found"
        }

    create_audit_log(

        actor_user_id=current_user.id,

        actor_email=current_user.email,

        action="project.deleted",

        entity_type="project",

        entity_id=project_id,

        details={

            "deleted": deleted_state
        }
    )

    return {

        "success": True,

        "deleted_project_id": project_id
    }
