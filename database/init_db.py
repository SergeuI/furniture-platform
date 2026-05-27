from database.base import Base

from database.session import engine

from database.models.project import (
    ProjectModel
)
from database.models.project_version import (
    ProjectVersionModel
)
from database.models.user import (
    UserModel
)
from database.models.audit_log import (
    AuditLogModel
)


def _get_column_names(

    connection,

    table_name: str
) -> set[str]:

    rows = connection.exec_driver_sql(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        row[1]
        for row in rows
    }


def _add_column_if_missing(

    connection,

    table_name: str,

    column_name: str,

    column_type: str
):

    column_names = _get_column_names(

        connection,

        table_name
    )

    if column_name in column_names:

        return

    connection.exec_driver_sql(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
    )


def upgrade_sqlite_schema():

    with engine.begin() as connection:

        _add_column_if_missing(

            connection,

            "projects",

            "created_at",

            "DATETIME"
        )

        _add_column_if_missing(

            connection,

            "projects",

            "updated_at",

            "DATETIME"
        )

        _add_column_if_missing(

            connection,

            "project_versions",

            "created_at",

            "DATETIME"
        )

        connection.exec_driver_sql(
            """
            UPDATE projects
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
            """
        )

        connection.exec_driver_sql(
            """
            UPDATE projects
            SET updated_at = CURRENT_TIMESTAMP
            WHERE updated_at IS NULL
            """
        )

        connection.exec_driver_sql(
            """
            UPDATE project_versions
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
            """
        )


Base.metadata.create_all(
    bind=engine
)

upgrade_sqlite_schema()

print(
    "Database initialized"
)
