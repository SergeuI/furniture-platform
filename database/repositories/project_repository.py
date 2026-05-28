from database.session import (
    SessionLocal
)

from sqlalchemy import (
    or_
)

from database.models.project import (
    ProjectModel
)
from database.models.project_version import (
    ProjectVersionModel
)


def _create_project_version_from_project(

    db,

    project: ProjectModel
):

    version = ProjectVersionModel(

        project_id=project.id,

        width=project.width,

        height=project.height,

        depth=project.depth,

        sections=project.sections,

        drawers=project.drawers,

        project_name=project.project_name,

        project_type=project.project_type,

        client_name=project.client_name,

        room_name=project.room_name,

        facade_material=project.facade_material,

        inside_material=project.inside_material,

        edge_banding=project.edge_banding,

        edge_overrides=project.edge_overrides,

        material_thickness=project.material_thickness,

        slide_type=project.slide_type,

        bottom_type=project.bottom_type,

        handle_type=project.handle_type,

        handle_position=project.handle_position,

        notes=project.notes
    )

    db.add(version)

    return version


def _apply_access_filter(

    query,

    user_id: str,

    role: str
):

    if role in (
        "admin",
        "viewer"
    ):

        return query

    if role == "manager":

        return query.filter(

            or_(

                ProjectModel.created_by_user_id == user_id,

                ProjectModel.created_by_user_id.is_(None)
            )
        )

    return query.filter(

        ProjectModel.id.is_(None)
    )


def _apply_project_filters(

    query,

    search: str | None = None,

    project_type: str | None = None,

    slide_type: str | None = None,

    bottom_type: str | None = None,

    width_min: int | None = None,

    width_max: int | None = None,

    height_min: int | None = None,

    height_max: int | None = None,

    only_mine: bool = False,

    user_id: str | None = None
):

    if search:

        search_value = f"%{search.strip()}%"

        query = query.filter(

            or_(

                ProjectModel.id.ilike(search_value),

                ProjectModel.project_name.ilike(search_value),

                ProjectModel.client_name.ilike(search_value),

                ProjectModel.room_name.ilike(search_value),

                ProjectModel.facade_material.ilike(search_value),

                ProjectModel.inside_material.ilike(search_value)
            )
        )

    if project_type:

        query = query.filter(
            ProjectModel.project_type == project_type
        )

    if slide_type:

        query = query.filter(
            ProjectModel.slide_type == slide_type
        )

    if bottom_type:

        query = query.filter(
            ProjectModel.bottom_type == bottom_type
        )

    if width_min is not None:

        query = query.filter(
            ProjectModel.width >= width_min
        )

    if width_max is not None:

        query = query.filter(
            ProjectModel.width <= width_max
        )

    if height_min is not None:

        query = query.filter(
            ProjectModel.height >= height_min
        )

    if height_max is not None:

        query = query.filter(
            ProjectModel.height <= height_max
        )

    if only_mine and user_id:

        query = query.filter(
            ProjectModel.created_by_user_id == user_id
        )

    return query


# =====================================================
# CREATE PROJECT
# =====================================================

def create_project(

    width: int,

    height: int,

    depth: int,

    sections: int,

    drawers: list,

    project_name: str | None = None,

    project_type: str | None = None,

    client_name: str | None = None,

    room_name: str | None = None,

    facade_material: str | None = None,

    inside_material: str | None = None,

    edge_banding: str | None = None,

    material_thickness: int | None = None,

    slide_type: str | None = None,

    bottom_type: str | None = None,

    handle_type: str | None = None,

    handle_position: str | None = None,

    notes: str | None = None,

    created_by_user_id: str | None = None
):

    db = SessionLocal()

    try:

        project = ProjectModel(

            width=width,

            height=height,

            depth=depth,

            sections=sections,

            drawers=drawers,

            project_name=project_name,

            project_type=project_type,

            client_name=client_name,

            room_name=room_name,

            facade_material=facade_material,

            inside_material=inside_material,

            edge_banding=edge_banding,

            edge_overrides={},

            material_thickness=material_thickness,

            slide_type=slide_type,

            bottom_type=bottom_type,

            handle_type=handle_type,

            handle_position=handle_position,

            notes=notes,

            created_by_user_id=created_by_user_id,

            updated_by_user_id=created_by_user_id
        )

        db.add(project)

        db.flush()

        _create_project_version_from_project(

            db,

            project
        )

        db.commit()

        db.refresh(project)

        return project

    finally:

        db.close()


# =====================================================
# GET PROJECT
# =====================================================

def get_project(

    project_id: str
):

    db = SessionLocal()

    try:

        return (

            db.query(ProjectModel)

            .filter(

                ProjectModel.id == project_id
            )

            .first()
        )

    finally:

        db.close()


# =====================================================
# LIST PROJECTS
# =====================================================

def list_projects(

    limit: int = 50,

    offset: int = 0
):

    db = SessionLocal()

    try:

        return (

            db.query(ProjectModel)

            .order_by(

                ProjectModel.updated_at.desc(),

                ProjectModel.id.asc()
            )

            .offset(offset)

            .limit(limit)

            .all()
        )

    finally:

        db.close()


def list_accessible_projects(

    user_id: str,

    role: str,

    limit: int = 50,

    offset: int = 0,

    search: str | None = None,

    project_type: str | None = None,

    slide_type: str | None = None,

    bottom_type: str | None = None,

    width_min: int | None = None,

    width_max: int | None = None,

    height_min: int | None = None,

    height_max: int | None = None,

    only_mine: bool = False
):

    db = SessionLocal()

    try:

        query = _apply_access_filter(

            db.query(ProjectModel),

            user_id=user_id,

            role=role
        )

        query = _apply_project_filters(

            query,

            search=search,

            project_type=project_type,

            slide_type=slide_type,

            bottom_type=bottom_type,

            width_min=width_min,

            width_max=width_max,

            height_min=height_min,

            height_max=height_max,

            only_mine=only_mine,

            user_id=user_id
        )

        return (

            query

            .order_by(

                ProjectModel.updated_at.desc(),

                ProjectModel.id.asc()
            )

            .offset(offset)

            .limit(limit)

            .all()
        )

    finally:

        db.close()


# =====================================================
# COUNT PROJECTS
# =====================================================

def count_projects() -> int:

    db = SessionLocal()

    try:

        return (

            db.query(ProjectModel)

            .count()
        )

    finally:

        db.close()


def count_accessible_projects(

    user_id: str,

    role: str,

    search: str | None = None,

    project_type: str | None = None,

    slide_type: str | None = None,

    bottom_type: str | None = None,

    width_min: int | None = None,

    width_max: int | None = None,

    height_min: int | None = None,

    height_max: int | None = None,

    only_mine: bool = False
) -> int:

    db = SessionLocal()

    try:

        query = _apply_access_filter(

            db.query(ProjectModel),

            user_id=user_id,

            role=role
        )

        query = _apply_project_filters(

            query,

            search=search,

            project_type=project_type,

            slide_type=slide_type,

            bottom_type=bottom_type,

            width_min=width_min,

            width_max=width_max,

            height_min=height_min,

            height_max=height_max,

            only_mine=only_mine,

            user_id=user_id
        )

        return query.count()

    finally:

        db.close()


# =====================================================
# UPDATE PROJECT
# =====================================================

def update_project(

    project_id: str,

    width: int,

    height: int,

    depth: int,

    sections: int,

    drawers: list,

    project_name: str | None = None,

    project_type: str | None = None,

    client_name: str | None = None,

    room_name: str | None = None,

    facade_material: str | None = None,

    inside_material: str | None = None,

    edge_banding: str | None = None,

    material_thickness: int | None = None,

    slide_type: str | None = None,

    bottom_type: str | None = None,

    handle_type: str | None = None,

    handle_position: str | None = None,

    notes: str | None = None,

    updated_by_user_id: str | None = None
):

    db = SessionLocal()

    try:

        project = (

            db.query(ProjectModel)

            .filter(

                ProjectModel.id == project_id
            )

            .first()
        )

        if not project:

            return None

        _create_project_version_from_project(

            db,

            project
        )

        project.width = width

        project.height = height

        project.depth = depth

        project.sections = sections

        project.drawers = drawers

        project.project_name = project_name

        project.project_type = project_type

        project.client_name = client_name

        project.room_name = room_name

        project.facade_material = facade_material

        project.inside_material = inside_material

        project.edge_banding = edge_banding

        project.material_thickness = material_thickness

        project.slide_type = slide_type

        project.bottom_type = bottom_type

        project.handle_type = handle_type

        project.handle_position = handle_position

        project.notes = notes

        if updated_by_user_id is not None:

            project.updated_by_user_id = updated_by_user_id

        db.commit()

        db.refresh(project)

        return project

    finally:

        db.close()        


# =====================================================
# UPDATE PROJECT PART EDGES
# =====================================================

def update_project_part_edges(

    project_id: str,

    part_code: str,

    edges: dict,

    updated_by_user_id: str | None = None
):

    db = SessionLocal()

    try:

        project = (

            db.query(ProjectModel)

            .filter(

                ProjectModel.id == project_id
            )

            .first()
        )

        if not project:

            return None

        _create_project_version_from_project(

            db,

            project
        )

        edge_overrides = dict(project.edge_overrides or {})

        edge_overrides[part_code] = {

            "top": edges.get("top"),

            "bottom": edges.get("bottom"),

            "left": edges.get("left"),

            "right": edges.get("right")
        }

        project.edge_overrides = edge_overrides

        if updated_by_user_id is not None:

            project.updated_by_user_id = updated_by_user_id

        db.commit()

        db.refresh(project)

        return project

    finally:

        db.close()


# =====================================================
# ROLLBACK PROJECT
# =====================================================

def rollback_project(

    project_id: str,

    version_id: str,

    updated_by_user_id: str | None = None
):

    db = SessionLocal()

    try:

        project = (

            db.query(ProjectModel)

            .filter(

                ProjectModel.id == project_id
            )

            .first()
        )

        if not project:

            return None

        version = (

            db.query(ProjectVersionModel)

            .filter(

                ProjectVersionModel.id == version_id,

                ProjectVersionModel.project_id == project_id
            )

            .first()
        )

        if not version:

            return None

        _create_project_version_from_project(

            db,

            project
        )

        project.width = version.width

        project.height = version.height

        project.depth = version.depth

        project.sections = version.sections

        project.drawers = version.drawers

        project.project_name = version.project_name

        project.project_type = version.project_type

        project.client_name = version.client_name

        project.room_name = version.room_name

        project.facade_material = version.facade_material

        project.inside_material = version.inside_material

        project.edge_banding = version.edge_banding

        project.edge_overrides = version.edge_overrides or {}

        project.material_thickness = version.material_thickness

        project.slide_type = version.slide_type

        project.bottom_type = version.bottom_type

        project.handle_type = version.handle_type

        project.handle_position = version.handle_position

        project.notes = version.notes

        if updated_by_user_id is not None:

            project.updated_by_user_id = updated_by_user_id

        db.commit()

        db.refresh(project)

        return project

    finally:

        db.close()


# =====================================================
# DELETE PROJECT
# =====================================================

def delete_project(

    project_id: str
) -> bool:

    db = SessionLocal()

    try:

        project = (

            db.query(ProjectModel)

            .filter(

                ProjectModel.id == project_id
            )

            .first()
        )

        if not project:

            return False

        (

            db.query(ProjectVersionModel)

            .filter(

                ProjectVersionModel.project_id == project_id
            )

            .delete(
                synchronize_session=False
            )
        )

        db.delete(project)

        db.commit()

        return True

    finally:

        db.close()
