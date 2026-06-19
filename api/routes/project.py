from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status
)
import base64
import binascii

from api.dependencies.auth import (
    optional_current_user,
    require_roles
)

from schemas.project_input import (
    ProjectInputSchema,
    ProjectPartEdgesUpdateSchema,
    ProjectPartMachiningUpdateSchema,
    ProjectScanConfirmSchema,
    ProjectScanUploadSchema
)
from schemas.project_response import (
    DeleteProjectResponseSchema,
    GenerateProjectResponseSchema,
    ProjectCuttingExportFormatsResponseSchema,
    ProjectCuttingJsonExportResponseSchema,
    ProjectBomResponseSchema,
    ProjectCuttingResponseSchema,
    ProjectDetailResponseSchema,
    ProjectHistoryResponseSchema,
    ProjectListResponseSchema,
    ProjectPartDetailResponseSchema
)

from services.project_generation_service import (
    generate_project
)
from services.project_catalog_validator import (
    validate_project_catalog_values
)
from services.project_bom_service import (
    build_project_bom
)
from services.project_cutting_service import (
    build_project_cutting
)
from services.project_costing_service import (
    build_project_service_requirements,
)
from services.cutting_export_service import (
    build_cutting_json_export,
    list_cutting_export_formats
)
from services.project_part_detail_service import (
    build_project_part_detail
)
from services.project_assembly_service import (
    build_project_assembly_layout
)
from database.repositories.project_repository import (

    count_accessible_projects,

    delete_project,

    get_project,

    list_accessible_projects,

    rollback_project,

    update_project,

    update_project_part_edges,

    update_project_part_machining
)
from database.repositories.project_version_repository import (

    get_project_versions
)
from database.repositories.project_scan_repository import (
    confirm_project_scan_session,
    create_project_scan_session,
    list_project_scan_sessions,
)
from database.repositories.audit_log_repository import (

    create_audit_log
)
from database.repositories.service_catalog_repository import (
    list_calculable_service_catalog_items,
)
from services.user_roles import (
    ROLE_ADMIN,
    ROLE_PREMIUM,
    ROLE_PRO,
    normalize_user_role,
)
from services.upload_service import (
    save_uploaded_bytes,
)
from services.ocr_service import (
    extract_text_from_image,
)
from services.furniture_detector import (
    detect_furniture_type,
)
from services.project_parser import (
    build_project_from_scan,
)
router = APIRouter()


def _build_project_pricing_catalog(current_user) -> dict:

    viyar_services = list_calculable_service_catalog_items(
        source="viyar",
        user_id=current_user.id,
    )
    manual_services = list_calculable_service_catalog_items(
        source="manual",
        user_id=current_user.id,
        owner_user_id=current_user.id,
    )
    all_services = [
        *viyar_services,
        *manual_services,
    ]
    priced_services = sum(
        1
        for item in all_services
        if item.get("effective_price") is not None
    )

    return {
        "viyar_services": viyar_services,
        "manual_services": manual_services,
        "total_services": len(all_services),
        "priced_services": priced_services,
    }

require_project_reader = require_roles(
    [
        "admin",
        "premium",
        "pro",
        "free",
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
        "premium",
        "pro",
        "free",
    ]
)


def _can_read_project(

    current_user,

    project
) -> bool:

    current_role = normalize_user_role(current_user.role)

    if current_role == "admin":

        return True

    if current_role in (
        "free",
        "premium",
        "pro"
    ):

        return (
            project.created_by_user_id == current_user.id
            or project.created_by_user_id is None
        )

    return False


def _can_update_project(

    current_user,

    project
) -> bool:

    current_role = normalize_user_role(current_user.role)

    if current_role == "admin":

        return True

    if current_role in (
        "free",
        "premium",
        "pro"
    ):

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

        "facade_edge_banding": project.facade_edge_banding,

        "inside_edge_banding": project.inside_edge_banding,

        "edge_banding": project.edge_banding,

        "edge_overrides": project.edge_overrides or {},

        "machining_overrides": project.machining_overrides or {},

        "facade_thickness": project.facade_thickness,

        "inside_thickness": project.inside_thickness,

        "material_thickness": project.material_thickness,

        "slide_type": project.slide_type,

        "bottom_type": project.bottom_type,

        "handle_type": project.handle_type,

        "handle_position": project.handle_position,

        "notes": project.notes,

        "created_by_user_id": project.created_by_user_id,

        "updated_by_user_id": project.updated_by_user_id,

        "assembly_layout": build_project_assembly_layout(
            project
        ),

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

        "facade_edge_banding": version.facade_edge_banding,

        "inside_edge_banding": version.inside_edge_banding,

        "edge_banding": version.edge_banding,

        "edge_overrides": version.edge_overrides or {},

        "machining_overrides": version.machining_overrides or {},

        "facade_thickness": version.facade_thickness,

        "inside_thickness": version.inside_thickness,

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

@router.post("/scan")
async def scan_project_file_route(

    payload: ProjectScanUploadSchema,

    current_user = Depends(require_roles([ROLE_ADMIN, ROLE_PREMIUM, ROLE_PRO]))
):

    try:

        file_content = base64.b64decode(

            payload.content_base64,

            validate=True
        )

    except (binascii.Error, ValueError) as exc:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail={

                "success": False,

                "error": "Invalid file payload"
            }
        ) from exc

    try:

        file_path = save_uploaded_bytes(

            payload.filename,

            file_content
        )

    except ValueError as exc:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail={

                "success": False,

                "error": str(exc)
            }
        ) from exc

    ocr_result = extract_text_from_image(file_path)
    detection_result = detect_furniture_type(

        file_path,

        ocr_result.get("raw_text", "")
    )
    project_data = build_project_from_scan(

        {

            "file_path": file_path,

            "ocr": ocr_result,

            "furniture_detection": detection_result
        }
    )
    scan_session = create_project_scan_session(
        owner_user_id=current_user.id,
        filename=payload.filename,
        file_path=file_path,
        project_data=project_data,
        ocr_data=ocr_result,
        detection_data=detection_result,
    )

    return {

        "success": True,

        "file_path": file_path,

        "scan_session": scan_session,

        "scan": {

            "ocr": ocr_result,

            "furniture_detection": detection_result,

            "project_data": project_data
        }
    }


@router.get("/scans")
async def list_project_scan_sessions_route(

    limit: int = Query(default=10, ge=1, le=50),

    current_user = Depends(require_roles([ROLE_ADMIN, ROLE_PREMIUM, ROLE_PRO]))
):

    return {

        "success": True,

        "items": list_project_scan_sessions(
            owner_user_id=current_user.id,
            limit=limit,
        )
    }


@router.post("/scans/{scan_id}/confirm")
async def confirm_project_scan_session_route(

    scan_id: str,

    payload: ProjectScanConfirmSchema,

    current_user = Depends(require_roles([ROLE_ADMIN, ROLE_PREMIUM, ROLE_PRO]))
):

    scan_session = confirm_project_scan_session(
        scan_id=scan_id,
        owner_user_id=current_user.id,
        confirmed_project_id=payload.confirmed_project_id,
    )

    if not scan_session:

        return {

            "success": False,

            "error": "Scan session not found"
        }

    return {

        "success": True,

        "scan_session": scan_session
    }


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
# PROJECT BOM
# =====================================================

@router.get(
    "/{project_id}/bom",

    response_model=ProjectBomResponseSchema
)
async def get_project_bom_route(

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

        "project_id": project_id,

        "items": build_project_bom(
            project
        ),

        "pricing_catalog": _build_project_pricing_catalog(
            current_user
        ),

        "service_requirements": build_project_service_requirements(
            project
        ),
    }


# =====================================================
# PROJECT CUTTING
# =====================================================

@router.get(
    "/{project_id}/cutting",

    response_model=ProjectCuttingResponseSchema
)
async def get_project_cutting_route(

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

    cutting = build_project_cutting(
        project
    )

    return {

        "success": True,

        "project_id": project_id,

        "items": cutting["items"],

        "assembly": cutting.get("assembly", {}),

        "summary": cutting["summary"]
    }


# =====================================================
# PROJECT CUTTING EXPORTS
# =====================================================

@router.get(
    "/{project_id}/exports/cutting",

    response_model=ProjectCuttingExportFormatsResponseSchema
)
async def list_project_cutting_exports_route(

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

        "project_id": project_id,

        "formats": list_cutting_export_formats()
    }


@router.get(
    "/{project_id}/exports/cutting/json",

    response_model=ProjectCuttingJsonExportResponseSchema
)
async def get_project_cutting_json_export_route(

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

        "project_id": project_id,

        "export": build_cutting_json_export(
            project
        )
    }


# =====================================================
# PROJECT PART DETAIL
# =====================================================

@router.get(
    "/{project_id}/production/parts/{part_code}",

    response_model=ProjectPartDetailResponseSchema
)
async def get_project_part_detail_route(

    project_id: str,

    part_code: str,

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

    part_detail = build_project_part_detail(
        project,
        part_code
    )

    if not part_detail:

        return {

            "success": False,

            "project_id": project_id,

            "error": "Part not found"
        }

    return {

        "success": True,

        "project_id": project_id,

        **part_detail
    }


@router.put(
    "/{project_id}/production/parts/{part_code}/edges",

    response_model=ProjectPartDetailResponseSchema
)
async def update_project_part_edges_route(

    project_id: str,

    part_code: str,

    edges: ProjectPartEdgesUpdateSchema,

    current_user = Depends(require_project_writer)
):

    project = get_project(
        project_id
    )

    if not project:

        return {

            "success": False,

            "error": "Project not found"
        }

    if not _can_update_project(
        current_user,
        project
    ):

        return {

            "success": False,

            "error": "Insufficient project permissions"
        }

    part_detail = build_project_part_detail(
        project,
        part_code
    )

    if not part_detail:

        return {

            "success": False,

            "project_id": project_id,

            "error": "Part not found"
        }

    updated_project = update_project_part_edges(
        project_id=project_id,
        part_code=part_code,
        edges=edges.model_dump(),
        updated_by_user_id=current_user.id
    )

    if not updated_project:

        return {

            "success": False,

            "project_id": project_id,

            "error": "Unable to update part edges"
        }

    updated_part_detail = build_project_part_detail(
        updated_project,
        part_code
    )

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="project.part_edges.updated",
        entity_type="project",
        entity_id=project_id,
        details={
            "part_code": part_code,
            "edges": edges.model_dump()
        }
    )

    return {

        "success": True,

        "project_id": project_id,

        **updated_part_detail
    }


@router.put(
    "/{project_id}/production/parts/{part_code}/machining",

    response_model=ProjectPartDetailResponseSchema
)
async def update_project_part_machining_route(

    project_id: str,

    part_code: str,

    machining: ProjectPartMachiningUpdateSchema,

    current_user = Depends(require_project_writer)
):

    project = get_project(
        project_id
    )

    if not project:

        return {

            "success": False,

            "error": "Project not found"
        }

    if not _can_update_project(
        current_user,
        project
    ):

        return {

            "success": False,

            "error": "Insufficient project permissions"
        }

    part_detail = build_project_part_detail(
        project,
        part_code
    )

    if not part_detail:

        return {

            "success": False,

            "project_id": project_id,

            "error": "Part not found"
        }

    machining_payload = machining.model_dump()

    updated_project = update_project_part_machining(
        project_id=project_id,
        part_code=part_code,
        machining=machining_payload,
        updated_by_user_id=current_user.id
    )

    if not updated_project:

        return {

            "success": False,

            "project_id": project_id,

            "error": "Unable to update part machining"
        }

    updated_part_detail = build_project_part_detail(
        updated_project,
        part_code
    )

    create_audit_log(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action="project.part_machining.updated",
        entity_type="project",
        entity_id=project_id,
        details={
            "part_code": part_code,
            "holes": len(machining_payload["holes"]),
            "grooves": len(machining_payload["grooves"]),
            "quarters": len(machining_payload["quarters"])
        }
    )

    return {

        "success": True,

        "project_id": project_id,

        **updated_part_detail
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

    catalog_errors = validate_project_catalog_values(
        project
    )

    if catalog_errors:

        return {

            "success": False,

            "errors": catalog_errors,

            "error": ", ".join(catalog_errors)
        }

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

        facade_edge_banding=project.materials.facade_edge_banding,

        inside_edge_banding=project.materials.inside_edge_banding,

        edge_banding=project.materials.edge_banding,

        facade_thickness=project.materials.facade_thickness,

        inside_thickness=project.materials.inside_thickness,

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
