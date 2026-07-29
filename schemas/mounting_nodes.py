from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MountingNodeItemCreateSchema(BaseModel):
    fitting_id: int
    quantity: int = Field(default=1, ge=1)
    role: str | None = Field(default=None, max_length=64)
    is_required: bool = True
    affects_processing: bool = True
    order_index: int = 0


class MountingNodeItemReadSchema(BaseModel):
    id: int
    node_id: int
    fitting_id: int
    fitting_code: str | None = None
    fitting_article: str | None = None
    fitting_name: str | None = None
    fitting_category_code: str | None = None
    quantity: int
    role: str | None = None
    is_required: bool = True
    affects_processing: bool = True
    order_index: int = 0


class MountingNodeTemplateLinkCreateSchema(BaseModel):
    template_id: int
    is_default: bool = False
    order_index: int = 0


class MountingNodeTemplateLinkReadSchema(BaseModel):
    id: int
    node_id: int
    template_id: int
    template_name: str | None = None
    fitting_id: int
    fitting_code: str | None = None
    fitting_article: str | None = None
    mounting_variant_key: str | None = None
    is_default: bool = False
    order_index: int = 0
    points_count: int = 0
    is_active: bool = True


class MountingNodeCreateSchema(BaseModel):
    code: str | None = Field(default=None, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool = True
    items: list[MountingNodeItemCreateSchema] = Field(default_factory=list)
    templates: list[MountingNodeTemplateLinkCreateSchema] = Field(default_factory=list)


class MountingNodeUpdateSchema(BaseModel):
    code: str | None = Field(default=None, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None
    items: list[MountingNodeItemCreateSchema] | None = None
    templates: list[MountingNodeTemplateLinkCreateSchema] | None = None


class MountingNodeListItemSchema(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    owner_user_id: str | None = None
    is_active: bool = True
    created_by_user_id: str | None = None
    updated_by_user_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    items_count: int = 0
    templates_count: int = 0


class MountingNodeDetailSchema(MountingNodeListItemSchema):
    items: list[MountingNodeItemReadSchema] = Field(default_factory=list)
    templates: list[MountingNodeTemplateLinkReadSchema] = Field(default_factory=list)


class MountingNodeListResponseSchema(BaseModel):
    success: bool
    nodes: list[MountingNodeListItemSchema] = Field(default_factory=list)
    error: str | None = None


class MountingNodeDetailResponseSchema(BaseModel):
    success: bool
    node: MountingNodeDetailSchema | None = None
    error: str | None = None


class MountingNodeOperationResponseSchema(BaseModel):
    success: bool
    node: MountingNodeDetailSchema | None = None
    error: str | None = None
