from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MountingSchemeNodeCreateSchema(BaseModel):
    node_id: int
    group_key: str = Field(min_length=1, max_length=64)
    quantity_per_group: int = Field(default=1, ge=1)
    role_code: str | None = Field(default=None, max_length=64)
    order_index: int = 0
    is_required: bool = True


class MountingSchemeNodeReadSchema(BaseModel):
    id: int
    scheme_id: int
    node_id: int
    node_code: str | None = None
    node_name: str | None = None
    group_key: str
    quantity_per_group: int
    role_code: str | None = None
    order_index: int = 0
    is_required: bool = True


class MountingSchemePlacementRuleCreateSchema(BaseModel):
    group_key: str = Field(min_length=1, max_length=64)
    distribution_mode: str = Field(default="equal", max_length=32)
    min_group_count: int = Field(default=1, ge=1)
    max_group_count: int | None = Field(default=None, ge=1)
    fixed_group_count: int | None = Field(default=None, ge=1)
    start_offset_mm: int | None = Field(default=None, ge=0)
    end_offset_mm: int | None = Field(default=None, ge=0)
    max_spacing_mm: int | None = Field(default=None, gt=0)
    fixed_spacing_mm: int | None = Field(default=None, gt=0)


class MountingSchemePlacementRuleReadSchema(BaseModel):
    id: int
    scheme_id: int
    group_key: str
    distribution_mode: str
    min_group_count: int
    max_group_count: int | None = None
    fixed_group_count: int | None = None
    start_offset_mm: int | None = None
    end_offset_mm: int | None = None
    max_spacing_mm: int | None = None
    fixed_spacing_mm: int | None = None


class MountingSchemeCreateSchema(BaseModel):
    code: str | None = Field(default=None, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool = True
    nodes: list[MountingSchemeNodeCreateSchema] = Field(default_factory=list)
    placement_rules: list[MountingSchemePlacementRuleCreateSchema] = Field(default_factory=list)


class MountingSchemeUpdateSchema(BaseModel):
    code: str | None = Field(default=None, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None
    nodes: list[MountingSchemeNodeCreateSchema] | None = None
    placement_rules: list[MountingSchemePlacementRuleCreateSchema] | None = None


class MountingSchemeListItemSchema(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
    nodes_count: int = 0
    placement_rules_count: int = 0


class MountingSchemeDetailSchema(MountingSchemeListItemSchema):
    nodes: list[MountingSchemeNodeReadSchema] = Field(default_factory=list)
    placement_rules: list[MountingSchemePlacementRuleReadSchema] = Field(default_factory=list)


class MountingSchemeListResponseSchema(BaseModel):
    success: bool
    schemes: list[MountingSchemeListItemSchema] = Field(default_factory=list)
    error: str | None = None


class MountingSchemeDetailResponseSchema(BaseModel):
    success: bool
    scheme: MountingSchemeDetailSchema | None = None
    error: str | None = None


class MountingSchemeOperationResponseSchema(BaseModel):
    success: bool
    scheme: MountingSchemeDetailSchema | None = None
    error: str | None = None
