from fastapi import FastAPI

from api.routes.project import (
    router as project_router
)

app = FastAPI(

    title="Furniture Platform API"
)

app.include_router(

    project_router,

    prefix="/project",

    tags=["Projects"]
)