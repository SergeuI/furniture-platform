from __future__ import annotations

MOUNTING_NODE_FUNCTIONAL_LABELS = {
    "connector": {
        "en": "Connector",
        "uk": "Кріплення деталей",
    },
    "door_hinge": {
        "en": "Door hinge",
        "uk": "Меблева завіса",
    },
    "drawer_slide": {
        "en": "Drawer slide",
        "uk": "Напрямна / висувна система",
    },
    "furniture_handle": {
        "en": "Furniture handle",
        "uk": "Меблева ручка",
    },
    "profile_handle": {
        "en": "Profile handle",
        "uk": "Ручка-профіль",
    },
    "cabinet_leg": {
        "en": "Cabinet leg",
        "uk": "Меблева опора / ніжка",
    },
    "wall_hanger": {
        "en": "Wall hanger",
        "uk": "Підвіс меблів",
    },
    "sink": {
        "en": "Sink",
        "uk": "Мийка",
    },
    "cooktop": {
        "en": "Cooktop",
        "uk": "Варильна поверхня",
    },
    "ventilation_grille": {
        "en": "Ventilation grille",
        "uk": "Вентиляційна решітка",
    },
    "electrical_socket": {
        "en": "Electrical socket",
        "uk": "Електрична розетка / електричний елемент",
    },
}

ALLOWED_MOUNTING_NODE_FUNCTIONAL_CODES = tuple(MOUNTING_NODE_FUNCTIONAL_LABELS.keys())


def normalize_mounting_node_functional_code(value: object) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized and normalized in MOUNTING_NODE_FUNCTIONAL_LABELS else ""


def get_mounting_node_functional_label(functional_code: str | None, language: str = "en") -> str:
    normalized_code = normalize_mounting_node_functional_code(functional_code)
    if not normalized_code:
        return ""

    normalized_language = "uk" if str(language or "").strip().lower() == "uk" else "en"
    return MOUNTING_NODE_FUNCTIONAL_LABELS[normalized_code].get(normalized_language, "")


def get_mounting_node_functional_options(language: str = "en") -> list[dict[str, str]]:
    normalized_language = "uk" if str(language or "").strip().lower() == "uk" else "en"

    return [
        {
            "code": code,
            "label": MOUNTING_NODE_FUNCTIONAL_LABELS[code].get(normalized_language, code),
        }
        for code in ALLOWED_MOUNTING_NODE_FUNCTIONAL_CODES
    ]
