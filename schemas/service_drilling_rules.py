from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ServiceDrillingRuleBaseSchema(BaseModel):
    service_catalog_item_id: str = Field(
        min_length=1,
        max_length=64,
    )
    rule_name: str = Field(
        min_length=1,
        max_length=255,
    )
    operation_type: str = Field(
        min_length=1,
        max_length=64,
    )
    hole_type: str = Field(
        min_length=1,
        max_length=64,
    )
    allowed_diameters: list[float] = Field(
        default_factory=list,
    )
    allowed_depths: list[float] = Field(
        default_factory=list,
    )
    material_thickness_min: float | None = None
    material_thickness_max: float | None = None
    max_blind_depth_formula: str | None = Field(
        default=None,
        max_length=255,
    )
    max_blind_depth_mm: float | None = None
    min_edge_offset_mm: float | None = None
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )
    source: str | None = Field(
        default=None,
        max_length=64,
    )
    is_active: bool = True


class ServiceDrillingRuleCreateSchema(ServiceDrillingRuleBaseSchema):
    pass


class ServiceDrillingRuleUpdateSchema(BaseModel):
    service_catalog_item_id: str | None = Field(
        default=None,
        max_length=64,
    )
    rule_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    operation_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    hole_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    allowed_diameters: list[float] | None = None
    allowed_depths: list[float] | None = None
    material_thickness_min: float | None = None
    material_thickness_max: float | None = None
    max_blind_depth_formula: str | None = Field(
        default=None,
        max_length=255,
    )
    max_blind_depth_mm: float | None = None
    min_edge_offset_mm: float | None = None
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )
    source: str | None = Field(
        default=None,
        max_length=64,
    )
    is_active: bool | None = None


class ServiceDrillingServiceCatalogItemSchema(BaseModel):
    id: str
    canonical_service_catalog_item_id: str
    source: str | None = None
    external_code: str | None = None
    parent_external_code: str | None = None
    name: str | None = None
    article: str | None = None
    folder_path: str | None = None
    base_price: float | None = None
    currency: str | None = None
    is_active: bool = True


class ServiceDrillingRuleResponseSchema(BaseModel):
    id: int
    service_catalog_item_id: str
    rule_name: str
    operation_type: str
    hole_type: str
    allowed_diameters: list[float] = Field(default_factory=list)
    allowed_depths: list[float] = Field(default_factory=list)
    material_thickness_min: float | None = None
    material_thickness_max: float | None = None
    max_blind_depth_formula: str | None = None
    max_blind_depth_mm: float | None = None
    min_edge_offset_mm: float | None = None
    notes: str | None = None
    source: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
    service_catalog_item: ServiceDrillingServiceCatalogItemSchema | None = None


class ServiceDrillingRuleListResponseSchema(BaseModel):
    success: bool
    rules: list[ServiceDrillingRuleResponseSchema] = Field(default_factory=list)
    error: str | None = None


class ServiceDrillingRuleOperationResponseSchema(BaseModel):
    success: bool
    rule: ServiceDrillingRuleResponseSchema | None = None
    error: str | None = None


class ServiceDrillingAvailableServicesResponseSchema(BaseModel):
    success: bool
    category: str | None = None
    items: list[ServiceDrillingServiceCatalogItemSchema] = Field(default_factory=list)
    error: str | None = None
