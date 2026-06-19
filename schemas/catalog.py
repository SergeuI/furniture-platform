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


class MaterialEdgePriceSchema(BaseModel):
    city: str | None = None
    price: float | None = None


class MaterialEdgeOptionSchema(BaseModel):
    id: str
    edge_key: str
    label: str | None = None
    article: str | None = None
    name: str | None = None
    thickness: str | None = None
    image: str | None = None
    has_cached_image: bool = False
    source_url: str | None = None
    source_site: str | None = None
    current_price: float | None = None
    current_price_city: str | None = None
    prices: List[MaterialEdgePriceSchema] = Field(default_factory=list)


class MaterialCatalogItemSchema(BaseModel):
    id: str
    article: str
    display_article: str | None = None
    name: str | None = None
    description: str | None = None
    color: str | None = None
    dimensions: str | None = None
    thickness: str | None = None
    category: str | None = None
    image: str | None = None
    source_url: str | None = None
    source_site: str | None = None
    tg_file_id: str | None = None
    owner_user_id: str | None = None
    is_default: bool = False
    has_cached_image: bool = False
    current_price: float | None = None
    current_price_city: str | None = None
    current_price_exact: bool = True
    prices: List[MaterialPriceSchema] = Field(default_factory=list)
    edge_options: List[MaterialEdgeOptionSchema] = Field(default_factory=list)


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
    force_refresh: bool = False


class MaterialCatalogCreateSchema(BaseModel):
    article: str | None = Field(
        default=None,
        max_length=128,
    )
    name: str | None = Field(
        default=None,
        max_length=255,
    )
    category: str = Field(
        default="dsp",
        min_length=2,
        max_length=64,
    )
    city: str | None = Field(
        default=None,
        max_length=128,
    )
    price: float | None = None
    source_url: str | None = Field(
        default=None,
        max_length=1000,
    )
    image_url: str | None = Field(
        default=None,
        max_length=500000,
    )
    is_default: bool = False


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


class MaterialEdgeAttachSchema(BaseModel):
    edge_key: str = Field(
        min_length=2,
        max_length=32,
    )
    source_url: str = Field(
        min_length=8,
        max_length=1000,
    )
    city: str | None = Field(
        default=None,
        max_length=128,
    )


class MaterialEdgeOperationResponseSchema(BaseModel):
    success: bool
    item: MaterialCatalogItemSchema | None = None
    error: str | None = None


class FittingCatalogItemSchema(BaseModel):
    id: str
    city: str | None = None
    code: str | None = None
    article: str | None = None
    name: str | None = None
    price: float | None = None
    stock: str | None = None
    fitting_type: str | None = None
    fitting_type_name: str | None = None
    fitting_group: str | None = None
    fitting_group_name: str | None = None
    fitting_description: str | None = None
    image_url: str | None = None
    has_cached_image: bool = False
    source_url: str | None = None
    source_site: str | None = None
    owner_user_id: str | None = None
    is_system: bool = True
    is_active: bool = True
    sort_order: int = 0


class FittingCategorySchema(BaseModel):
    code: str
    name: str
    group: str
    group_name: str
    description: str | None = None
    icon_key: str | None = None
    item_count: int = 0


class FittingCatalogCreateSchema(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
    )
    article: str | None = Field(
        default=None,
        max_length=128,
    )
    code: str | None = Field(
        default=None,
        max_length=128,
    )
    city: str | None = Field(
        default=None,
        max_length=128,
    )
    price: float | None = None
    stock: str | None = Field(
        default=None,
        max_length=255,
    )
    fitting_type: str = Field(
        min_length=2,
        max_length=64,
    )
    fitting_group: str = Field(
        min_length=2,
        max_length=64,
    )
    image_url: str | None = Field(
        default=None,
        max_length=500000,
    )
    source_url: str | None = Field(
        default=None,
        max_length=1000,
    )
    is_active: bool = True
    sort_order: int = 0
    is_system: bool = False


class FittingCatalogUpdateSchema(FittingCatalogCreateSchema):
    pass


class FittingCatalogOperationResponseSchema(BaseModel):
    success: bool
    item: FittingCatalogItemSchema | None = None
    error: str | None = None


class FittingCatalogListResponseSchema(BaseModel):
    success: bool
    city_options: List[str] = Field(default_factory=list)
    selected_city: str | None = None
    categories: List[FittingCategorySchema] = Field(default_factory=list)
    items: List[FittingCatalogItemSchema] = Field(default_factory=list)
    error: str | None = None


class CatalogAutoRefreshStatusSchema(BaseModel):
    loop_running: bool = False
    interval_seconds: int = 0
    stale_hours: int = 0
    service_catalog_hours: int = 0
    last_cycle_started_at: datetime | None = None
    last_cycle_finished_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_service_catalog_sync_at: datetime | None = None
    material_jobs_queued: int = 0
    service_users_synced: int = 0
    service_catalog_synced: bool = False


class CatalogAutoRefreshStatusResponseSchema(BaseModel):
    success: bool
    status: CatalogAutoRefreshStatusSchema
    error: str | None = None


ServiceCatalogNodeSchema.model_rebuild()
