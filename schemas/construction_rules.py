from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConstructionRuleMountingNodeReferenceSchema(BaseModel):
    id: int
    code: str
    name: str
    fastening_type: str | None = None
    is_active: bool = True


class ConstructionRuleMountingSchemeReferenceSchema(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    is_active: bool = True


class ConstructionRuleMountingOptionSchema(BaseModel):
    id: int
    is_preferred: bool = False
    is_active: bool = True
    order_index: int = 0
    mounting_scheme: ConstructionRuleMountingSchemeReferenceSchema | None = None
    mounting_node: ConstructionRuleMountingNodeReferenceSchema | None = None


class ConstructionRuleVariantSchema(BaseModel):
    id: int
    code: str
    name: str
    parameters: dict[str, Any] | list[Any] | None = None
    is_default: bool = False
    is_active: bool = True
    order_index: int = 0
    mounting_options: list[ConstructionRuleMountingOptionSchema] = Field(default_factory=list)


class ConstructionRuleListItemSchema(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    primary_part_role: str
    secondary_part_role: str
    connection_type: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConstructionRuleDetailSchema(ConstructionRuleListItemSchema):
    variants: list[ConstructionRuleVariantSchema] = Field(default_factory=list)


class ConstructionRuleListResponseSchema(BaseModel):
    success: bool
    rules: list[ConstructionRuleListItemSchema] = Field(default_factory=list)
    error: str | None = None


class ConstructionRuleDetailResponseSchema(BaseModel):
    success: bool
    rule: ConstructionRuleDetailSchema | None = None
    error: str | None = None
