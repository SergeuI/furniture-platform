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

    facade_edge_banding: Optional[str] = None

    inside_edge_banding: Optional[str] = None

    edge_banding: Optional[str] = None

    edge_overrides: Dict[str, Any] = Field(
        default_factory=dict
    )

    machining_overrides: Dict[str, Any] = Field(
        default_factory=dict
    )

    facade_thickness: Optional[int] = None

    inside_thickness: Optional[int] = None

    material_thickness: Optional[int] = None

    slide_type: Optional[str] = None

    bottom_type: Optional[str] = None

    handle_type: Optional[str] = None

    handle_position: Optional[str] = None

    notes: Optional[str] = None

    created_by_user_id: Optional[str] = None

    updated_by_user_id: Optional[str] = None

    assembly_layout: Dict[str, Any] = Field(
        default_factory=dict
    )

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

    facade_edge_banding: Optional[str] = None

    inside_edge_banding: Optional[str] = None

    edge_banding: Optional[str] = None

    edge_overrides: Dict[str, Any] = Field(
        default_factory=dict
    )

    machining_overrides: Dict[str, Any] = Field(
        default_factory=dict
    )

    facade_thickness: Optional[int] = None

    inside_thickness: Optional[int] = None

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

    errors: List[str] = Field(
        default_factory=list
    )


class ProjectListResponseSchema(BaseModel):

    success: bool

    total: int

    limit: int

    offset: int

    projects: List[ProjectResponseItemSchema]


class ProjectQuotaItemResponseSchema(BaseModel):

    usage: int

    limit: Optional[int] = None

    is_unlimited: bool = False

    can_create: bool = False


class ProjectQuotaResponseSchema(BaseModel):

    success: bool

    project_quota: ProjectQuotaItemResponseSchema


class ProjectHistoryResponseSchema(BaseModel):

    success: bool

    project_id: Optional[str] = None

    versions: List[ProjectVersionResponseItemSchema] = Field(
        default_factory=list
    )

    error: Optional[str] = None


class ProjectBomItemResponseSchema(BaseModel):

    part_name: str

    category: str

    quantity: int

    material: Optional[str] = None

    thickness: Optional[int] = None

    edge_banding: Optional[str] = None

    notes: Optional[str] = None


class ProjectBomServicePriceItemResponseSchema(BaseModel):

    id: str

    source: str

    name: str

    article: Optional[str] = None

    folder_path: Optional[str] = None

    unit: Optional[str] = None

    base_price: Optional[float] = None

    effective_price: Optional[float] = None

    currency: Optional[str] = None

    effective_currency: Optional[str] = None

    user_price: Optional[float] = None

    user_currency: Optional[str] = None

    user_last_synced_at: Optional[datetime] = None

    user_price_sync_status: Optional[str] = None


class ProjectBomPricingCatalogResponseSchema(BaseModel):

    viyar_services: List[ProjectBomServicePriceItemResponseSchema] = Field(
        default_factory=list
    )

    manual_services: List[ProjectBomServicePriceItemResponseSchema] = Field(
        default_factory=list
    )

    total_services: int = 0

    priced_services: int = 0


class ProjectBomRequirementItemResponseSchema(BaseModel):

    category: str

    code: str

    name: str

    unit: Optional[str] = None

    quantity: float | int

    meta: Dict[str, Any] = Field(
        default_factory=dict
    )

    match_terms: List[str] = Field(
        default_factory=list
    )


class ProjectBomRequirementsSummaryResponseSchema(BaseModel):

    operations_count: int = 0

    fittings_count: int = 0

    total_cut_area_m2: float = 0

    total_cut_length_m: float = 0

    total_edge_length_m: float = 0

    total_parts: int = 0


class ProjectBomRequirementsResponseSchema(BaseModel):

    operations: List[ProjectBomRequirementItemResponseSchema] = Field(
        default_factory=list
    )

    fittings: List[ProjectBomRequirementItemResponseSchema] = Field(
        default_factory=list
    )

    summary: ProjectBomRequirementsSummaryResponseSchema = Field(
        default_factory=ProjectBomRequirementsSummaryResponseSchema
    )


class ProjectBomResponseSchema(BaseModel):

    success: bool

    project_id: Optional[str] = None

    items: List[ProjectBomItemResponseSchema] = Field(
        default_factory=list
    )

    pricing_catalog: ProjectBomPricingCatalogResponseSchema = Field(
        default_factory=ProjectBomPricingCatalogResponseSchema
    )

    service_requirements: ProjectBomRequirementsResponseSchema = Field(
        default_factory=ProjectBomRequirementsResponseSchema
    )

    error: Optional[str] = None


class ProjectCuttingItemResponseSchema(BaseModel):

    export_code: str

    part_name: str

    category: str

    width: int

    height: int

    quantity: int

    material: Optional[str] = None

    thickness: Optional[int] = None

    edge_top: Optional[str] = None

    edge_bottom: Optional[str] = None

    edge_left: Optional[str] = None

    edge_right: Optional[str] = None

    grain_direction: Optional[str] = None

    notes: Optional[str] = None


class ProjectCuttingSummaryResponseSchema(BaseModel):

    total_parts: int

    total_area_m2: float

    total_cut_length_m: float

    total_edge_length_m: float


class ProjectCuttingResponseSchema(BaseModel):

    success: bool

    project_id: Optional[str] = None

    items: List[ProjectCuttingItemResponseSchema] = Field(
        default_factory=list
    )

    assembly: Dict[str, Any] = Field(
        default_factory=dict
    )

    summary: Optional[ProjectCuttingSummaryResponseSchema] = None

    error: Optional[str] = None


class ProjectCuttingExportFormatResponseSchema(BaseModel):

    format: str

    label: str

    status: str

    description: Optional[str] = None


class ProjectCuttingExportFormatsResponseSchema(BaseModel):

    success: bool

    project_id: Optional[str] = None

    formats: List[ProjectCuttingExportFormatResponseSchema] = Field(
        default_factory=list
    )

    error: Optional[str] = None


class ProjectCuttingJsonExportResponseSchema(BaseModel):

    success: bool

    project_id: Optional[str] = None

    export: Dict[str, Any] = Field(
        default_factory=dict
    )

    error: Optional[str] = None


class ProjectPartEdgeResponseSchema(BaseModel):

    side: str

    material: str

    length: int


class ProjectPartHoleResponseSchema(BaseModel):

    number: int

    side: str

    origin: str

    x: float

    y: float

    z: float

    diameter: float

    depth: float

    type: str


class ProjectPartGrooveResponseSchema(BaseModel):

    number: int

    side: str

    origin: str

    x: float

    y: float

    depth: float

    width: float

    length: float

    type: str


class ProjectPartQuarterResponseSchema(BaseModel):

    number: int

    side: str

    origin: str

    x: float

    y: float

    depth: float

    width: float

    length: float

    radius: float

    type: str


class ProjectPartDetailResponseSchema(BaseModel):

    success: bool

    project_id: Optional[str] = None

    part: Optional[ProjectCuttingItemResponseSchema] = None

    edges: List[ProjectPartEdgeResponseSchema] = Field(
        default_factory=list
    )

    holes: List[ProjectPartHoleResponseSchema] = Field(
        default_factory=list
    )

    grooves: List[ProjectPartGrooveResponseSchema] = Field(
        default_factory=list
    )

    quarters: List[ProjectPartQuarterResponseSchema] = Field(
        default_factory=list
    )

    error: Optional[str] = None


class DeleteProjectResponseSchema(BaseModel):

    success: bool

    deleted_project_id: Optional[str] = None

    error: Optional[str] = None
