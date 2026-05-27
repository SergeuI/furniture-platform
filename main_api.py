import os

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware
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

app = FastAPI(

    title="Furniture Platform API"
)

frontend_origins = [

    origin.strip()

    for origin in os.getenv(

        "FRONTEND_ORIGINS",

        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:3000,http://127.0.0.1:3000"
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
