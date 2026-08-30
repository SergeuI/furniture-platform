from __future__ import annotations

import re
import unicodedata
from typing import Any


_DECOR_HINTS = (
    "decor",
    "декор",
    "code",
    "код",
    "article",
    "артикул",
    "sku",
    "mpn",
    "product id",
    "productid",
)

_STRUCTURE_HINTS = (
    "structure",
    "surface",
    "структур",
    "поверх",
    "texture",
    "текстур",
    "finish",
    "emboss",
)

_MANUFACTURER_HINTS = (
    "manufacturer",
    "manufacture",
    "виробник",
    "производитель",
    "brand",
    "бренд",
)

_DIMENSIONS_PATTERN = re.compile(
    r"(?P<width>\d{2,4})\s*[xх×]\s*(?P<length>\d{2,4})(?:\s*[xх×]\s*(?P<thickness>\d{1,3}))?",
    re.IGNORECASE,
)

_THICKNESS_PATTERN = re.compile(
    r"(?P<thickness>\d{1,3}(?:[.,]\d+)?)\s*(?:мм|mm)\b",
    re.IGNORECASE,
)

_DECOR_CODE_PATTERN = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_DECOR_CODE_ALPHANUM_PATTERN = re.compile(r"\b([A-Z]{1,3}\d{2,4})\b", re.IGNORECASE)
_DECOR_CODE_FALLBACK_PATTERN = re.compile(r"(?<!\d)(\d{3,5})(?!\d)")
_STRUCTURE_CODE_PATTERN = re.compile(r"\b([A-Z0-9][A-Z0-9-]{0,5})\b")
_MANUFACTURER_DESCRIPTOR_WORDS = {
    "дсп",
    "лдсп",
    "mdf",
    "hdf",
    "лам",
    "лам.",
    "ламінат",
    "ламінована",
    "ламінований",
    "лист",
    "плита",
    "панель",
    "плиты",
    "матеріал",
    "материал",
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_for_compare(value: Any) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    cleaned = unicodedata.normalize("NFKC", cleaned)
    cleaned = re.sub(r"[^\w\d]+", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.casefold()


def _normalize_code(value: Any) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    cleaned = unicodedata.normalize("NFKC", cleaned)
    cleaned = re.sub(r"[^0-9A-Za-zА-Яа-яІЇЄҐ_-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.upper()


def _normalize_dimensions(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            width = int(float(str(value[0]).replace(",", ".")))
            length = int(float(str(value[1]).replace(",", ".")))
            return f"{width}x{length}"
        except Exception:
            return ""

    text = _clean_text(value)
    if not text:
        return ""

    match = _DIMENSIONS_PATTERN.search(text)
    if not match:
        return ""

    width = match.group("width")
    length = match.group("length")
    return f"{width}x{length}"


def _normalize_thickness(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""

    dimensions_match = _DIMENSIONS_PATTERN.search(text)
    if dimensions_match and dimensions_match.group("thickness"):
        thickness_value = dimensions_match.group("thickness").replace(",", ".")
        try:
            numeric_value = float(thickness_value)
            if numeric_value.is_integer():
                return f"{int(numeric_value)} мм"
            return f"{numeric_value:g} мм"
        except ValueError:
            return f"{_clean_text(dimensions_match.group('thickness'))} мм"

    match = _THICKNESS_PATTERN.search(text)
    if match:
        thickness = match.group("thickness").replace(",", ".")
        try:
            thickness_value = float(thickness)
            if thickness_value.is_integer():
                return f"{int(thickness_value)} мм"
            return f"{thickness_value:g} мм"
        except ValueError:
            return f"{_clean_text(match.group('thickness'))} мм"

    try:
        thickness_value = float(text.replace(",", "."))
        if thickness_value.is_integer():
            return f"{int(thickness_value)} мм"
        return f"{thickness_value:g} мм"
    except ValueError:
        return ""


def _extract_first_value(material: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _clean_text(material.get(key))
        if value:
            return value
    return ""


def _extract_manufacturer(material: dict[str, Any]) -> str:
    direct = _extract_first_value(material, ("manufacturer_name", "brand"))
    if direct:
        return direct

    characteristics = material.get("characteristics")
    if isinstance(characteristics, dict):
        for key, value in characteristics.items():
            normalized_key = _normalize_for_compare(key)
            if any(hint in normalized_key for hint in _MANUFACTURER_HINTS):
                candidate = _clean_text(value) or _clean_text(key)
                if candidate:
                    return candidate

    return ""


def _extract_category(material: dict[str, Any], expected_category: str | None = None) -> str:
    return _clean_text(
        material.get("category")
        or material.get("product_type")
        or expected_category
    )


def _extract_decor_code(material: dict[str, Any]) -> str:
    characteristics = material.get("characteristics")
    candidate_texts: list[str] = []

    if isinstance(characteristics, dict):
        for key, value in characteristics.items():
            normalized_key = _normalize_for_compare(key)
            if any(hint in normalized_key for hint in _DECOR_HINTS):
                candidate_texts.extend([_clean_text(key), _clean_text(value)])

    candidate_texts.extend(
        [
            _clean_text(material.get("name")),
            _clean_text(material.get("description")),
        ]
    )

    def is_dimension_token(text: str, match: re.Match[str]) -> bool:
        before = text[match.start() - 1 : match.start()].lower() if match.start() > 0 else ""
        after = text[match.end() : match.end() + 1].lower()
        return before in {"x", "х", "×"} or after in {"x", "х", "×"}

    for text in candidate_texts:
        if not text:
            continue
        match = _DECOR_CODE_ALPHANUM_PATTERN.search(text)
        if match:
            return match.group(1).upper()

    for text in candidate_texts:
        if not text:
            continue
        match = _DECOR_CODE_PATTERN.search(text)
        if match and not is_dimension_token(text, match):
            return match.group(1)

    for text in candidate_texts:
        if not text:
            continue
        match = _DECOR_CODE_FALLBACK_PATTERN.search(text)
        if match and not is_dimension_token(text, match):
            return match.group(1)

    return ""


def _extract_structure_code(material: dict[str, Any], decor_code: str | None = None) -> str:
    characteristics = material.get("characteristics")
    if isinstance(characteristics, dict):
        for key, value in characteristics.items():
            normalized_key = _normalize_for_compare(key)
            if not any(hint in normalized_key for hint in _STRUCTURE_HINTS):
                continue
            candidate = _clean_text(value) or _clean_text(key)
            if candidate:
                match = _STRUCTURE_CODE_PATTERN.search(candidate.upper())
                if match:
                    return match.group(1).upper()
                return candidate.upper()

    text = _clean_text(material.get("name"))
    if not text:
        return ""

    if decor_code:
        pattern = re.compile(
            rf"\b{re.escape(str(decor_code))}\b\s+([A-Z0-9][A-Z0-9-]{{0,5}})\b",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            return match.group(1).upper()

    return ""


def _extract_identity_snapshot(
    material: dict[str, Any],
    *,
    expected_category: str | None = None,
) -> dict[str, str]:
    name = _clean_text(material.get("name"))
    decor_code = _extract_decor_code(material)
    snapshot = {
        "manufacturer": _normalize_for_compare(_extract_manufacturer(material)),
        "category": _normalize_for_compare(_extract_category(material, expected_category)),
        "decor_code": _normalize_for_compare(decor_code),
        "structure": _normalize_for_compare(_extract_structure_code(material, decor_code=decor_code)),
        "thickness": _normalize_for_compare(_normalize_thickness(material.get("thickness") or name)),
        "dimensions": _normalize_for_compare(_normalize_dimensions(material.get("dimensions") or name)),
    }
    return snapshot


def _display_value(material: dict[str, Any], field: str, snapshot_value: str) -> str | None:
    if not snapshot_value:
        return None

    if field == "manufacturer":
        return _clean_text(
            material.get("manufacturer_name")
            or material.get("brand")
            or material.get("manufacturer")
        ) or snapshot_value
    if field == "category":
        return _clean_text(material.get("category") or material.get("product_type")) or snapshot_value
    if field == "decor_code":
        return _clean_text(_extract_decor_code(material)) or snapshot_value
    if field == "structure":
        decor_code = _extract_decor_code(material)
        return _clean_text(_extract_structure_code(material, decor_code=decor_code)) or snapshot_value
    if field == "thickness":
        return _clean_text(_normalize_thickness(material.get("thickness") or material.get("name"))) or snapshot_value
    if field == "dimensions":
        return _clean_text(_normalize_dimensions(material.get("dimensions") or material.get("name"))) or snapshot_value

    return snapshot_value


def validate_material_supplier_offer_identity(
    existing_material: dict[str, Any],
    incoming_material: dict[str, Any],
    *,
    expected_category: str | None = None,
) -> dict[str, Any]:
    existing = _extract_identity_snapshot(existing_material)
    incoming = _extract_identity_snapshot(incoming_material, expected_category=expected_category)

    conflicts: list[dict[str, str | None]] = []
    missing_fields: list[str] = []
    matched_fields: list[str] = []
    evidence_score = 0

    field_labels = {
        "manufacturer": "manufacturer",
        "category": "category",
        "decor_code": "decor_code",
        "structure": "structure",
        "thickness": "thickness",
        "dimensions": "dimensions",
    }

    evidence_fields = {"manufacturer", "category", "decor_code", "structure", "thickness", "dimensions"}

    for field in field_labels:
        existing_value = existing.get(field, "")
        incoming_value = incoming.get(field, "")
        if existing_value and incoming_value:
            if existing_value == incoming_value:
                matched_fields.append(field_labels[field])
                if field in evidence_fields:
                    evidence_score += 1
            else:
                conflicts.append(
                    {
                        "field": field_labels[field],
                        "existing": _display_value(existing_material, field, existing_value),
                        "incoming": _display_value(incoming_material, field, incoming_value),
                    }
                )
        elif existing_value or incoming_value:
            missing_fields.append(field_labels[field])

    if conflicts:
        status = "conflict"
    elif evidence_score >= 3:
        status = "compatible"
    elif missing_fields:
        status = "needs_review"
    else:
        status = "needs_review"

    return {
        "status": status,
        "conflicts": conflicts,
        "missing_fields": missing_fields,
        "matched_fields": matched_fields,
    }
