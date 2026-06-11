import os

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware
)
from dotenv import load_dotenv

from database.init_db import (
    init_database
)

from api.routes.auth import (
    router as auth_router
)
from api.routes.project import (
    router as project_router
)
from api.routes.audit import (
    router as audit_router
)
from api.routes.catalog import (
    router as catalog_router
)
from services.material_import_queue_service import (
    start_material_import_queue_loop,
    stop_material_import_queue_loop,
)

load_dotenv()
init_database()

app = FastAPI(

    title="Furniture Platform API"
)


@app.on_event("startup")
async def startup_background_services():

    start_material_import_queue_loop()


@app.on_event("shutdown")
async def shutdown_background_services():

    stop_material_import_queue_loop()

frontend_origins = [

    origin.strip()

    for origin in os.getenv(

        "FRONTEND_ORIGINS",

        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175,http://localhost:4175,http://127.0.0.1:4175,http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")

    if origin.strip()
]

app.add_middleware(

    CORSMiddleware,

    allow_origins=frontend_origins,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]
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

app.include_router(

    audit_router,

    prefix="/audit",

    tags=["Audit"]
)

app.include_router(

    catalog_router,

    prefix="/catalog",

    tags=["Catalog"]
)
