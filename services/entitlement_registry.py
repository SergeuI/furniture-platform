from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


FEATURE_KEY_PATTERN = re.compile(r"^[a-z0-9._]+$")

ALLOWED_ENTITLEMENT_VALUE_TYPES = (
    "boolean",
    "integer",
    "decimal",
    "text",
    "enum",
)


def _trim_text(value: object | None) -> str:
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class EntitlementRegistryFeature:
    feature_key: str
    name_uk: str
    description_uk: str
    category: str
    value_type: str
    enum_options_json: tuple[str, ...] = ()
    sort_order: int = 0

    def __post_init__(self) -> None:
        feature_key = _trim_text(self.feature_key)
        name_uk = _trim_text(self.name_uk)
        description_uk = _trim_text(self.description_uk)
        category = _trim_text(self.category)
        value_type = _trim_text(self.value_type).lower()

        if not feature_key:
            raise ValueError("feature_key is required")
        if not FEATURE_KEY_PATTERN.match(feature_key):
            raise ValueError("feature_key must contain only lowercase letters, digits, dots and underscores")
        if not name_uk:
            raise ValueError("name_uk is required")
        if not category:
            raise ValueError("category is required")
        if value_type not in ALLOWED_ENTITLEMENT_VALUE_TYPES:
            raise ValueError("Unsupported value_type")

        options = tuple(_trim_text(option) for option in self.enum_options_json if _trim_text(option))
        if value_type == "enum":
            if not options:
                raise ValueError("enum_options_json is required for enum features")
            if len(options) != len(set(options)):
                raise ValueError("enum_options_json cannot contain duplicates")
        elif options:
            raise ValueError("enum_options_json is allowed only for enum features")

        object.__setattr__(self, "feature_key", feature_key)
        object.__setattr__(self, "name_uk", name_uk)
        object.__setattr__(self, "description_uk", description_uk)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "value_type", value_type)
        object.__setattr__(self, "enum_options_json", options)
        object.__setattr__(self, "sort_order", int(self.sort_order or 0))


SYSTEM_ENTITLEMENT_REGISTRY: tuple[EntitlementRegistryFeature, ...] = (
    EntitlementRegistryFeature(
        feature_key="materials.view",
        name_uk="Доступ до каталогу матеріалів",
        description_uk="Дозволяє переглядати каталог матеріалів.",
        category="materials",
        value_type="boolean",
        sort_order=10,
    ),
    EntitlementRegistryFeature(
        feature_key="materials.create",
        name_uk="Додавання власних матеріалів",
        description_uk="Дозволяє створювати лише власні приватні матеріали.",
        category="materials",
        value_type="boolean",
        sort_order=20,
    ),
    EntitlementRegistryFeature(
        feature_key="materials.edit",
        name_uk="Редагування власних матеріалів",
        description_uk="Дозволяє редагувати лише власні приватні матеріали.",
        category="materials",
        value_type="boolean",
        sort_order=30,
    ),
    EntitlementRegistryFeature(
        feature_key="materials.delete",
        name_uk="Видалення власних матеріалів",
        description_uk="Дозволяє видаляти лише власні приватні матеріали.",
        category="materials",
        value_type="boolean",
        sort_order=40,
    ),
    EntitlementRegistryFeature(
        feature_key="materials.max_owned",
        name_uk="Максимальна кількість власних матеріалів",
        description_uk="Визначає, скільки власних приватних матеріалів користувач може одночасно зберігати у своїй бібліотеці. Системні матеріали адміністратора та приватні матеріали інших користувачів до ліміту не входять.",
        category="materials",
        value_type="integer",
        sort_order=50,
    ),
    EntitlementRegistryFeature(
        feature_key="fittings.view",
        name_uk="Доступ до каталогу фурнітури",
        description_uk="Дозволяє переглядати каталог фурнітури.",
        category="fittings",
        value_type="boolean",
        sort_order=10,
    ),
    EntitlementRegistryFeature(
        feature_key="fittings.create",
        name_uk="Додавання власної фурнітури",
        description_uk="Дозволяє створювати лише власні приватні позиції фурнітури.",
        category="fittings",
        value_type="boolean",
        sort_order=20,
    ),
    EntitlementRegistryFeature(
        feature_key="fittings.edit",
        name_uk="Редагування власної фурнітури",
        description_uk="Дозволяє редагувати лише власні приватні позиції фурнітури.",
        category="fittings",
        value_type="boolean",
        sort_order=30,
    ),
    EntitlementRegistryFeature(
        feature_key="fittings.delete",
        name_uk="Видалення власної фурнітури",
        description_uk="Дозволяє видаляти лише власні приватні позиції фурнітури.",
        category="fittings",
        value_type="boolean",
        sort_order=40,
    ),
    EntitlementRegistryFeature(
        feature_key="fitting_holes.use",
        name_uk="Доступ до присадки фурнітури",
        description_uk="Дозволяє відкривати, додавати, редагувати та зберігати все, що пов'язане з модулем присадки фурнітури: схеми, точки отворів, варіанти кріплення, preview та збереження.",
        category="fitting_holes",
        value_type="boolean",
        sort_order=10,
    ),
    EntitlementRegistryFeature(
        feature_key="projects.view",
        name_uk="Перегляд проєктів",
        description_uk="Дозволяє переглядати список та деталі проєктів.",
        category="projects",
        value_type="boolean",
        sort_order=10,
    ),
    EntitlementRegistryFeature(
        feature_key="projects.create",
        name_uk="Створення проєктів",
        description_uk="Дозволяє створювати нові проєкти.",
        category="projects",
        value_type="boolean",
        sort_order=20,
    ),
    EntitlementRegistryFeature(
        feature_key="projects.edit",
        name_uk="Редагування проєктів",
        description_uk="Дозволяє редагувати наявні проєкти.",
        category="projects",
        value_type="boolean",
        sort_order=30,
    ),
    EntitlementRegistryFeature(
        feature_key="projects.delete",
        name_uk="Видалення проєктів",
        description_uk="Дозволяє видаляти проєкти.",
        category="projects",
        value_type="boolean",
        sort_order=40,
    ),
    EntitlementRegistryFeature(
        feature_key="projects.max_owned",
        name_uk="Максимальна кількість власних проєктів",
        description_uk="Визначає, скільки власних проєктів користувач може одночасно мати в системі.",
        category="projects",
        value_type="integer",
        sort_order=50,
    ),
    EntitlementRegistryFeature(
        feature_key="cutting.use",
        name_uk="Використання розкрою",
        description_uk="Дозволяє відкривати та використовувати модуль розкрою.",
        category="production",
        value_type="boolean",
        sort_order=10,
    ),
    EntitlementRegistryFeature(
        feature_key="ai.image_analysis",
        name_uk="AI-аналіз зображень",
        description_uk="Дозволяє запускати AI-аналіз зображень і PDF-проєктів.",
        category="ai",
        value_type="boolean",
        sort_order=10,
    ),
)


def get_system_entitlement_registry() -> tuple[EntitlementRegistryFeature, ...]:
    return SYSTEM_ENTITLEMENT_REGISTRY


def get_system_entitlement_registry_keys() -> tuple[str, ...]:
    return tuple(feature.feature_key for feature in SYSTEM_ENTITLEMENT_REGISTRY)


def build_system_entitlement_registry_map() -> dict[str, EntitlementRegistryFeature]:
    return {feature.feature_key: feature for feature in SYSTEM_ENTITLEMENT_REGISTRY}


def iter_system_entitlement_registry() -> Iterable[EntitlementRegistryFeature]:
    return SYSTEM_ENTITLEMENT_REGISTRY


__all__ = [
    "ALLOWED_ENTITLEMENT_VALUE_TYPES",
    "EntitlementRegistryFeature",
    "FEATURE_KEY_PATTERN",
    "SYSTEM_ENTITLEMENT_REGISTRY",
    "build_system_entitlement_registry_map",
    "get_system_entitlement_registry",
    "get_system_entitlement_registry_keys",
    "iter_system_entitlement_registry",
]
