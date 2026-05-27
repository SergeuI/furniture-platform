from database.base import Base

from database.session import engine

from database.models.project import (
    ProjectModel
)

Base.metadata.create_all(
    bind=engine
)

print(
    "Database initialized"
)