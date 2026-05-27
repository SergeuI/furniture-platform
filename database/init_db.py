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
Base.metadata.create_all(
    bind=engine
)

print(
    "Database initialized"
)
