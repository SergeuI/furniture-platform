from __future__ import annotations

from datetime import date, datetime
from typing import List

from pydantic import (
    BaseModel,
    ConfigDict,
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
    full_description: str | None = None
    article: str | None = None
    unit: str | None = None
    base_price: float | None = None
    currency: str | None = None
    source_url: str | None = None
    rules_source_url: str | None = None
    rules_parsed_at: datetime | None = None
    rules_parse_status: str | None = None
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
    description_audit: ServiceCatalogDescriptionAuditSchema | None = None
    items: List[ServiceCatalogNodeSchema] = Field(
        default_factory=list
    )
    error: str | None = None


class ServiceCatalogDescriptionAuditSchema(BaseModel):
    total_services: int = 0
    with_source_url: int = 0
    with_short_description: int = 0
    with_only_short_description: int = 0
    with_full_description: int = 0
    with_description_marker: int = 0
    no_full_description: int = 0
    without_full_description: int = 0
    without_description_marker: int = 0
    needs_review: int = 0
    failed_downloads: int = 0
    categories: dict = Field(default_factory=dict)


class ServiceCatalogImportAuditSchema(BaseModel):
    total_records: int = 0
    valid_services: int = 0
    suspicious_records: int = 0
    records_without_article: int = 0
    records_without_price: int = 0
    filtered_service_rows: int = 0
    deactivated_suspicious_count: int = 0


class ServiceCatalogSyncResponseSchema(BaseModel):
    success: bool
    source: str
    imported_count: int
    folder_count: int
    service_count: int
    fallback_only_import: bool = False
    import_audit: ServiceCatalogImportAuditSchema | None = None
    description_audit: ServiceCatalogDescriptionAuditSchema | None = None
    description_backfill_audit: dict | None = None
    drilling_description_audit: dict | None = None
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
    currency: str | None = None
    availability: str | None = None
    old_price: float | None = None
    is_promo: bool = False
    discount_percent: float | None = None
    promo_label: str | None = None
    promo_valid_until: date | None = None
    source_checked_at: datetime | None = None
    updated_at: datetime | None = None


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
    current_price_details: MaterialPriceSchema | None = None
    prices: List[MaterialPriceSchema] = Field(default_factory=list)
    edge_options: List[MaterialEdgeOptionSchema] = Field(default_factory=list)


class MaterialCategorySchema(BaseModel):
    code: str
    name: str


class MaterialOwnershipQuotaSchema(BaseModel):
    owned_count: int = 0
    limit: int | None = None
    is_unlimited: bool = False
    can_create: bool = False


class MaterialOwnerSchema(BaseModel):
    id: str
    display_name: str | None = None
    login: str | None = None
    email: str


class MaterialOwnersResponseSchema(BaseModel):
    success: bool
    material_article: str | None = None
    owners_count: int = 0
    owners: List[MaterialOwnerSchema] = Field(default_factory=list)
    error: str | None = None


class MaterialCatalogListResponseSchema(BaseModel):
    success: bool
    categories: List[MaterialCategorySchema] = Field(default_factory=list)
    city_options: List[str] = Field(default_factory=list)
    selected_city: str | None = None
    material_quota: MaterialOwnershipQuotaSchema | None = None
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
        min_length=1,
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


class MaterialCatalogUpdateSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    name: str | None = Field(
        default=None,
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
    )
    color: str | None = Field(
        default=None,
        max_length=255,
    )
    dimensions: str | None = Field(
        default=None,
        max_length=255,
    )
    thickness: str | None = Field(
        default=None,
        max_length=255,
    )
    price: float | None = Field(
        default=None,
        ge=0,
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
    description: str | None = None
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
    owner_display_name: str | None = None
    owner_login: str | None = None
    owner_email: str | None = None
    technical_product_id: int | None = None
    is_system: bool = True
    is_active: bool = True
    sort_order: int = 0


class FittingCatalogImageSchema(BaseModel):
    id: int
    sort_order: int
    is_primary: bool
    content_type: str


class FittingSupplierSchema(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool = True


class FittingSupplierOfferInputSchema(BaseModel):
    offer_id: int | None = None
    supplier_id: int | None = None
    article: str | None = Field(default=None, max_length=128)
    external_product_id: str | None = Field(default=None, max_length=128)
    source_url: str | None = Field(default=None, max_length=1000)
    price: float | None = None
    currency: str | None = Field(default=None, max_length=16)
    unit: str | None = Field(default=None, max_length=32)
    stock: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    priority: int = 100


class FittingSupplierOfferSchema(FittingSupplierOfferInputSchema):
    id: int
    fitting_id: int
    supplier_code: str
    supplier_name: str


class FittingCatalogDetailItemSchema(FittingCatalogItemSchema):
    id: int
    brand: str | None = None
    currency: str | None = None
    unit: str | None = None
    availability: str | None = None
    characteristics: dict[str, str] = Field(default_factory=dict)
    images: List[FittingCatalogImageSchema] = Field(default_factory=list)
    supplier_offers: List[FittingSupplierOfferSchema] = Field(default_factory=list)
    parsed_at: datetime | None = None
    price_updated_at: datetime | None = None


class FittingCatalogDetailResponseSchema(BaseModel):
    success: bool
    item: FittingCatalogDetailItemSchema | None = None
    error: str | None = None


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
        default="",
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
    supplier_offer: FittingSupplierOfferInputSchema | None = None
    is_active: bool = True
    sort_order: int = 0
    is_system: bool = False


class FittingCatalogUpdateSchema(FittingCatalogCreateSchema):
    pass


class FittingSourcePreviewRequestSchema(BaseModel):
    source_url: str = Field(
        min_length=8,
        max_length=1000,
    )
    city: str | None = Field(
        default=None,
        max_length=128,
    )


class FittingSourcePreviewSupplierSchema(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool = True


class FittingSourcePreviewResponseSchema(BaseModel):
    success: bool
    source: str | None = None
    source_site: str | None = None
    source_url: str | None = None
    city: str | None = None
    name: str | None = None
    article: str | None = None
    brand: str | None = None
    image_url: str | None = None
    image_urls: List[str] = Field(default_factory=list)
    price: float | None = None
    availability: str | None = None
    currency: str | None = None
    unit: str | None = None
    supplier: FittingSourcePreviewSupplierSchema | None = None
    error: str | None = None


class FittingCatalogOperationResponseSchema(BaseModel):
    success: bool
    operation: str | None = None
    selected_item_id: str | None = None
    deleted_count: int = 0
    deleted_ids: List[str] = Field(default_factory=list)
    deleted_cities: List[str] = Field(default_factory=list)
    dependent_nodes: List[dict] = Field(default_factory=list)
    item: FittingCatalogDetailItemSchema | None = None
    error: str | None = None


class FittingSupplierListResponseSchema(BaseModel):
    success: bool
    items: List[FittingSupplierSchema] = Field(default_factory=list)
    error: str | None = None


class FittingSupplierOfferListResponseSchema(BaseModel):
    success: bool
    items: List[FittingSupplierOfferSchema] = Field(default_factory=list)
    error: str | None = None


class FittingSupplierOfferOperationResponseSchema(BaseModel):
    success: bool
    item: FittingSupplierOfferSchema | None = None
    error: str | None = None


class FittingCatalogListResponseSchema(BaseModel):
    success: bool
    city_options: List[str] = Field(default_factory=list)
    selected_city: str | None = None
    categories: List[FittingCategorySchema] = Field(default_factory=list)
    items: List[FittingCatalogItemSchema] = Field(default_factory=list)
    error: str | None = None


class FittingManufacturerSchema(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    website_url: str | None = None
    logo_url: str | None = None
    country_code: str | None = None
    is_active: bool = True
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FittingManufacturerCreateSchema(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    website_url: str | None = Field(default=None, max_length=1000)
    logo_url: str | None = Field(default=None, max_length=1000)
    country_code: str | None = Field(default=None, max_length=16)
    is_active: bool = True
    sort_order: int = 0


class FittingManufacturerUpdateSchema(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    website_url: str | None = Field(default=None, max_length=1000)
    logo_url: str | None = Field(default=None, max_length=1000)
    country_code: str | None = Field(default=None, max_length=16)
    is_active: bool = True
    sort_order: int = 0


class FittingSeriesSchema(BaseModel):
    id: int
    manufacturer_id: int
    code: str
    name: str
    description: str | None = None
    is_active: bool = True
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FittingSeriesCreateSchema(BaseModel):
    manufacturer_id: int
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True
    sort_order: int = 0


class FittingSeriesUpdateSchema(BaseModel):
    manufacturer_id: int
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True
    sort_order: int = 0


class FittingTaxonomyCategorySchema(BaseModel):
    id: int
    code: str
    name: str
    parent_id: int | None = None
    description: str | None = None
    is_active: bool = True
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FittingTaxonomyCategoryCreateSchema(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    parent_id: int | None = None
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True
    sort_order: int = 0


class FittingTaxonomyCategoryUpdateSchema(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    parent_id: int | None = None
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True
    sort_order: int = 0


class FittingProductSchema(BaseModel):
    id: int
    article: str | None = None
    code: str | None = None
    name: str
    brand: str | None = None
    description: str | None = None
    manufacturer_id: int | None = None
    series_id: int | None = None
    category_id: int | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FittingManufacturerListResponseSchema(BaseModel):
    success: bool
    items: List[FittingManufacturerSchema] = Field(default_factory=list)
    error: str | None = None


class FittingSeriesListResponseSchema(BaseModel):
    success: bool
    items: List[FittingSeriesSchema] = Field(default_factory=list)
    error: str | None = None


class FittingCategoryListResponseSchema(BaseModel):
    success: bool
    items: List[FittingTaxonomyCategorySchema] = Field(default_factory=list)
    error: str | None = None


class FittingProductListResponseSchema(BaseModel):
    success: bool
    items: List[FittingProductSchema] = Field(default_factory=list)
    error: str | None = None


class FittingProductDetailResponseSchema(BaseModel):
    success: bool
    item: FittingProductSchema | None = None
    error: str | None = None


class FittingProductTaxonomyUpdateSchema(BaseModel):
    manufacturer_id: int | None = None
    series_id: int | None = None
    category_id: int | None = None
    is_active: bool | None = None


class FittingProductTaxonomyOperationResponseSchema(BaseModel):
    success: bool
    item: FittingProductSchema | None = None
    dependent_nodes: List[dict] = Field(default_factory=list)
    error: str | None = None


class FittingManufacturerOperationResponseSchema(BaseModel):
    success: bool
    item: FittingManufacturerSchema | None = None
    error: str | None = None


class FittingSeriesOperationResponseSchema(BaseModel):
    success: bool
    item: FittingSeriesSchema | None = None
    error: str | None = None


class FittingTaxonomyCategoryOperationResponseSchema(BaseModel):
    success: bool
    item: FittingTaxonomyCategorySchema | None = None
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
