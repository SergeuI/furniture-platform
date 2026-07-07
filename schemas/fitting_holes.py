from __future__ import annotations

from typing import List

from pydantic import (
    BaseModel,
    Field,
)


class FittingHoleTemplateCreate(BaseModel):
    fitting_id: int
    name: str = Field(
        min_length=1,
        max_length=255,
    )
    bundle_key: str | None = Field(
        default=None,
        max_length=64,
    )
    bundle_name: str | None = Field(
        default=None,
        max_length=255,
    )
    bundle_order_index: int = 0
    template_type: str | None = Field(
        default=None,
        max_length=64,
    )
    side: str | None = Field(
        default=None,
        max_length=64,
    )
    coordinate_system: str | None = Field(
        default=None,
        max_length=64,
    )
    mounting_variant_key: str = Field(
        default="surface_mount",
        max_length=64,
    )
    is_default: bool = False
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )
    is_active: bool = True


class FittingHoleTemplateUpdate(BaseModel):
    fitting_id: int | None = None
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    bundle_key: str | None = Field(
        default=None,
        max_length=64,
    )
    bundle_name: str | None = Field(
        default=None,
        max_length=255,
    )
    bundle_order_index: int | None = None
    template_type: str | None = Field(
        default=None,
        max_length=64,
    )
    side: str | None = Field(
        default=None,
        max_length=64,
    )
    coordinate_system: str | None = Field(
        default=None,
        max_length=64,
    )
    mounting_variant_key: str | None = Field(
        default=None,
        max_length=64,
    )
    is_default: bool | None = None
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )
    is_active: bool | None = None


class FittingHoleTemplateResponse(BaseModel):
    id: int
    fitting_id: int
    name: str | None = None
    bundle_key: str | None = None
    bundle_name: str | None = None
    bundle_order_index: int = 0
    template_type: str | None = None
    side: str | None = None
    coordinate_system: str | None = None
    mounting_variant_key: str = "surface_mount"
    is_default: bool = False
    notes: str | None = None
    is_active: bool = True


class FittingHoleTemplateListResponseSchema(BaseModel):
    success: bool
    fitting_id: int | None = None
    templates: List[FittingHoleTemplateResponse] = Field(
        default_factory=list
    )
    error: str | None = None


class FittingHoleTemplateOperationResponseSchema(BaseModel):
    success: bool
    template: FittingHoleTemplateResponse | None = None
    error: str | None = None


class FittingHoleBundleResponseSchema(BaseModel):
    success: bool
    bundle_key: str | None = None
    bundle_name: str | None = None
    templates: List[FittingHoleTemplateResponse] = Field(
        default_factory=list
    )
    error: str | None = None


class FittingHoleBundleListItemSchema(BaseModel):
    bundle_key: str
    bundle_name: str | None = None
    template_count: int = 0


class FittingHoleBundleListResponseSchema(BaseModel):
    success: bool
    bundles: List[FittingHoleBundleListItemSchema] = Field(
        default_factory=list
    )
    error: str | None = None


class FittingHolePointCreate(BaseModel):
    template_id: int | None = None
    label: str | None = Field(
        default=None,
        max_length=255,
    )
    x_mm: float | None = None
    y_mm: float | None = None
    z_mm: float | None = None
    diameter_mm: float
    depth_mm: float | None = None
    side: str | None = Field(
        default=None,
        max_length=64,
    )
    operation: str | None = Field(
        default=None,
        max_length=64,
    )
    order_index: int = 0
    quantity: int = 1
    mirrored: bool = False
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )


class FittingHolePointUpdate(BaseModel):
    template_id: int | None = None
    label: str | None = Field(
        default=None,
        max_length=255,
    )
    x_mm: float | None = None
    y_mm: float | None = None
    z_mm: float | None = None
    diameter_mm: float | None = None
    depth_mm: float | None = None
    side: str | None = Field(
        default=None,
        max_length=64,
    )
    operation: str | None = Field(
        default=None,
        max_length=64,
    )
    order_index: int | None = None
    quantity: int | None = None
    mirrored: bool | None = None
    notes: str | None = Field(
        default=None,
        max_length=5000,
    )


class FittingHolePointResponse(BaseModel):
    id: int
    template_id: int
    label: str | None = None
    x_mm: float | None = None
    y_mm: float | None = None
    z_mm: float | None = None
    diameter_mm: float | None = None
    depth_mm: float | None = None
    side: str | None = None
    operation: str | None = None
    order_index: int = 0
    quantity: int = 1
    mirrored: bool = False
    notes: str | None = None


class FittingHolePointListResponseSchema(BaseModel):
    success: bool
    template_id: int | None = None
    points: List[FittingHolePointResponse] = Field(
        default_factory=list
    )
    error: str | None = None


class FittingHolePointOperationResponseSchema(BaseModel):
    success: bool
    point: FittingHolePointResponse | None = None
    error: str | None = None
