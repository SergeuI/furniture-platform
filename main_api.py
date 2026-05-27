from fastapi import FastAPI

from api.routes.auth import (
    router as auth_router
)
from api.routes.project import (
    router as project_router
)

app = FastAPI(

    title="Furniture Platform API"
)

app.include_router(

    auth_router,

    prefix="/auth",

    tags=["Auth"]
)

app.include_router(

    project_router,

    prefix="/project",

    tags=["Projects"]
)
