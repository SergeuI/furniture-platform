from typing import List

from pydantic import (
    BaseModel,
    Field
)


class CatalogItemSchema(BaseModel):
    id: str
    category: str
    value: str
    sort_order: int
    is_active: bool


class CatalogItemCreateSchema(BaseModel):
    category: str = Field(
        min_length=2,
        max_length=64
    )
    value: str = Field(
        min_length=1,
        max_length=128
    )
    sort_order: int = 0


class CatalogItemUpdateSchema(BaseModel):
    value: str = Field(
        min_length=1,
        max_length=128
    )
    sort_order: int = 0


class CatalogItemActiveSchema(BaseModel):
    is_active: bool


class CatalogItemListResponseSchema(BaseModel):
    success: bool
    items: List[CatalogItemSchema]
    error: str | None = None


class CatalogItemOperationResponseSchema(BaseModel):
    success: bool
    item: CatalogItemSchema | None = None
    error: str | None = None


class SpecificationCatalogResponseSchema(BaseModel):
    success: bool
    project_types: List[str]
    slide_types: List[str]
    bottom_types: List[str]
    material_thicknesses: List[int]
    edge_bandings: List[str]
    handle_positions: List[str]
