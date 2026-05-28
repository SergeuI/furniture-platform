from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from datetime import datetime

from pydantic import (
    BaseModel,
    Field
)


# =====================================================
# PROJECT DATA
# =====================================================

class ProjectResponseItemSchema(BaseModel):

    id: str

    width: int

    height: int

    depth: int

    sections: int

    drawers: List[int]

    project_name: Optional[str] = None

    project_type: Optional[str] = None

    client_name: Optional[str] = None

    room_name: Optional[str] = None

    facade_material: Optional[str] = None

    inside_material: Optional[str] = None

    edge_banding: Optional[str] = None

    material_thickness: Optional[int] = None

    slide_type: Optional[str] = None

    bottom_type: Optional[str] = None

    handle_type: Optional[str] = None

    handle_position: Optional[str] = None

    notes: Optional[str] = None

    created_by_user_id: Optional[str] = None

    updated_by_user_id: Optional[str] = None

    created_at: Optional[datetime] = None

    updated_at: Optional[datetime] = None


class ProjectVersionResponseItemSchema(BaseModel):

    id: str

    width: int

    height: int

    depth: int

    sections: int

    drawers: List[int]

    project_name: Optional[str] = None

    project_type: Optional[str] = None

    client_name: Optional[str] = None

    room_name: Optional[str] = None

    facade_material: Optional[str] = None

    inside_material: Optional[str] = None

    edge_banding: Optional[str] = None

    material_thickness: Optional[int] = None

    slide_type: Optional[str] = None

    bottom_type: Optional[str] = None

    handle_type: Optional[str] = None

    handle_position: Optional[str] = None

    notes: Optional[str] = None

    created_at: Optional[datetime] = None


# =====================================================
# PROJECT RESPONSES
# =====================================================

class GenerateProjectResponseSchema(BaseModel):

    success: bool

    errors: List[str] = Field(
        default_factory=list
    )

    result: Dict[str, Any] = Field(
        default_factory=dict
    )


class ProjectDetailResponseSchema(BaseModel):

    success: bool

    project: Optional[ProjectResponseItemSchema] = None

    error: Optional[str] = None


class ProjectListResponseSchema(BaseModel):

    success: bool

    total: int

    limit: int

    offset: int

    projects: List[ProjectResponseItemSchema]


class ProjectHistoryResponseSchema(BaseModel):

    success: bool

    project_id: Optional[str] = None

    versions: List[ProjectVersionResponseItemSchema] = Field(
        default_factory=list
    )

    error: Optional[str] = None


class DeleteProjectResponseSchema(BaseModel):

    success: bool

    deleted_project_id: Optional[str] = None

    error: Optional[str] = None
