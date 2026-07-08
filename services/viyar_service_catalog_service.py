from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request
from urllib.request import urlopen

from bs4 import BeautifulSoup


VIYAR_SERVICES_URL = "https://viyar.ua/ua/catalog/uslugi/"
VIYAR_SERVICE_GROUPS = [
    {
        "code": "cutting",
        "name": "Порізка",
        "slug": "porezka",
        "description": "Розпил плитних матеріалів.",
        "pages": [
            {"code": "cutting-main", "name": "Порізка", "slug": "porezka", "url": "https://viyar.ua/ua/catalog/porezka/"},
        ],
    },
    {
        "code": "drilling",
        "name": "Свердління",
        "slug": "prisadka",
        "description": "Свердління та присадка деталей.",
        "pages": [
            {"code": "drilling-main", "name": "Свердління", "slug": "prisadka", "url": "https://viyar.ua/ua/catalog/prisadka/"},
        ],
    },
    {
        "code": "straight_edgebanding",
        "name": "Кромкування",
        "slug": "pokleyka",
        "description": "Прямолінійне крайкування деталей.",
        "pages": [
            {"code": "straight-edgebanding-main", "name": "Кромкування", "slug": "pokleyka", "url": "https://viyar.ua/ua/catalog/pokleyka/"},
        ],
    },
    {
        "code": "milling",
        "name": "Фрезерування",
        "slug": "frezerovka",
        "description": "Фрезерування деталей і фасадів.",
        "pages": [
            {"code": "milling-page-1", "name": "Фрезерування - сторінка 1", "slug": "frezerovka", "url": "https://viyar.ua/ua/catalog/frezerovka/"},
            {"code": "milling-page-2", "name": "Фрезерування - сторінка 2", "slug": "frezerovka-page-2", "url": "https://viyar.ua/ua/catalog/frezerovka/page-2/"},
        ],
    },
    {
        "code": "additional_services",
        "name": "Додаткові послуги",
        "slug": "dopolnitelnye_uslugi",
        "description": "Додаткові виробничі операції.",
        "pages": [
            {"code": "additional-services-main", "name": "Додаткові послуги", "slug": "dopolnitelnye_uslugi", "url": "https://viyar.ua/ua/catalog/dopolnitelnye_uslugi/"},
        ],
    },
    {
        "code": "curved_edgebanding",
        "name": "Крайкування криволінійне",
        "slug": "pokleyka_krivolineynaya",
        "description": "Криволінійне крайкування деталей.",
        "pages": [
            {"code": "curved-edgebanding-page-1", "name": "Крайкування криволінійне - сторінка 1", "slug": "pokleyka_krivolineynaya", "url": "https://viyar.ua/ua/catalog/pokleyka_krivolineynaya/"},
            {"code": "curved-edgebanding-page-2", "name": "Крайкування криволінійне - сторінка 2", "slug": "pokleyka_krivolineynaya-page-2", "url": "https://viyar.ua/ua/catalog/pokleyka_krivolineynaya/page-2/"},
            {"code": "curved-edgebanding-page-3", "name": "Крайкування криволінійне - сторінка 3", "slug": "pokleyka_krivolineynaya-page-3", "url": "https://viyar.ua/ua/catalog/pokleyka_krivolineynaya/page-3/"},
            {"code": "curved-edgebanding-page-4", "name": "Крайкування криволінійне - сторінка 4", "slug": "pokleyka_krivolineynaya-page-4", "url": "https://viyar.ua/ua/catalog/pokleyka_krivolineynaya/page-4/"},
        ],
    },
    {
        "code": "jointing",
        "name": "Стяжка",
        "slug": "styazhka",
        "description": "Стяжка та збирання.",
        "pages": [
            {"code": "jointing-main", "name": "Стяжка", "slug": "styazhka", "url": "https://viyar.ua/ua/catalog/styazhka/"},
        ],
    },
    {
        "code": "packing",
        "name": "Пакування",
        "slug": "upakovka",
        "description": "Пакування та підготовка до відвантаження.",
        "pages": [
            {"code": "packing-main", "name": "Пакування", "slug": "upakovka", "url": "https://viyar.ua/ua/catalog/upakovka/"},
        ],
    },
]
VIYAR_SERVICE_PAGE_BY_CODE = {
    group["code"]: group["pages"][0]["url"]
    for group in VIYAR_SERVICE_GROUPS
}
VIYAR_SERVICE_PAGE_BY_CODE.update(
    {
        page["code"]: page["url"]
        for group in VIYAR_SERVICE_GROUPS
        for page in group["pages"]
    }
)
PRICE_PATTERN = re.compile(
    r"(\d{1,3}(?:[\s\u00a0]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?:\u0433\u0440\u043d(?:\.)?|\u20b4|uah)",
    re.IGNORECASE,
)
ARTICLE_PATTERNS = [
    re.compile(r"\u0430\u0440\u0442\u0438\u043a\u0443\u043b\s*[:#]?\s*([A-Za-z\u0410-\u042f\u0430-\u044f0-9._/\-]+)", re.IGNORECASE),
    re.compile(r"sku\s*[:#]?\s*([A-Za-z0-9._/\-]+)", re.IGNORECASE),
    re.compile(r"\u043a\u043e\u0434\s*(?:\u043f\u043e\u0441\u043b\u0443\u0433\u0438|\u0442\u043e\u0432\u0430\u0440\u0443)?\s*[:#]?\s*([A-Za-z\u0410-\u042f\u0430-\u044f0-9._/\-]+)", re.IGNORECASE),
]
ARTICLE_BANNED_VALUES = {
    "\u0441\u0443\u043c\u0430",
    "\u0446\u0456\u043d\u0430",
    "\u0432\u0430\u0440\u0442\u0456\u0441\u0442\u044c",
    "service",
    "sku",
    "uah",
}
PRICE_WORKER_PATH = Path(__file__).with_name("viyar_price_worker.py")
PRICE_WORKER_TIMEOUT_SECONDS = 120


def _normalize_viyar_numeric_article(value: str | None) -> str | None:

    normalized = _normalize_text(value).strip()

    if not normalized:
        return None

    digits_only = re.sub(r"\D+", "", normalized)

    if len(digits_only) < 4:
        return None

    return digits_only


def _fallback_article_from_external_code(external_code: str | None) -> str | None:

    normalized = _normalize_text(external_code).strip()

    if not normalized:
        return None

    match = re.search(r"(\d{4,})$", normalized)

    if not match:
        return None

    return match.group(1)


FALLBACK_SERVICE_FOLDERS = [
    {
        "code": group["code"],
        "name": group["name"],
        "slug": group["slug"],
        "source_url": group["pages"][0]["url"],
        "description": group["description"],
        "pages": group["pages"],
    }
    for group in VIYAR_SERVICE_GROUPS
]


FALLBACK_CODE_BY_NAME = {
    item["name"]: item
    for item in FALLBACK_SERVICE_FOLDERS
}

VIYAR_SERVICE_BLOCKED_NAMES = {
    "дата",
    "опис",
    "обмеження",
    "найдешевший товар",
    "заголовок",
    "назва",
    "ціна",
    "table",
    "header",
}

VIYAR_SERVICE_BLOCKED_PREFIXES = (
    "дата",
    "опис",
    "обмеж",
    "найдешев",
    "header",
    "table",
)


def _build_viyar_service_audit() -> dict[str, int]:
    return {
        "total_records": 0,
        "valid_services": 0,
        "suspicious_records": 0,
        "records_without_article": 0,
        "records_without_price": 0,
        "filtered_service_rows": 0,
    }


def _bump_viyar_service_audit(
    audit: dict[str, int] | None,
    key: str,
    amount: int = 1,
) -> None:

    if audit is None:
        return

    audit[key] = int(audit.get(key, 0)) + amount


def _is_blocked_viyar_service_name(value: str | None) -> bool:

    normalized = _normalize_text(value)

    if not normalized:
        return True

    lowered = normalized.lower()

    if lowered in VIYAR_SERVICE_BLOCKED_NAMES:
        return True

    if lowered.startswith(VIYAR_SERVICE_BLOCKED_PREFIXES):
        return True

    if lowered in {
        _normalize_text(folder["name"]).lower()
        for folder in FALLBACK_SERVICE_FOLDERS
    }:
        return True

    if lowered in {
        _normalize_text(page["name"]).lower()
        for folder in FALLBACK_SERVICE_FOLDERS
        for page in folder.get("pages", [])
    }:
        return True

    if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", lowered):
        return True

    return False


def _mark_viyar_service_rejection(
    audit: dict[str, int] | None,
    *,
    suspicious: bool = False,
    missing_price: bool = False,
) -> None:

    if suspicious:
        _bump_viyar_service_audit(audit, "suspicious_records")
        _bump_viyar_service_audit(audit, "filtered_service_rows")

    if missing_price:
        _bump_viyar_service_audit(audit, "records_without_price")


def _build_viyar_description_audit() -> dict[str, int]:
    return {
        "total_services": 0,
        "with_source_url": 0,
        "with_short_description": 0,
        "with_full_description": 0,
        "without_full_description": 0,
        "failed_downloads": 0,
    }


def _normalize_text(value: str | None) -> str:

    if not value:
        return ""

    return re.sub(r"\s+", " ", value).strip()


VIYAR_DESCRIPTION_STOP_MARKERS = {
    "характеристики",
    "відгуки та питання",
    "відгуки",
    "питання",
    "строки",
    "доставка та оплата",
    "доставка",
    "оплата",
    "показати більше",
}


VIYAR_DESCRIPTION_START_MARKERS = (
    "опис",
    "обмеження",
    "технічний опис",
    "технічні характеристики",
    "технічна інформація",
    "інформація",
    "інформаційний блок",
    "характеристики",
    "умови",
    "додаткова інформація",
)

VIYAR_DESCRIPTION_STOP_PREFIXES = (
    "відгуки",
    "питання",
    "доставка",
    "оплата",
    "table",
    "header",
)

VIYAR_DESCRIPTION_SECTION_TAGS = (
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "strong",
    "b",
    "p",
    "li",
    "div",
    "span",
)

VIYAR_DESCRIPTION_MAX_LENGTH = 8000


def _normalized_viyar_description_heading(value: str | None) -> str:

    normalized = _normalize_text(value).lower()
    normalized = re.sub(r"^#+\s*", "", normalized)

    return normalized[:-1] if normalized.endswith(":") else normalized


def _is_viyar_description_heading(value: str | None) -> bool:

    normalized = _normalized_viyar_description_heading(value)

    if not normalized or len(normalized) > 120:
        return False

    return any(
        normalized == marker
        or normalized.startswith(f"{marker} ")
        or normalized.startswith(f"{marker}:")
        for marker in VIYAR_DESCRIPTION_START_MARKERS
    )


def _is_viyar_description_stop_line(value: str | None) -> bool:

    normalized = _normalized_viyar_description_heading(value)

    if not normalized:
        return True

    if normalized in VIYAR_DESCRIPTION_STOP_MARKERS:
        return True

    return normalized.startswith(VIYAR_DESCRIPTION_STOP_PREFIXES)


def _looks_like_viyar_full_description(value: str | None) -> bool:

    normalized = _normalize_text(value)

    if len(normalized) < 50:
        return False

    if "\n" in normalized:
        return True

    if len(re.findall(r"[.!?]+", normalized)) >= 2:
        return True

    lowered = normalized.lower()

    return any(
        marker in lowered
        for marker in (
            "обмеження",
            "характеристик",
            "техніч",
            "інформаці",
            "опис",
        )
    )


def _collect_viyar_description_after_element(element) -> str | None:

    collected: list[str] = []

    for sibling in element.find_next_siblings():
        sibling_text = _normalize_text(
            getattr(sibling, "get_text", lambda *_args, **_kwargs: str(sibling))(" ", strip=True)
        )

        if not sibling_text:
            continue

        if _is_viyar_description_stop_line(sibling_text):
            break

        if _is_viyar_description_heading(sibling_text) and collected:
            break

        collected.append(sibling_text)

        if len(" ".join(collected)) >= VIYAR_DESCRIPTION_MAX_LENGTH:
            break

    description = "\n".join(collected).strip()

    return description if _looks_like_viyar_full_description(description) else None


def _collect_viyar_description_from_lines(lines: list[str]) -> str | None:

    for index, line in enumerate(lines):
        if not _is_viyar_description_heading(line):
            continue

        collected: list[str] = []

        for next_line in lines[index + 1 :]:
            if _is_viyar_description_stop_line(next_line):
                break

            if _is_viyar_description_heading(next_line) and collected:
                break

            collected.append(next_line)

            if len(" ".join(collected)) >= VIYAR_DESCRIPTION_MAX_LENGTH:
                break

        description = "\n".join(collected).strip()

        if _looks_like_viyar_full_description(description):
            return description

    return None


def _extract_viyar_service_full_description(html: str) -> str | None:

    soup = BeautifulSoup(html, "html.parser")
    lines = [
        _normalize_text(line)
        for line in soup.get_text("\n", strip=True).splitlines()
    ]
    lines = [line for line in lines if line]

    start_index = None

    for index in range(len(lines) - 1, -1, -1):
        lowered = lines[index].lower()
        if lowered == "опис:" or lowered == "опис":
            start_index = index + 1
            break

    if start_index is None:
        return None

    collected: list[str] = []

    for line in lines[start_index:]:
        lowered = line.lower()

        if lowered in VIYAR_DESCRIPTION_STOP_MARKERS:
            break

        if lowered.startswith("### ") and "опис" not in lowered:
            break

        collected.append(line)

    description = "\n".join(collected).strip()

    return description or None


def _extract_viyar_service_category(folder_path: str | None) -> str:

    normalized = _normalize_text(folder_path).lower()

    if "prisadka" in normalized:
        return "drilling"

    if "pokleyka_krivolineynaya" in normalized or "pokleyka" in normalized:
        return "edgebanding"

    if "porezka" in normalized:
        return "cutting"

    if "frezerovka" in normalized:
        return "milling"

    return "other"


VIYAR_PREFERRED_DESCRIPTION_HEADINGS = (
    "опис",
    "обмеження",
    "технічний опис",
    "технічна інформація",
    "інформація",
    "інформаційний блок",
    "умови",
    "додаткова інформація",
)

VIYAR_CHARACTERISTICS_ONLY_MARKERS = (
    "основні характеристики продукту",
    "технічні характеристики та функціональність",
    "тип послуги:",
    "виробник:",
    "країна виробник:",
)


def _is_viyar_preferred_description_heading(value: str | None) -> bool:

    normalized = _normalized_viyar_description_heading(value)

    return any(
        normalized == marker
        or normalized.startswith(f"{marker} ")
        or normalized.startswith(f"{marker}:")
        for marker in VIYAR_PREFERRED_DESCRIPTION_HEADINGS
    )


def _extract_viyar_preferred_description(html: str) -> str | None:

    soup = BeautifulSoup(html, "html.parser")
    lines = [
        _normalize_text(line)
        for line in soup.get_text("\n", strip=True).splitlines()
    ]
    lines = [line for line in lines if line]

    for index, line in enumerate(lines):
        if not _is_viyar_preferred_description_heading(line):
            continue

        collected: list[str] = []

        for next_line in lines[index + 1 :]:
            if _is_viyar_description_stop_line(next_line):
                break

            if _is_viyar_description_heading(next_line) and collected:
                break

            collected.append(next_line)

            if len(" ".join(collected)) >= VIYAR_DESCRIPTION_MAX_LENGTH:
                break

        description = "\n".join(collected).strip()

        if _looks_like_viyar_full_description(description):
            return description

    return None


def _extract_viyar_service_full_description(html: str) -> str | None:

    soup = BeautifulSoup(html, "html.parser")

    preferred_description = _extract_viyar_preferred_description(html)
    if preferred_description:
        return preferred_description

    page_text = _normalize_text(soup.get_text(" ", strip=True)).lower()
    if any(marker in page_text for marker in VIYAR_CHARACTERISTICS_ONLY_MARKERS) and not any(
        marker in page_text
        for marker in (
            "опис",
            "обмеження",
            "технічний опис",
            "технічна інформація",
            "інформаційний блок",
            "додаткова інформація",
            "умови",
        )
    ):
        return None

    for tag in soup.select(",".join(VIYAR_DESCRIPTION_SECTION_TAGS)):
        text = _normalize_text(tag.get_text(" ", strip=True))

        if not _is_viyar_description_heading(text):
            continue

        description = _collect_viyar_description_after_element(tag)

        if description:
            return description

    lines = [
        _normalize_text(line)
        for line in soup.get_text("\n", strip=True).splitlines()
    ]
    lines = [line for line in lines if line]

    description = _collect_viyar_description_from_lines(lines)

    if description:
        return description

    fallback_paragraphs = [
        _normalize_text(paragraph.get_text(" ", strip=True))
        for paragraph in soup.find_all("p")
    ]
    fallback_paragraphs = [
        paragraph
        for paragraph in fallback_paragraphs
        if paragraph and len(paragraph) >= 120
    ]

    for paragraph in fallback_paragraphs:
        if _looks_like_viyar_full_description(paragraph):
            return paragraph

    return None


def _fetch_viyar_service_full_description(
    source_url: str,
    use_remote: bool = True,
    cookie_override: str | None = None,
    diagnostic: bool = False,
) -> dict[str, Any]:

    normalized_source_url = _normalize_text(source_url)

    if not normalized_source_url:
        return {
            "full_description": None,
            "rules_parse_status": "not_available",
            "rules_parsed_at": None,
            "rules_source_url": None,
        }

    if not use_remote:
        return {
            "full_description": None,
            "rules_parse_status": "skipped",
            "rules_parsed_at": None,
            "rules_source_url": normalized_source_url,
        }

    html, auth_required, _fetch_mode = _fetch_price_page(
        normalized_source_url,
        use_remote=use_remote,
        cookie_override=cookie_override,
    )

    full_description = None
    rules_parse_status = "no_full_description"

    if html and not auth_required:
        payload = _extract_viyar_service_full_description_payload(html)
        full_description = payload.get("full_description")
        rules_parse_status = payload.get("rules_parse_status") or rules_parse_status

    rendered_page = {}
    rendered_html = ""
    rendered_text = ""
    rendered_final_url = normalized_source_url
    rendered_success = False
    rendered_login_required = False

    if not full_description:
        rendered_pages = _fetch_rendered_price_pages(
            [
                {
                    "external_code": "viyar-service-description",
                    "source_url": normalized_source_url,
                }
            ],
            cookie_override=cookie_override,
        )
        rendered_page = rendered_pages.get("viyar-service-description") or {}
        rendered_html = rendered_page.get("html") or ""
        rendered_text = rendered_page.get("body_text") or ""
        rendered_final_url = rendered_page.get("final_url") or normalized_source_url
        rendered_success = bool(rendered_page.get("success"))
        rendered_login_required = "login_required" in rendered_final_url.lower()

        if rendered_success and not rendered_login_required:
            payload = _extract_viyar_service_full_description_payload(
                rendered_html or rendered_text
            )
            if payload.get("full_description"):
                full_description = payload.get("full_description")
                rules_parse_status = payload.get("rules_parse_status") or "parsed"
            elif payload.get("rules_parse_status") == "needs_review":
                rules_parse_status = "needs_review"

    if not full_description and (
        rendered_login_required
        or (not rendered_success and not (html and not auth_required))
    ):
        return {
            "full_description": None,
            "rules_parse_status": "failed",
            "rules_parsed_at": None,
            "rules_source_url": rendered_final_url if rendered_page else normalized_source_url,
        }

    return {
        "full_description": full_description,
        "rules_parse_status": "parsed" if full_description else rules_parse_status,
        "rules_parsed_at": datetime.utcnow() if full_description else None,
        "rules_source_url": rendered_final_url if full_description and rendered_page else normalized_source_url,
    }


def _extract_viyar_service_full_description(html: str) -> str | None:
    payload = _extract_viyar_service_full_description_payload(html)
    return payload.get("full_description")


def backfill_viyar_drilling_service_descriptions(
    use_remote: bool = True,
    cookie_override: str | None = None,
) -> dict[str, Any]:

    from database.models.service_catalog_item import ServiceCatalogItemModel
    from database.session import SessionLocal

    db = SessionLocal()

    try:
        services = (
            db.query(ServiceCatalogItemModel)
            .filter(ServiceCatalogItemModel.source == "viyar")
            .filter(ServiceCatalogItemModel.item_type == "service")
            .filter(ServiceCatalogItemModel.is_active.is_(True))
            .filter(ServiceCatalogItemModel.folder_path == "viyar-services/prisadka")
            .order_by(
                ServiceCatalogItemModel.sort_order.asc(),
                ServiceCatalogItemModel.name.asc(),
            )
            .all()
        )

        audit: dict[str, Any] = {
            "total_active_services": len(services),
            "with_source_url": 0,
            "with_full_description": 0,
            "without_full_description": 0,
            "failed_articles": [],
        }

        now = datetime.utcnow()

        for service in services:
            source_url = _normalize_text(service.source_url)

            if source_url:
                audit["with_source_url"] += 1

            fetch_result = _fetch_viyar_service_full_description(
                source_url or _source_url_from_service_code(service.external_code),
                use_remote=use_remote,
                cookie_override=cookie_override,
            )
            full_description = fetch_result.get("full_description")
            parse_status = fetch_result.get("rules_parse_status") or "no_full_description"

            if full_description:
                service.full_description = full_description
                service.rules_source_url = fetch_result.get("rules_source_url") or source_url or service.source_url
                service.rules_parsed_at = now
                service.rules_parse_status = "parsed"
                audit["with_full_description"] += 1
                continue

            if service.full_description and _normalize_text(service.full_description):
                service.rules_source_url = fetch_result.get("rules_source_url") or source_url or service.source_url
                service.rules_parse_status = "parsed"
                audit["with_full_description"] += 1
                continue

            service.rules_source_url = fetch_result.get("rules_source_url") or source_url or service.source_url
            service.rules_parsed_at = None
            service.rules_parse_status = (
                "failed" if parse_status == "failed" else "no_full_description"
            )
            audit["without_full_description"] += 1
            audit["failed_articles"].append(service.article or service.external_code)

        db.commit()

        audit["failed_articles"] = sorted(
            {
                article
                for article in audit["failed_articles"]
                if article
            }
        )

        return audit

    finally:

        db.close()


def _fetch_viyar_service_full_description(
    source_url: str,
    use_remote: bool = True,
    cookie_override: str | None = None,
    diagnostic: bool = False,
) -> dict[str, Any]:

    normalized_source_url = _normalize_text(source_url)

    if not normalized_source_url:
        return {
            "full_description": None,
            "rules_parse_status": "not_available",
            "rules_parsed_at": None,
            "rules_source_url": None,
        }

    if not use_remote:
        return {
            "full_description": None,
            "rules_parse_status": "skipped",
            "rules_parsed_at": None,
            "rules_source_url": normalized_source_url,
        }

    html, auth_required, _fetch_mode = _fetch_price_page(
        normalized_source_url,
        use_remote=use_remote,
        cookie_override=cookie_override,
    )

    if not html or auth_required:
        return {
            "full_description": None,
            "rules_parse_status": "failed",
            "rules_parsed_at": None,
            "rules_source_url": normalized_source_url,
        }

    payload = _extract_viyar_service_full_description_payload(
        html,
        diagnostic=diagnostic,
    )
    payload["rules_source_url"] = normalized_source_url
    return payload


def _apply_viyar_service_full_description_fallback(
    service,
    *,
    fetch_result: dict[str, Any],
) -> bool:

    full_description = _normalize_text(fetch_result.get("full_description"))
    fetch_status = _normalize_text(fetch_result.get("rules_parse_status")).lower()
    existing_full_description = _normalize_text(service.full_description)
    existing_full_description_valid = _is_viyar_valid_full_description_text(existing_full_description)

    if full_description:
        service.full_description = full_description
        service.rules_source_url = (
            fetch_result.get("rules_source_url")
            or service.rules_source_url
            or service.source_url
        )
        service.rules_parsed_at = fetch_result.get("rules_parsed_at") or datetime.utcnow()
        service.rules_parse_status = "parsed"
        return True

    if existing_full_description_valid:
        service.rules_source_url = (
            fetch_result.get("rules_source_url")
            or service.rules_source_url
            or service.source_url
        )
        service.rules_parsed_at = (
            fetch_result.get("rules_parsed_at")
            or service.rules_parsed_at
            or datetime.utcnow()
        )
        service.rules_parse_status = "parsed"
        return True

    fallback_description = _normalize_text(service.description)
    if _is_viyar_valid_full_description_text(fallback_description):
        full_description = fallback_description

    if not full_description:
        service.full_description = None
        service.rules_source_url = (
            fetch_result.get("rules_source_url")
            or service.rules_source_url
            or service.source_url
        )
        service.rules_parsed_at = None
        service.rules_parse_status = (
            "needs_review" if fetch_status == "needs_review" else "no_full_description"
        )
        return False

    service.full_description = full_description
    service.rules_source_url = (
        fetch_result.get("rules_source_url")
        or service.rules_source_url
        or service.source_url
    )
    service.rules_parsed_at = fetch_result.get("rules_parsed_at") or datetime.utcnow()
    service.rules_parse_status = "parsed"
    return True


def backfill_viyar_service_descriptions(
    use_remote: bool = True,
    cookie_override: str | None = None,
) -> dict[str, Any]:

    from database.models.service_catalog_item import ServiceCatalogItemModel
    from database.session import SessionLocal

    db = SessionLocal()

    try:
        services = (
            db.query(ServiceCatalogItemModel)
            .filter(ServiceCatalogItemModel.source == "viyar")
            .filter(ServiceCatalogItemModel.item_type == "service")
            .filter(ServiceCatalogItemModel.is_active.is_(True))
            .order_by(
                ServiceCatalogItemModel.folder_path.asc(),
                ServiceCatalogItemModel.sort_order.asc(),
                ServiceCatalogItemModel.name.asc(),
            )
            .all()
        )

        audit: dict[str, Any] = {
            "total_active_services": len(services),
            "with_source_url": 0,
            "with_short_description": 0,
            "with_only_short_description": 0,
            "with_full_description": 0,
            "no_full_description": 0,
            "without_full_description": 0,
            "failed_downloads": 0,
            "failed_articles": [],
            "categories": {
                "drilling": {
                    "total_services": 0,
                    "with_source_url": 0,
                    "with_short_description": 0,
                    "with_only_short_description": 0,
                    "with_full_description": 0,
                    "no_full_description": 0,
                    "without_full_description": 0,
                    "failed_downloads": 0,
                },
                "edgebanding": {
                    "total_services": 0,
                    "with_source_url": 0,
                    "with_short_description": 0,
                    "with_only_short_description": 0,
                    "with_full_description": 0,
                    "no_full_description": 0,
                    "without_full_description": 0,
                    "failed_downloads": 0,
                },
                "cutting": {
                    "total_services": 0,
                    "with_source_url": 0,
                    "with_short_description": 0,
                    "with_only_short_description": 0,
                    "with_full_description": 0,
                    "no_full_description": 0,
                    "without_full_description": 0,
                    "failed_downloads": 0,
                },
                "milling": {
                    "total_services": 0,
                    "with_source_url": 0,
                    "with_short_description": 0,
                    "with_only_short_description": 0,
                    "with_full_description": 0,
                    "no_full_description": 0,
                    "without_full_description": 0,
                    "failed_downloads": 0,
                },
                "other": {
                    "total_services": 0,
                    "with_source_url": 0,
                    "with_short_description": 0,
                    "with_only_short_description": 0,
                    "with_full_description": 0,
                    "no_full_description": 0,
                    "without_full_description": 0,
                    "failed_downloads": 0,
                },
            },
        }

        now = datetime.utcnow()

        for service in services:
            source_url = _normalize_text(service.source_url)

            if source_url:
                audit["with_source_url"] += 1

            fetch_result = _fetch_viyar_service_full_description(
                source_url or _source_url_from_service_code(service.external_code),
                use_remote=use_remote,
                cookie_override=cookie_override,
            )
            full_description = _normalize_text(fetch_result.get("full_description"))
            parse_status = _normalize_text(fetch_result.get("rules_parse_status") or "no_full_description").lower()
            existing_full_description = _normalize_text(service.full_description)
            existing_full_description_valid = _is_viyar_valid_full_description_text(existing_full_description)

            if full_description:
                service.full_description = full_description
                service.rules_source_url = fetch_result.get("rules_source_url") or source_url or service.source_url
                service.rules_parsed_at = fetch_result.get("rules_parsed_at") or now
                service.rules_parse_status = "parsed"
                audit["with_full_description"] += 1
                continue

            if existing_full_description_valid:
                service.rules_source_url = fetch_result.get("rules_source_url") or source_url or service.source_url
                service.rules_parsed_at = fetch_result.get("rules_parsed_at") or service.rules_parsed_at or now
                service.rules_parse_status = "parsed"
                audit["with_full_description"] += 1
                continue

            service.full_description = None
            service.rules_source_url = fetch_result.get("rules_source_url") or source_url or service.source_url
            service.rules_parsed_at = None
            service.rules_parse_status = "failed" if parse_status == "failed" else parse_status
            if service.rules_parse_status not in {"needs_review", "failed"}:
                service.rules_parse_status = "no_full_description"
            if service.rules_parse_status == "failed":
                audit["failed_downloads"] += 1
            else:
                audit["no_full_description"] += 1
            audit["without_full_description"] = audit["no_full_description"]
            audit["failed_articles"].append(service.article or service.external_code)

        db.commit()

        audit["failed_articles"] = sorted(
            {
                article
                for article in audit["failed_articles"]
                if article
            }
        )

        return audit

    finally:
        db.close()


def backfill_viyar_drilling_service_descriptions(
    use_remote: bool = True,
    cookie_override: str | None = None,
) -> dict[str, Any]:

    return backfill_viyar_service_descriptions(
        use_remote=use_remote,
        cookie_override=cookie_override,
    )


def _is_viyar_valid_full_description_text(value: str | None) -> bool:

    normalized = _normalize_text(value)

    if not normalized:
        return False

    lowered = normalized.lower()
    noise_markers = (
        "код:",
        "ціна viyarpro",
        "строки",
        "грн/шт",
        "основні характеристики продукту",
        "технічні характеристики та функціональність",
        "тип товару",
        "тип послуги",
        "виробник",
        "країна виробник",
        "viyarpro",
    )

    if "опис:" not in lowered:
        return False

    if len(normalized) < 50:
        return False

    if sum(1 for marker in noise_markers if marker in lowered) >= 3 and not any(
        marker in lowered for marker in ("обмеження", "обладнання")
    ):
        return False

    return True


def _is_viyar_stale_full_description_text(value: str | None) -> bool:

    normalized = _normalize_text(value)

    if not normalized:
        return False

    lowered = normalized.lower()
    has_description_block = (
        "опис:" in lowered
        and ("обмеження:" in lowered or "обладнання:" in lowered)
    )
    stale_markers = (
        "код:",
        "ціна viyarpro",
        "строки",
        "увага! колір товару",
        "грн/шт",
        "є/шт",
        "основні характеристики продукту",
        "технічні характеристики та функціональність",
        "тип товару:",
        "тип послуги:",
        "виробник:",
        "країна виробник:",
        "viyarpro",
    )

    if has_description_block:
        return False

    return any(marker in lowered for marker in stale_markers)


def _extract_viyar_service_full_description_payload(
    html: str,
    diagnostic: bool = False,
) -> dict[str, Any]:

    soup = BeautifulSoup(html, "html.parser")
    description_section = soup.select_one("section#description")
    characteristics_section = soup.select_one("section#characteristics")
    diagnostics = {
        "selected_selector": None,
        "selected_text_length": 0,
        "selected_text": "",
        "has_description_section": description_section is not None,
        "has_characteristics_section": characteristics_section is not None,
        "candidate_blocks": [],
        "rejected_blocks": [],
    }

    def _record_candidate(selector: str, text: str, *, accepted: bool, reason: str) -> None:
        preview = text[:300]
        bucket = diagnostics["candidate_blocks"] if accepted else diagnostics["rejected_blocks"]
        bucket.append(
            {
                "selector": selector,
                "text_length": len(text),
                "preview": preview,
                "reason": reason,
            }
        )

    def _section_lines(section) -> list[str]:
        if section is None:
            return []

        section_soup = BeautifulSoup(str(section), "html.parser")
        for selector in (
            "section#characteristics",
            ".vr-block-char",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
        ):
            for node in section_soup.select(selector):
                node.decompose()

        lines = [
            _normalize_text(line)
            for line in section_soup.get_text("\n", strip=True).splitlines()
        ]
        return [line for line in lines if line]

    def _section_text(section) -> tuple[str, str | None]:
        if section is None:
            return "", None

        section_soup = BeautifulSoup(str(section), "html.parser")
        for selector in (
            "section#characteristics",
            ".vr-block-char",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
        ):
            for node in section_soup.select(selector):
                node.decompose()

        preferred_chunks: list[str] = []
        selected_selector = None
        for selector in (
            ".vr-product-content__text",
            ".vr-section-block_body",
            ".vr-block-desc__list",
        ):
            nodes = section_soup.select(selector)
            for node in nodes:
                text = _normalize_text(node.get_text("\n", strip=True))
                if text:
                    preferred_chunks.append(text)
                    if selected_selector is None:
                        selected_selector = f"section#description {selector}"
                    _record_candidate(
                        f"section#description {selector}",
                        text,
                        accepted=True,
                        reason="preferred description block",
                    )

        if preferred_chunks:
            return "\n".join(dict.fromkeys(preferred_chunks)).strip(), selected_selector

        fallback_text = _normalize_text(section_soup.get_text("\n", strip=True))
        if fallback_text:
            _record_candidate(
                "section#description",
                fallback_text,
                accepted=True,
                reason="fallback text inside section#description",
            )
        return fallback_text, "section#description" if fallback_text else None

    description_text, selected_selector = _section_text(description_section)
    characteristics_text, _characteristics_selector = _section_text(characteristics_section)
    if characteristics_text:
        _record_candidate(
            "section#characteristics",
            characteristics_text,
            accepted=False,
            reason="forbidden source; characteristics are not full description",
        )
    description_lines = _section_lines(description_section)
    marker_index = None

    for index, line in enumerate(description_lines):
        normalized = _normalized_viyar_description_heading(line)
        if normalized == "опис":
            marker_index = index
            break
        if normalized.startswith("опис:"):
            marker_index = index
            break

    if marker_index is not None:
        collected: list[str] = [description_lines[marker_index]]
        stop_markers = {
            "характеристики",
            "основні характеристики продукту",
            "відгуки",
            "питання",
            "доставка",
            "оплата",
            "table",
            "header",
        }

        for next_line in description_lines[marker_index + 1 :]:
            next_normalized = _normalized_viyar_description_heading(next_line)
            if next_normalized in stop_markers:
                break
            collected.append(next_line)
            if len(" ".join(collected)) >= VIYAR_DESCRIPTION_MAX_LENGTH:
                break

        description_text = "\n".join(collected).strip()
        selected_selector = selected_selector or "section#description"
        if description_text:
            _record_candidate(
                selected_selector,
                description_text,
                accepted=True,
                reason="description block starting from explicit marker",
            )

    if marker_index is not None and _is_viyar_valid_full_description_text(description_text):
        payload = {
            "full_description": description_text,
            "rules_parse_status": "parsed",
            "rules_parsed_at": datetime.utcnow(),
        }
        if diagnostic:
            diagnostics["selected_selector"] = selected_selector or "section#description"
            diagnostics["selected_text_length"] = len(description_text)
            diagnostics["selected_text"] = description_text[:300]
            payload["diagnostics"] = diagnostics
        return payload

    if description_section is not None:
        suspicious_text = "\n".join(
            part for part in (description_text, characteristics_text) if part
        ).lower()
        has_suspicious_noise = any(
            marker in suspicious_text
            for marker in (
                "код:",
                "ціна viyarpro",
                "строки",
                "грн/шт",
                "основні характеристики продукту",
                "технічні характеристики та функціональність",
                "тип товару",
                "тип послуги",
                "виробник",
                "країна виробник",
                "viyarpro",
            )
        )

        payload = {
            "full_description": None,
            "rules_parse_status": (
                "needs_review"
                if has_suspicious_noise
                else "no_full_description"
            ),
            "rules_parsed_at": None,
        }
        if diagnostic:
            diagnostics["selected_selector"] = selected_selector or "section#description"
            diagnostics["selected_text_length"] = len(description_text)
            diagnostics["selected_text"] = description_text[:300]
            payload["diagnostics"] = diagnostics
        return payload

    if _is_viyar_valid_full_description_text(characteristics_text):
        payload = {
            "full_description": None,
            "rules_parse_status": "needs_review",
            "rules_parsed_at": None,
        }
        if diagnostic:
            diagnostics["selected_selector"] = None
            diagnostics["selected_text_length"] = len(characteristics_text)
            diagnostics["selected_text"] = characteristics_text[:300]
            payload["diagnostics"] = diagnostics
        return payload

    payload = {
        "full_description": None,
        "rules_parse_status": "no_full_description",
        "rules_parsed_at": None,
    }
    if diagnostic:
        diagnostics["selected_selector"] = selected_selector
        diagnostics["selected_text_length"] = len(description_text)
        diagnostics["selected_text"] = description_text[:300]
        payload["diagnostics"] = diagnostics
    return payload


def _slugify(value: str) -> str:

    normalized = _normalize_text(value).lower()
    slug = re.sub(r"[^a-z0-9?-?????]+", "-", normalized, flags=re.IGNORECASE)
    return slug.strip("-") or "service"


def _extract_service_entries_from_html(
    html: str,
    page: dict[str, Any],
    audit: dict[str, int] | None = None,
) -> list[dict[str, Any]]:

    soup = BeautifulSoup(html, "html.parser")
    entries: list[dict[str, Any]] = []
    seen_codes: set[str] = set()

    for card in soup.select(".vr-product__card"):
        _bump_viyar_service_audit(audit, "total_records")
        article = _normalize_text(card.get("data-owner-id"))
        name = _normalize_text(card.get("data-sort-name"))
        raw_price = _normalize_text(card.get("data-price") or card.get("data-sort-price"))

        if _is_blocked_viyar_service_name(name):
            _mark_viyar_service_rejection(audit, suspicious=True)
            continue

        if not raw_price:
            _mark_viyar_service_rejection(audit, missing_price=True)
            continue

        try:
            price = float(raw_price.replace(" ", "").replace(",", "."))
        except ValueError:
            price, _ = _extract_price_from_text(raw_price)

        if price is None:
            _mark_viyar_service_rejection(audit, missing_price=True)
            continue

        link = card.select_one("a.vr-card__link")
        href = _normalize_text(link.get("href")) if link else ""
        source_url = urljoin(page["url"], href) if href else page["url"]
        description = page.get("description")
        entry_key = article or _slugify(name)
        external_code = f"viyar-service-{page['code']}-{entry_key}"
        resolved_article = article or _extract_article_from_text(name, source_url)

        if external_code in seen_codes:
            continue

        seen_codes.add(external_code)
        _bump_viyar_service_audit(audit, "valid_services")
        if not resolved_article:
            _bump_viyar_service_audit(audit, "records_without_article")
        entries.append(
            {
                "article": resolved_article,
                "base_price": price,
                "currency": "UAH",
                "description": description,
                "external_code": external_code,
                "is_active": True,
                "is_calculable": True,
                "item_type": "service",
                "name": name,
                "parent_external_code": f"viyar-folder-{page['group_code']}",
                "slug": f"{page['slug']}-{_slugify(name)}",
                "sort_order": len(entries) + 1,
                "source": "viyar",
                "source_url": source_url,
                "unit": "service",
            }
        )

    if entries:
        return entries

    for row in soup.select("table tr"):
        cells = [
            _normalize_text(cell.get_text(" ", strip=True))
            for cell in row.find_all(["td", "th"])
        ]
        cells = [cell for cell in cells if cell]

        if not cells:
            continue

        _bump_viyar_service_audit(audit, "total_records")
        row_text = _normalize_text(" ".join(cells))
        price, _ = _extract_price_from_text(row_text)

        if price is None:
            _mark_viyar_service_rejection(audit, missing_price=True)
            continue

        name_candidates = [
            cell
            for cell in cells
            if _normalize_text(cell).lower() not in {"????", "????????", "???", "uah"}
        ]
        if not name_candidates:
            _mark_viyar_service_rejection(audit, suspicious=True)
            continue

        name = name_candidates[0]
        if len(name) < 3 or _is_blocked_viyar_service_name(name):
            _mark_viyar_service_rejection(audit, suspicious=True)
            continue

        description = " | ".join(name_candidates[1:3]) if len(name_candidates) > 1 else page.get("description")
        article = _extract_article_from_text(row_text, page["url"])
        entry_slug = _slugify(name)
        external_code = f"viyar-service-{page['code']}-{entry_slug}"

        if external_code in seen_codes:
            continue

        seen_codes.add(external_code)
        _bump_viyar_service_audit(audit, "valid_services")
        if not article:
            _bump_viyar_service_audit(audit, "records_without_article")
        entries.append(
            {
                "article": article,
                "base_price": price,
                "currency": "UAH",
                "description": description,
                "external_code": external_code,
                "is_active": True,
                "is_calculable": True,
                "item_type": "service",
                "name": name,
                "parent_external_code": f"viyar-folder-{page['group_code']}",
                "slug": f"{page['slug']}-{entry_slug}",
                "sort_order": len(entries) + 1,
                "source": "viyar",
                "source_url": page["url"],
                "unit": "service",
            }
        )

    return entries


def _extract_descriptions(soup: BeautifulSoup) -> dict[str, str]:

    descriptions: dict[str, str] = {}

    for heading in soup.find_all(["h2", "h3"]):

        title = _normalize_text(heading.get_text(" ", strip=True))

        if title not in FALLBACK_CODE_BY_NAME:
            continue

        parts: list[str] = []
        sibling = heading.find_next_sibling()

        while sibling and getattr(sibling, "name", None) not in {"h2", "h3"}:

            text = _normalize_text(sibling.get_text(" ", strip=True))

            if text:
                parts.append(text)

            sibling = sibling.find_next_sibling()

        if parts:
            descriptions[title] = " ".join(parts[:2])

    return descriptions


def _extract_service_folders(soup: BeautifulSoup) -> list[dict[str, Any]]:

    folders: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    descriptions = _extract_descriptions(soup)

    for anchor in soup.select("a[href]"):

        name = _normalize_text(anchor.get_text(" ", strip=True))

        if name not in FALLBACK_CODE_BY_NAME:
            continue

        folder_meta = FALLBACK_CODE_BY_NAME[name]
        code = folder_meta["code"]

        if code in seen_codes:
            continue

        href = anchor.get("href") or ""
        extracted_source_url = urljoin(VIYAR_SERVICES_URL, href) if href else VIYAR_SERVICES_URL
        source_url = folder_meta.get("source_url") or extracted_source_url

        folders.append(
            {
                "code": code,
                "name": name,
                "slug": folder_meta["slug"],
                "description": descriptions.get(name) or folder_meta["description"],
                "source_url": source_url,
                "pages": folder_meta.get("pages", []),
            }
        )
        seen_codes.add(code)

    if folders:
        return sorted(
            folders,
            key=lambda item: next(
                (
                    index
                    for index, folder in enumerate(FALLBACK_SERVICE_FOLDERS)
                    if folder["code"] == item["code"]
                ),
                999,
            ),
        )

    return [
        {
            **folder,
            "source_url": folder.get("source_url") or _source_url_from_service_code(folder["code"]),
        }
        for folder in FALLBACK_SERVICE_FOLDERS
    ]


def fetch_viyar_service_folders(
    use_remote: bool = True,
) -> list[dict[str, Any]]:

    if not use_remote:
        return [
            {
                **folder,
                "source_url": folder.get("source_url") or _source_url_from_service_code(folder["code"]),
            }
            for folder in FALLBACK_SERVICE_FOLDERS
        ]

    request = Request(
        VIYAR_SERVICES_URL,
        headers=_build_request_headers(),
    )

    try:

        with urlopen(request, timeout=20) as response:
            html = response.read().decode("utf-8", errors="ignore")

    except (HTTPError, URLError, TimeoutError):
        return [
            {
                **folder,
                "source_url": folder.get("source_url") or _source_url_from_service_code(folder["code"]),
            }
            for folder in FALLBACK_SERVICE_FOLDERS
        ]

    soup = BeautifulSoup(html, "html.parser")

    return _extract_service_folders(soup)


def _get_viyar_cookie() -> str:

    return os.getenv("VIYAR_COOKIE", "").strip()


def _build_request_headers(
    include_cookie: bool = False,
    cookie_override: str | None = None,
) -> dict[str, str]:

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
    }

    cookie = (cookie_override or _get_viyar_cookie()).strip()

    if include_cookie and cookie:
        headers["Cookie"] = cookie

    return headers


def _fetch_html(
    url: str,
    use_remote: bool = True,
    include_cookie: bool = False,
    cookie_override: str | None = None,
) -> tuple[str | None, bool]:

    if not use_remote:
        return None, False

    request = Request(
        url,
        headers=_build_request_headers(
            include_cookie=include_cookie,
            cookie_override=cookie_override,
        ),
    )

    try:

        with urlopen(request, timeout=20) as response:
            payload = response.read()
            charset = None

            try:
                charset = response.headers.get_content_charset()
            except Exception:
                charset = None

            encodings = [
                charset,
                "utf-8",
                "utf-8-sig",
                "windows-1251",
                "cp1251",
            ]

            seen: set[str] = set()
            for encoding in encodings:
                if not encoding:
                    continue

                normalized_encoding = encoding.lower()
                if normalized_encoding in seen:
                    continue
                seen.add(normalized_encoding)

                try:
                    html = payload.decode(normalized_encoding)
                    break
                except UnicodeDecodeError:
                    html = None
            else:
                html = payload.decode("utf-8", errors="replace")

            final_url = getattr(response, "geturl", lambda: url)()

    except (HTTPError, URLError, TimeoutError):
        return None, False

    auth_required = "login_required" in str(final_url) or "login_required" in html

    return html, auth_required


def _fetch_price_page(
    url: str,
    use_remote: bool = True,
    cookie_override: str | None = None,
) -> tuple[str | None, bool, str]:

    html, auth_required = _fetch_html(
        url,
        use_remote=use_remote,
        include_cookie=False,
        cookie_override=None,
    )

    if html and not auth_required:
        return html, False, "public"

    if (cookie_override or _get_viyar_cookie()).strip():
        cookie_html, cookie_auth_required = _fetch_html(
            url,
            use_remote=use_remote,
            include_cookie=True,
            cookie_override=cookie_override,
        )

        if cookie_html:
            return cookie_html, cookie_auth_required, "cookie"

    return html, auth_required, "public"


def _extract_price_from_html(
    html: str,
) -> tuple[float | None, str | None]:

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    candidates = _extract_price_candidates(text)
    return _select_price_candidate(candidates)


def _extract_price_from_text(
    text: str,
) -> tuple[float | None, str | None]:

    normalized = _normalize_text(text)

    if not normalized:
        return None, None

    candidates = _extract_price_candidates(normalized)
    return _select_price_candidate(candidates)


def _extract_price_candidates(text: str) -> list[tuple[float, str]]:

    normalized = _normalize_text(text)

    if not normalized:
        return []

    candidates: list[tuple[float, str]] = []
    seen: set[tuple[float, str]] = set()

    for match in PRICE_PATTERN.finditer(normalized):
        raw_label = _normalize_text(match.group(0))
        raw_value = match.group(1).replace(" ", "").replace("\u00a0", "").replace(",", ".")

        try:
            value = float(raw_value)
        except ValueError:
            continue

        # Ignore obviously broken or meaningless values.
        if value <= 0 or value > 100000:
            continue

        key = (value, raw_label)
        if key in seen:
            continue

        seen.add(key)
        candidates.append((value, raw_label))

    return candidates


def _select_price_candidate(
    candidates: list[tuple[float, str]],
) -> tuple[float | None, str | None]:

    if not candidates:
        return None, None

    distinct_values = {value for value, _ in candidates}

    if len(distinct_values) != 1:
        return None, None

    value, label = candidates[0]
    return value, label


def _fallback_article_from_url(url: str) -> str:

    slug = url.rstrip("/").split("/")[-1].split("?")[0].strip()

    if not slug:
        return "VIYAR-SERVICE"

    return slug.replace("-", "_").upper()


def _source_url_from_service_code(code: str | None) -> str:

    if not code:
        return VIYAR_SERVICES_URL

    return VIYAR_SERVICE_PAGE_BY_CODE.get(code, VIYAR_SERVICES_URL)


def _normalize_service_source_url(
    source_url: str | None,
    external_code: str | None = None,
    article: str | None = None,
) -> str:

    normalized = (source_url or "").strip()

    if normalized and "catalog/uslugi" not in normalized:
        return normalized

    code = None

    if external_code and external_code.startswith("viyar-service-"):
        code = external_code.removeprefix("viyar-service-")

    if not code and article:
        normalized_article = _normalize_text(article).replace("-", "_").upper()
        for folder in FALLBACK_SERVICE_FOLDERS:
            if folder["code"].upper() == normalized_article:
                code = folder["code"]
                break

    return _source_url_from_service_code(code)


def _is_valid_article(value: str | None) -> bool:
    return _normalize_viyar_numeric_article(value) is not None


def _extract_article_from_html(
    html: str,
    source_url: str,
) -> str | None:

    soup = BeautifulSoup(html, "html.parser")

    meta_candidates = [
        soup.find(attrs={"itemprop": "sku"}),
        soup.find("meta", attrs={"property": "product:retailer_item_id"}),
        soup.find("meta", attrs={"property": "product:sku"}),
        soup.find("meta", attrs={"name": "sku"}),
    ]

    for candidate in meta_candidates:
        if not candidate:
            continue

        if candidate.name == "meta":
            value = _normalize_text(candidate.get("content"))
        else:
            value = _normalize_text(candidate.get_text(" ", strip=True))

        normalized_value = _normalize_viyar_numeric_article(value)
        if normalized_value:
            return normalized_value

    text = soup.get_text(" ", strip=True)

    for pattern in ARTICLE_PATTERNS:
        match = pattern.search(text)
        if match:
            article = _normalize_text(match.group(1))
            normalized_article = _normalize_viyar_numeric_article(article)
            if normalized_article:
                return normalized_article

    return None


def _extract_article_from_text(
    text: str,
    source_url: str,
) -> str | None:

    normalized = _normalize_text(text)

    if normalized:
        for pattern in ARTICLE_PATTERNS:
            match = pattern.search(normalized)
            if match:
                article = _normalize_text(match.group(1))
                normalized_article = _normalize_viyar_numeric_article(article)
                if normalized_article:
                    return normalized_article

    return None


def _fetch_rendered_price_pages(
    service_items: list[dict[str, Any]],
    cookie_override: str | None,
) -> dict[str, dict[str, Any]]:

    if not service_items:
        return {}

    payload = {
        "cookie": cookie_override,
        "items": [
            {
                "external_code": item["external_code"],
                "source_url": item.get("source_url") or VIYAR_SERVICES_URL,
            }
            for item in service_items
        ],
    }

    try:
        completed = subprocess.run(
            [sys.executable, str(PRICE_WORKER_PATH)],
            input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            capture_output=True,
            timeout=PRICE_WORKER_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception:
        return {}

    stdout = (completed.stdout or b"").decode("utf-8", errors="replace").strip()

    if not stdout:
        return {}

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return {}

    if not isinstance(result, dict) or not result.get("success"):
        return {}

    rendered: dict[str, dict[str, Any]] = {}

    for row in result.get("results") or []:
        external_code = row.get("external_code")
        if external_code:
            rendered[external_code] = row

    return rendered


def build_viyar_service_catalog_records(
    use_remote: bool = True,
    cookie_override: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:

    folders = fetch_viyar_service_folders(
        use_remote=use_remote
    )
    audit = _build_viyar_service_audit()
    rendered_pages = _fetch_rendered_price_pages(
        [
            {
                "external_code": f"viyar-page-{page['code']}",
                "source_url": page["url"],
            }
            for folder in folders
            for page in (folder.get("pages") or [])
        ],
        cookie_override=cookie_override,
    )
    description_details_by_source_url: dict[str, dict[str, Any]] = {}

    records: list[dict[str, Any]] = [
        {
            "source": "viyar",
            "external_code": "viyar-services",
            "parent_external_code": None,
            "name": "Виробничі послуги Viyar",
            "slug": "viyar-services",
            "item_type": "folder",
            "folder_path": "viyar-services",
            "description": (
                "Ієрархічний каталог виробничих послуг Viyar, "
                "підготовлений для використання у прорахунку."
            ),
            "article": None,
            "unit": None,
            "base_price": None,
            "currency": "UAH",
            "source_url": VIYAR_SERVICES_URL,
            "is_calculable": False,
            "sort_order": 0,
            "is_active": True,
        }
    ]

    for index, folder in enumerate(folders, start=1):

        folder_code = f"viyar-folder-{folder['code']}"
        folder_path = f"viyar-services/{folder['slug']}"

        records.append(
            {
                "source": "viyar",
                "external_code": folder_code,
                "parent_external_code": "viyar-services",
                "name": folder["name"],
                "slug": folder["slug"],
                "item_type": "folder",
                "folder_path": folder_path,
                "description": folder.get("description"),
                "article": None,
                "unit": None,
                "base_price": None,
                "currency": "UAH",
                "source_url": folder.get("source_url") or VIYAR_SERVICES_URL,
                "is_calculable": False,
                "sort_order": index,
                "is_active": True,
            }
        )

        for page_index, page in enumerate(folder.get("pages") or [], start=1):
            page_description = page.get("description") or folder.get("description")

            page_meta = {
                **page,
                "description": page_description,
                "group_code": folder["code"],
            }
            html, auth_required = _fetch_html(
                page["url"],
                use_remote=use_remote,
                include_cookie=False,
                cookie_override=None,
            )
            discovered_entries = (
                _extract_service_entries_from_html(html, page_meta, audit=audit)
                if html and not auth_required
                else []
            )

            if not discovered_entries:
                rendered_page = rendered_pages.get(f"viyar-page-{page['code']}") or {}
                rendered_html = rendered_page.get("html") or ""
                if rendered_page.get("success") and rendered_html:
                    discovered_entries = _extract_service_entries_from_html(
                        rendered_html,
                        page_meta,
                        audit=audit,
                    )

            if discovered_entries:
                for discovered_index, entry in enumerate(discovered_entries, start=1):
                    source_url = _normalize_text(entry.get("source_url")) or page["url"]
                    description_details = description_details_by_source_url.get(source_url)

                    if description_details is None:
                        description_details = _fetch_viyar_service_full_description(
                            source_url,
                            use_remote=use_remote,
                            cookie_override=cookie_override,
                        )
                        description_details_by_source_url[source_url] = description_details

                    records.append(
                        {
                            **entry,
                            **description_details,
                            "folder_path": folder_path,
                            "sort_order": page_index * 1000 + discovered_index,
                        }
                    )

    return records, audit


def fetch_viyar_service_price_updates(
    service_items: list[dict[str, Any]],
    use_remote: bool = True,
    cookie_override: str | None = None,
) -> dict[str, Any]:

    updates: list[dict[str, Any]] = []
    auth_required = False
    source_modes: set[str] = set()
    rendered_pages = _fetch_rendered_price_pages(
        service_items,
        cookie_override=cookie_override,
    )

    for item in service_items:
        source_url = _normalize_service_source_url(
            item.get("source_url"),
            external_code=item.get("external_code"),
            article=item.get("article"),
        )
        html, page_requires_auth, fetch_mode = _fetch_price_page(
            source_url,
            use_remote=use_remote,
            cookie_override=cookie_override,
        )
        source_modes.add(fetch_mode)
        auth_required = auth_required or page_requires_auth
        rendered_page = rendered_pages.get(item["external_code"]) or {}
        rendered_html = rendered_page.get("html") or ""
        rendered_text = rendered_page.get("body_text") or ""
        rendered_final_url = rendered_page.get("final_url") or source_url
        rendered_login_required = "login_required" in rendered_final_url.lower()

        if rendered_page.get("success"):
            source_modes.add("rendered")
            auth_required = auth_required or rendered_login_required

        if (not html or page_requires_auth) and rendered_page.get("success"):
            html = rendered_html
            page_requires_auth = rendered_login_required

        article = (
            _extract_article_from_html(html, source_url)
            if html
            else _fallback_article_from_external_code(item.get("external_code"))
        )

        if rendered_text:
            rendered_article = _extract_article_from_text(rendered_text, source_url)
            if _is_valid_article(rendered_article):
                article = rendered_article

        if not html or page_requires_auth:
            updates.append(
                {
                    "article": (
                        article
                        or _normalize_viyar_numeric_article(item.get("article"))
                        or _fallback_article_from_external_code(item.get("external_code"))
                    ),
                    "external_code": item["external_code"],
                    "status": "auth_required" if page_requires_auth else "skipped",
                    "price_source_label": None,
                    "price_source_mode": fetch_mode,
                }
            )
            continue

        html_text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        html_candidates = _extract_price_candidates(html_text)
        rendered_candidates = _extract_price_candidates(rendered_text) if rendered_text else []
        ambiguous_candidates = html_candidates if len({value for value, _ in html_candidates}) > 1 else rendered_candidates

        if len({value for value, _ in ambiguous_candidates}) > 1:
            updates.append(
                {
                    "article": article,
                    "external_code": item["external_code"],
                    "status": "ambiguous",
                    "price_source_label": "; ".join(label for _, label in ambiguous_candidates[:3]),
                    "price_source_mode": fetch_mode,
                }
            )
            continue

        price, price_label = _extract_price_from_html(html)

        if price is None and rendered_text:
            price, price_label = _extract_price_from_text(rendered_text)
            if price is not None:
                fetch_mode = "rendered"

        if price is None:
            updates.append(
                {
                    "article": article,
                    "external_code": item["external_code"],
                    "status": "not_found",
                    "price_source_label": None,
                    "price_source_mode": fetch_mode,
                }
            )
            continue

        updates.append(
            {
                "article": article,
                "base_price": price,
                "currency": "UAH",
                "external_code": item["external_code"],
                "price_source_label": price_label,
                "price_source_mode": fetch_mode,
                "status": "priced",
            }
        )

    if source_modes == {"public"}:
        source_mode = "viyar-public"
    elif source_modes == {"cookie"}:
        source_mode = "viyar-auth-fallback"
    elif source_modes:
        source_mode = "viyar-mixed"
    else:
        source_mode = "viyar"

    return {
        "auth_required": auth_required,
        "source": source_mode,
        "updates": updates,
    }
