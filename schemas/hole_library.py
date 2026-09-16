from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HoleLibraryServiceItemSchema(BaseModel):
    id: str
    source: str | None = None
    external_code: str | None = None
    article: str | None = None
    name: str | None = None
    is_active: bool = True


class HoleLibraryServiceDrillingRuleSchema(BaseModel):
    id: int
    rule_name: str
    operation_type: str
    hole_type: str
    allowed_diameters: list[float] = Field(default_factory=list)
    allowed_depths: list[float] = Field(default_factory=list)
    is_active: bool = True


class HoleLibraryServiceMappingSchema(BaseModel):
    id: int
    hole_type_id: int
    supplier_code: str
    service_external_code: str
    service_article: str | None = None
    service_catalog_item_id: str | None = None
    service_drilling_rule_id: int | None = None
    mapping_status: str
    notes: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
    service_catalog_item: HoleLibraryServiceItemSchema | None = None
    service_drilling_rule: HoleLibraryServiceDrillingRuleSchema | None = None


class HoleLibraryTypeSchema(BaseModel):
    id: int
    code: str
    name: str
    owner_user_id: str | None = None
    is_system: bool = True
    operation_type: str
    surface_type: str
    diameter_mm: float | None = None
    depth_mode: str
    fixed_depth_mm: float | None = None
    min_depth_mm: float | None = None
    max_depth_mm: float | None = None
    material_depth_offset_mm: float | None = None
    is_countersink: bool = False
    notes: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
    primary_mapping: HoleLibraryServiceMappingSchema | None = None
    mappings: list[HoleLibraryServiceMappingSchema] = Field(default_factory=list)


class HoleLibraryListResponseSchema(BaseModel):
    success: bool
    items: list[HoleLibraryTypeSchema] = Field(default_factory=list)
    count: int = 0
    error: str | None = None


class HoleLibraryOperationResponseSchema(BaseModel):
    success: bool
    item: HoleLibraryTypeSchema | None = None
    error: str | None = None


class HoleLibraryUpdateSchema(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    owner_user_id: str | None = Field(default=None, max_length=255)
    is_system: bool | None = None
    operation_type: str | None = Field(default=None, min_length=1, max_length=64)
    surface_type: str | None = Field(default=None, min_length=1, max_length=32)
    diameter_mm: float | None = None
    depth_mode: str | None = Field(default=None, min_length=1, max_length=32)
    fixed_depth_mm: float | None = None
    min_depth_mm: float | None = None
    max_depth_mm: float | None = None
    material_depth_offset_mm: float | None = None
    is_countersink: bool | None = None
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None


class HoleLibraryCreateSchema(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    owner_user_id: str | None = Field(default=None, max_length=255)
    is_system: bool = True
    operation_type: str = Field(min_length=1, max_length=64)
    surface_type: str = Field(min_length=1, max_length=32)
    diameter_mm: float | None = None
    depth_mode: str = Field(min_length=1, max_length=32)
    fixed_depth_mm: float | None = None
    min_depth_mm: float | None = None
    max_depth_mm: float | None = None
    material_depth_offset_mm: float | None = None
    is_countersink: bool = False
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool = True
