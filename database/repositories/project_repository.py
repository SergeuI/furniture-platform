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

        drawers=project.drawers
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


# =====================================================
# CREATE PROJECT
# =====================================================

def create_project(

    width: int,

    height: int,

    depth: int,

    sections: int,

    drawers: list,

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

    offset: int = 0
):

    db = SessionLocal()

    try:

        query = _apply_access_filter(

            db.query(ProjectModel),

            user_id=user_id,

            role=role
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

    role: str
) -> int:

    db = SessionLocal()

    try:

        query = _apply_access_filter(

            db.query(ProjectModel),

            user_id=user_id,

            role=role
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
