from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProcessingOperationTypeCapabilitiesSchema(BaseModel):
    template_editor: bool = False
    operations_preview: bool = False
    preview_3d: bool = False
    service_mapping: bool = False
    estimate_export: bool = False
    cutting_effect: bool = False


class ProcessingOperationTypeSchema(BaseModel):
    key: str
    name: str
    description: str
    category: Literal["drilling", "routing", "contour", "manual"]
    status: Literal["available", "planned", "needs_configuration"]
    geometry_kind: str
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    pricing_units: list[str] = Field(default_factory=list)
    capabilities: ProcessingOperationTypeCapabilitiesSchema
    version: int = 1


class ProcessingOperationTypeListResponseSchema(BaseModel):
    success: bool
    items: list[ProcessingOperationTypeSchema] = Field(default_factory=list)
    count: int = 0
    error: str | None = None
