from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ALLOWED_FEATURE_VALUE_TYPES = (
    "boolean",
    "integer",
    "decimal",
    "text",
    "enum",
)

ALLOWED_PLAN_CODES = (
    "trial",
    "free",
    "pro",
    "business",
)

FEATURE_KEY_PATTERN = re.compile(r"^[a-z0-9._]+$")


def _trim_text(value):
    if value is None:
        return None
    return str(value).strip()


class FeatureValidationMixin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "feature_key",
        "name_uk",
        "description_uk",
        "category",
        "value_type",
        check_fields=False,
        mode="before",
    )
    @classmethod
    def _trim_feature_text(cls, value):
        return _trim_text(value)

    @field_validator("enum_options_json", check_fields=False, mode="before")
    @classmethod
    def _normalize_enum_options(cls, value):
        if value in (None, ""):
            return None
        if isinstance(value, list):
            return [
                _trim_text(item)
                for item in value
            ]
        return value

    @model_validator(mode="after")
    def _validate_feature_payload(self):
        feature_key = _trim_text(getattr(self, "feature_key", None))
        if feature_key is not None and not FEATURE_KEY_PATTERN.match(feature_key):
            raise ValueError(
                "feature_key може містити лише малі латинські літери, цифри, крапки та підкреслення"
            )

        value_type = _trim_text(getattr(self, "value_type", None))
        if value_type is not None and value_type not in ALLOWED_FEATURE_VALUE_TYPES:
            raise ValueError(
                "Непідтримуваний value_type"
            )

        enum_options_json = getattr(self, "enum_options_json", None)
        if value_type is None:
            if isinstance(enum_options_json, list):
                self.enum_options_json = [
                    option
                    for option in enum_options_json
                    if option is not None
                ]
            return self

        if value_type == "enum":
            options = [
                option
                for option in (enum_options_json or [])
                if option is not None and str(option).strip()
            ]
            if not options:
                raise ValueError(
                    "Для enum потрібно вказати перелік enum_options_json"
                )
            normalized_options: list[str] = []
            seen: set[str] = set()
            for option in options:
                normalized_option = _trim_text(option)
                if not normalized_option:
                    raise ValueError(
                        "enum_options_json не може містити порожні значення"
                    )
                if normalized_option in seen:
                    raise ValueError(
                        "enum_options_json не може містити дублікати"
                    )
                seen.add(normalized_option)
                normalized_options.append(normalized_option)
            self.enum_options_json = normalized_options
        else:
            if enum_options_json not in (None, [], ()):
                raise ValueError(
                    "enum_options_json дозволено лише для value_type=enum"
                )
            self.enum_options_json = None

        return self


class FeatureCreateRequest(FeatureValidationMixin):
    feature_key: str = Field(min_length=1, max_length=128)
    name_uk: str = Field(min_length=1, max_length=255)
    description_uk: str | None = Field(default=None, max_length=5000)
    category: str = Field(min_length=1, max_length=128)
    value_type: str = Field(min_length=1, max_length=32)
    enum_options_json: list[str] | None = None
    is_active: bool = True
    sort_order: int = 0


class FeatureUpdateRequest(FeatureValidationMixin):
    name_uk: str | None = Field(default=None, min_length=1, max_length=255)
    description_uk: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, min_length=1, max_length=128)
    value_type: str | None = Field(default=None, min_length=1, max_length=32)
    enum_options_json: list[str] | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class FeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feature_key: str
    name_uk: str
    description_uk: str | None = None
    category: str
    value_type: str
    enum_options_json: list[str] | None = None
    is_system: bool = False
    is_active: bool
    sort_order: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PlanEntitlementValueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: int = Field(gt=0)
    plan_code: str = Field(min_length=1, max_length=32)
    bool_value: bool | None = None
    integer_value: int | None = None
    decimal_value: Decimal | str | int | None = None
    text_value: str | None = Field(default=None, max_length=5000)
    is_unlimited: bool = False
    is_not_applicable: bool = False

    @field_validator("plan_code", mode="before")
    @classmethod
    def _trim_plan_code(cls, value):
        return _trim_text(value)

    @field_validator("text_value", mode="before")
    @classmethod
    def _trim_text_value(cls, value):
        return _trim_text(value)

    @field_validator("decimal_value", mode="before")
    @classmethod
    def _reject_float_decimal(cls, value):
        if isinstance(value, float):
            raise ValueError("decimal_value має бути Decimal або рядком, а не float")
        if value in (None, ""):
            return None
        return value

    @model_validator(mode="after")
    def _validate_plan_entitlement_value(self):
        if self.plan_code not in ALLOWED_PLAN_CODES:
            raise ValueError("Непідтримуваний plan_code")
        if self.is_unlimited and self.is_not_applicable:
            raise ValueError("is_unlimited та is_not_applicable не можуть бути true одночасно")
        return self


class PlanEntitlementValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    feature_id: int
    plan_code: str
    bool_value: bool | None = None
    integer_value: int | None = None
    decimal_value: Decimal | None = None
    text_value: str | None = None
    is_unlimited: bool = False
    is_not_applicable: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MatrixRowResponse(BaseModel):
    feature: FeatureResponse
    trial: PlanEntitlementValueResponse | None = None
    free: PlanEntitlementValueResponse | None = None
    pro: PlanEntitlementValueResponse | None = None
    business: PlanEntitlementValueResponse | None = None


class MatrixUpdateRequest(BaseModel):
    rows: list[PlanEntitlementValueRequest] = Field(default_factory=list)


class FeatureListResponse(BaseModel):
    success: bool
    features: list[FeatureResponse] = Field(default_factory=list)
    error: str | None = None


class FeatureOperationResponse(BaseModel):
    success: bool
    feature: FeatureResponse | None = None
    matrix_row: MatrixRowResponse | None = None
    error: str | None = None


class MatrixResponse(BaseModel):
    success: bool
    matrix: list[MatrixRowResponse] = Field(default_factory=list)
    error: str | None = None


class MatrixUpdateResponse(BaseModel):
    success: bool
    updated_count: int = 0
    matrix: list[MatrixRowResponse] = Field(default_factory=list)
    error: str | None = None


class EntitlementRegistrySyncPreviewResponse(BaseModel):
    success: bool
    can_apply: bool = False
    new_features: list[dict[str, Any]] = Field(default_factory=list)
    metadata_updates: list[dict[str, Any]] = Field(default_factory=list)
    missing_plan_rows: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)
    registry_features_missing_from_db: list[str] = Field(default_factory=list)
    db_system_features_missing_from_registry: list[str] = Field(default_factory=list)
    summary: dict[str, Any] | None = None
    error: str | None = None


class EntitlementRegistrySyncApplyResponse(BaseModel):
    success: bool
    applied: bool = False
    created_features: list[str] = Field(default_factory=list)
    updated_features: list[str] = Field(default_factory=list)
    created_plan_rows: list[dict[str, Any]] = Field(default_factory=list)
    orphaned_system_feature_keys: list[str] = Field(default_factory=list)
    summary: dict[str, Any] | None = None
    error: str | None = None
