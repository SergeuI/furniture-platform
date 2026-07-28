from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from schemas.project_response import ProjectCuttingItemResponseSchema
from schemas.fitting_holes import FittingHoleTemplateResponse


class ProcessingOperationPlacementSchema(BaseModel):
    x_mm: float | None = None
    y_mm: float | None = None
    z_mm: float | None = None
    target_panel: str | None = None
    target_surface: str | None = None
    target_side: str | None = None
    side: str | None = None
    coordinate_system: str | None = None
    mounting_variant_key: str | None = None


class ProcessingOperationGeometrySchema(BaseModel):
    diameter_mm: float | None = None
    depth_mm: float | None = None
    is_through: bool | None = None
    operation: str | None = None


class ProcessingOperationServiceMappingSchema(BaseModel):
    service_drilling_rule_id: int | None = None
    resolved_service_catalog_item_id: str | None = None
    resolution_source: str | None = None
    found: bool = False


class ProcessingOperationProductionEffectsSchema(BaseModel):
    affects_cutting: bool = False
    affects_finished_contour: bool = False
    affects_edge_banding: bool = False
    requires_cnc: bool = False
    include_in_estimate: bool = True


class ProcessingOperationMetadataSchema(BaseModel):
    source_label: str | None = None
    template_notes: str | None = None
    point_notes: str | None = None
    fitting_code: str | None = None
    fitting_article: str | None = None
    fitting_category_code: str | None = None
    bundle_key: str | None = None
    bundle_name: str | None = None
    target_panel: str | None = None
    target_surface: str | None = None
    target_side: str | None = None
    source_data: dict[str, Any] = Field(default_factory=dict)


class ProcessingOperationSchema(BaseModel):
    id: int | str | None = None
    operation_type: str
    source_type: str
    source_id: int | str | None = None
    template_id: int | str | None = None
    label: str | None = None
    placement: ProcessingOperationPlacementSchema
    geometry: ProcessingOperationGeometrySchema
    quantity: int = 1
    mirrored: bool = False
    order_index: int = 0
    service_mapping: ProcessingOperationServiceMappingSchema
    production_effects: ProcessingOperationProductionEffectsSchema
    metadata: ProcessingOperationMetadataSchema


class ProcessingOperationPreviewResponseSchema(BaseModel):
    success: bool
    template: FittingHoleTemplateResponse | None = None
    operations: list[ProcessingOperationSchema] = Field(default_factory=list)
    error: str | None = None


class ProcessingProjectPreviewSchema(BaseModel):
    id: int | str | None = None


class ProcessingProjectPartOperationPlacementSchema(BaseModel):
    x_mm: float | None = None
    y_mm: float | None = None
    z_mm: float | None = None
    target_panel: str | None = None
    target_surface: str | None = None
    target_side: str | None = None
    side: str | None = None
    coordinate_system: str | None = None
    mounting_variant_key: str | None = None


class ProcessingProjectPartOperationGeometrySchema(BaseModel):
    diameter_mm: float | None = None
    depth_mm: float | None = None
    is_through: bool | None = None
    operation: str | None = None
    length_mm: float | None = None
    width_mm: float | None = None
    direction: str | None = None
    end_radius_mm: float | None = None
    edge: str | None = None
    start_offset_mm: float | None = None
    end_offset_mm: float | None = None
    radius_mm: float | None = None


class ProcessingProjectPartOperationServiceMappingSchema(BaseModel):
    service_drilling_rule_id: int | None = None
    resolved_service_catalog_item_id: str | None = None
    resolution_source: str | None = None
    found: bool = False


class ProcessingProjectPartOperationProductionEffectsSchema(BaseModel):
    affects_cutting: bool = False
    affects_finished_contour: bool = False
    affects_edge_banding: bool = False
    requires_cnc: bool = False
    include_in_estimate: bool = False


class ProcessingProjectPartOperationMetadataSchema(BaseModel):
    project_id: int | str | None = None
    part_identifier: str | None = None
    part_key: str | None = None
    part_type: str | None = None
    part_name: str | None = None
    source_index: int | None = None
    source_data: dict[str, Any] = Field(default_factory=dict)


class ProcessingProjectPartOperationSchema(BaseModel):
    id: int | str | None = None
    operation_type: str
    source_type: str
    source_id: int | str | None = None
    template_id: int | str | None = None
    label: str | None = None
    placement: ProcessingProjectPartOperationPlacementSchema
    geometry: ProcessingProjectPartOperationGeometrySchema
    quantity: int = 1
    mirrored: bool = False
    order_index: int = 0
    service_mapping: ProcessingProjectPartOperationServiceMappingSchema
    production_effects: ProcessingProjectPartOperationProductionEffectsSchema
    metadata: ProcessingProjectPartOperationMetadataSchema


class ProcessingProjectPartOperationPreviewResponseSchema(BaseModel):
    success: bool
    project: ProcessingProjectPreviewSchema | None = None
    part: ProjectCuttingItemResponseSchema | None = None
    operations: list[ProcessingProjectPartOperationSchema] = Field(default_factory=list)
    count: int = 0
    error: str | None = None
