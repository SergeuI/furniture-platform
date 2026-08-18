import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware
)
from fastapi.staticfiles import StaticFiles
import uvicorn
from dotenv import load_dotenv

load_dotenv()

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
from api.routes.admin_entitlements import (
    router as admin_entitlements_router,
)
from api.routes.fitting_holes import (
    router as fitting_holes_router
)
from api.routes.mounting_nodes import (
    router as mounting_nodes_router
)
from api.routes.mounting_schemes import (
    router as mounting_schemes_router
)
from api.routes.processing import (
    router as processing_router
)
from api.routes.service_drilling_rules import (
    router as service_drilling_rules_router
)
from services.material_import_queue_service import (
    start_material_import_queue_loop,
    stop_material_import_queue_loop,
)
init_database()

app = FastAPI(

    title="Furniture Platform API"
)

uploads_root = Path("data/uploads")
uploads_root.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_root.as_posix()), name="uploads")


@app.get("/health")
async def health_check():
    return {
        "success": True,
        "status": "ok",
    }


@app.on_event("startup")
async def startup_background_services():

    start_material_import_queue_loop()


@app.on_event("shutdown")
async def shutdown_background_services():

    stop_material_import_queue_loop()


default_frontend_origins = {
    "http://45.94.157.42",
    "https://45.94.157.42",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:4175",
    "http://127.0.0.1:4175",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}
configured_frontend_origins = {
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
}
frontend_origins = sorted(default_frontend_origins | configured_frontend_origins)

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

app.include_router(

    admin_entitlements_router,

    prefix="/admin/entitlements",

    tags=["Admin Entitlements"]
)

app.include_router(

    fitting_holes_router,

    prefix="/fitting-holes",

    tags=["Fitting Holes"]
)

app.include_router(

    mounting_nodes_router,

    prefix="/mounting-nodes",

    tags=["Mounting Nodes"]
)

app.include_router(

    mounting_schemes_router,

    prefix="/mounting-schemes",

    tags=["Mounting Schemes"]
)

app.include_router(

    processing_router,

    prefix="/processing",

    tags=["Processing"]
)

app.include_router(

    service_drilling_rules_router,

    prefix="/service-drilling-rules",

    tags=["Service Drilling Rules"]
)


if __name__ == "__main__":
    uvicorn.run(
        "main_api:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=False,
        log_level=os.getenv("API_LOG_LEVEL", "info").lower(),
    )
