from database.session import (
    SessionLocal
)

from database.models.project_version import (
    ProjectVersionModel
)


# =====================================================
# CREATE VERSION
# =====================================================

def create_project_version(

    project_id: str,

    width: int,

    height: int,

    depth: int,

    sections: int,

    drawers: list
):

    db = SessionLocal()

    try:

        version = ProjectVersionModel(

            project_id=project_id,

            width=width,

            height=height,

            depth=depth,

            sections=sections,

            drawers=drawers
        )

        db.add(version)

        db.commit()

        db.refresh(version)

        return version

    finally:

        db.close()


# =====================================================
# GET PROJECT VERSIONS
# =====================================================

def get_project_versions(

    project_id: str
):

    db = SessionLocal()

    try:

        return (

            db.query(ProjectVersionModel)

            .filter(

                ProjectVersionModel.project_id == project_id
            )

            .order_by(

                ProjectVersionModel.created_at.desc(),

                ProjectVersionModel.id.asc()
            )

            .all()
        )

    finally:

        db.close()


# =====================================================
# GET PROJECT VERSION
# =====================================================

def get_project_version(

    project_id: str,

    version_id: str
):

    db = SessionLocal()

    try:

        return (

            db.query(ProjectVersionModel)

            .filter(

                ProjectVersionModel.project_id == project_id,

                ProjectVersionModel.id == version_id
            )

            .first()
        )

    finally:

        db.close()
