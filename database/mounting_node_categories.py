from __future__ import annotations

from typing import Final


ALLOWED_MOUNTING_NODE_CATEGORY_CODES: Final[tuple[str, ...]] = (
    "fastening",
    "hinges",
    "drawer_systems",
    "handles_profiles",
    "supports_legs",
    "hangers",
    "sinks_plumbing",
    "appliances",
    "ventilation",
    "electrical",
    "other",
)

MOUNTING_NODE_CATEGORY_LABELS: Final[dict[str, str]] = {
    "fastening": "Кріплення деталей",
    "hinges": "Завіси",
    "drawer_systems": "Напрямні та висувні системи",
    "handles_profiles": "Ручки та профілі",
    "supports_legs": "Опори та ніжки",
    "hangers": "Підвіси",
    "sinks_plumbing": "Мийки та сантехніка",
    "appliances": "Вбудована техніка",
    "ventilation": "Вентиляція",
    "electrical": "Електрика",
    "other": "Інше",
}


def normalize_mounting_node_category_code(value: object) -> str | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    normalized = text.lower()
    return normalized if normalized in ALLOWED_MOUNTING_NODE_CATEGORY_CODES else None


def is_valid_mounting_node_category_code(value: object) -> bool:
    return normalize_mounting_node_category_code(value) is not None


def get_mounting_node_category_label(category_code: str | None) -> str | None:
    normalized = normalize_mounting_node_category_code(category_code)
    if normalized is None:
        return None
    return MOUNTING_NODE_CATEGORY_LABELS.get(normalized)

