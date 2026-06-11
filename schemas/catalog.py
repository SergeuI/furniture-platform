from datetime import datetime
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


class ServiceCatalogItemSchema(BaseModel):
    id: str
    source: str
    external_code: str
    parent_external_code: str | None = None
    owner_user_id: str | None = None
    name: str
    slug: str
    item_type: str
    folder_path: str | None = None
    description: str | None = None
    article: str | None = None
    unit: str | None = None
    base_price: float | None = None
    currency: str | None = None
    source_url: str | None = None
    is_calculable: bool
    sort_order: int
    is_active: bool
    last_synced_at: datetime | None = None
    price_sync_status: str | None = None
    price_source_label: str | None = None
    effective_price: float | None = None
    effective_currency: str | None = None
    user_price: float | None = None
    user_currency: str | None = None
    user_last_synced_at: datetime | None = None
    user_price_sync_status: str | None = None
    user_price_source_label: str | None = None


class ServiceCatalogNodeSchema(ServiceCatalogItemSchema):
    children: List["ServiceCatalogNodeSchema"] = Field(
        default_factory=list
    )


class ServiceCatalogTreeResponseSchema(BaseModel):
    success: bool
    source: str
    items: List[ServiceCatalogNodeSchema] = Field(
        default_factory=list
    )
    error: str | None = None


class ServiceCatalogSyncResponseSchema(BaseModel):
    success: bool
    source: str
    imported_count: int
    folder_count: int
    service_count: int
    fallback_only_import: bool = False
    items: List[ServiceCatalogNodeSchema] = Field(
        default_factory=list
    )
    error: str | None = None


class ServiceCatalogPriceSyncResponseSchema(BaseModel):
    success: bool
    source: str
    priced_count: int
    skipped_count: int
    auth_required: bool = False
    items: List[ServiceCatalogNodeSchema] = Field(
        default_factory=list
    )
    error: str | None = None


class ServiceCatalogItemUpdateSchema(BaseModel):
    unit: str | None = Field(
        default=None,
        max_length=64,
    )
    base_price: float | None = None
    is_calculable: bool
    is_active: bool


class ServiceCatalogOperationResponseSchema(BaseModel):
    success: bool
    item: ServiceCatalogItemSchema | None = None
    error: str | None = None


class ManualServiceCatalogItemCreateSchema(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=160,
    )
    article: str | None = Field(
        default=None,
        max_length=128,
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
    )
    unit: str | None = Field(
        default=None,
        max_length=64,
    )
    base_price: float | None = None
    is_calculable: bool = True
    is_active: bool = True


class ManualServiceCatalogItemUpdateSchema(ManualServiceCatalogItemCreateSchema):
    pass


class MaterialPriceSchema(BaseModel):
    city: str | None = None
    price: float | None = None


class MaterialCatalogItemSchema(BaseModel):
    id: str
    article: str
    name: str | None = None
    category: str | None = None
    image: str | None = None
    source_url: str | None = None
    tg_file_id: str | None = None
    is_default: bool = False
    current_price: float | None = None
    prices: List[MaterialPriceSchema] = Field(default_factory=list)


class MaterialCategorySchema(BaseModel):
    code: str
    name: str


class MaterialCatalogListResponseSchema(BaseModel):
    success: bool
    categories: List[MaterialCategorySchema] = Field(default_factory=list)
    city_options: List[str] = Field(default_factory=list)
    selected_city: str | None = None
    items: List[MaterialCatalogItemSchema] = Field(default_factory=list)
    error: str | None = None


class MaterialImportFromViyarSchema(BaseModel):
    article: str = Field(
        min_length=2,
        max_length=128,
    )
    category: str = Field(
        default="dsp",
        min_length=2,
        max_length=64,
    )
    source_url: str | None = Field(
        default=None,
        max_length=1000,
    )


class MaterialImportJobSchema(BaseModel):
    id: str
    article: str
    category: str
    city: str
    owner_user_id: str | None = None
    status: str
    attempt_count: int
    max_attempts: int
    next_retry_at: datetime | None = None
    last_error: str | None = None
    last_strategy: str | None = None
    last_source_url: str | None = None
    preferred_url: str | None = None
    debug_trace: List[dict] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None


class MaterialCatalogOperationResponseSchema(BaseModel):
    success: bool
    item: MaterialCatalogItemSchema | None = None
    job: MaterialImportJobSchema | None = None
    selected_city: str | None = None
    error: str | None = None


class FittingCatalogItemSchema(BaseModel):
    id: str
    city: str | None = None
    code: str | None = None
    article: str | None = None
    name: str | None = None
    price: float | None = None
    stock: str | None = None


class FittingCatalogListResponseSchema(BaseModel):
    success: bool
    items: List[FittingCatalogItemSchema] = Field(default_factory=list)
    error: str | None = None


ServiceCatalogNodeSchema.model_rebuild()
