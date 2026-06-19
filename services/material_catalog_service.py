import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


VIYAR_BASE_URL = "https://www.viyar.ua"
WORKER_PATH = Path(__file__).with_name("material_catalog_worker.py")
WORKER_TIMEOUT_SECONDS = 45
CITY_COOKIES = {
    "kyiv": "KYIV",
    "lviv": "LVIV",
    "dnipro": "DNIPRO",
    "odessa": "ODESA",
    "kharkiv": "KHARKIV",
    "khmelnytskyi": "KHMELNYTSKYI",
    "rivne": "RIVNE",
}


class MaterialImportError(RuntimeError):

    def __init__(
        self,
        message: str,
        *,
        trace: list[dict] | None = None,
        strategy: str | None = None,
        source_url: str | None = None,
    ):
        super().__init__(message)
        self.trace = trace or []
        self.strategy = strategy
        self.source_url = source_url


def _push_trace(trace: list[dict], stage: str, **payload) -> None:

    entry = {"stage": stage}

    for key, value in payload.items():
        if value is None:
            continue
        entry[key] = value

    trace.append(entry)


def _normalize_text(value) -> str:

    return " ".join(str(value or "").split()).strip()


def _extract_price(value: str | None) -> float | None:

    normalized = (
        _normalize_text(value)
        .replace("грн", "")
        .replace("₴", "")
        .replace(" ", "")
    )

    if not normalized:
        return None

    normalized = normalized.replace(",", ".")

    try:
        return float(normalized)
    except ValueError:
        return None


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str:

    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = _normalize_text(node.get_text(" ", strip=True))
            if text:
                return text

    return ""


def _first_attr(soup: BeautifulSoup, selectors: list[str], attr: str) -> str | None:

    for selector in selectors:
        node = soup.select_one(selector)
        if node and node.get(attr):
            value = _normalize_text(node.get(attr))
            if value:
                return value

    return None


def _normalize_asset_url(value: str | None) -> str | None:

    asset = _normalize_text(value)

    if not asset:
        return None

    if asset.startswith(("data:", "blob:")):
        return asset

    # Responsive image sets are ordered inconsistently across providers.
    # Pick the largest declared candidate instead of the first thumbnail.
    if "," in asset:
        srcset_candidates: list[tuple[float, str]] = []

        for index, candidate in enumerate(asset.split(",")):
            parts = candidate.strip().split()

            if not parts:
                continue

            score = float(index)

            if len(parts) > 1:
                descriptor = parts[-1].lower()

                try:
                    if descriptor.endswith("w"):
                        score = float(descriptor[:-1])
                    elif descriptor.endswith("x"):
                        score = float(descriptor[:-1]) * 10000
                except ValueError:
                    pass

            srcset_candidates.append((score, parts[0]))

        if srcset_candidates:
            asset = max(srcset_candidates, key=lambda item: item[0])[1]

    if asset.startswith("//"):
        return f"https:{asset}"

    if asset.startswith("http"):
        return asset

    if asset.startswith("/"):
        return f"{VIYAR_BASE_URL}{asset}"

    return f"{VIYAR_BASE_URL}/{asset.lstrip('/')}"


def _normalize_article(value: str | None) -> str:

    return "".join(re.findall(r"\d+", str(value or "")))


def _extract_dimensions_from_text(value: str | None) -> str | None:

    text = _normalize_text(value)

    if not text:
        return None

    match = re.search(
        r"(\d{2,4}\s*[xх×]\s*\d{2,4}\s*[xх×]\s*\d{1,3}\s*(?:мм|mm)?)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    return (
        match.group(1)
        .replace("х", "x")
        .replace("×", "x")
        .replace("mm", "мм")
    )


def _extract_thickness_from_text(value: str | None) -> str | None:

    text = _normalize_text(value)

    if not text:
        return None

    dimensions = _extract_dimensions_from_text(text)

    if dimensions:
        match = re.search(r"x\s*(\d{1,3})\s*(?:мм|mm)?$", dimensions, re.IGNORECASE)
        if match:
            return f"{match.group(1)} мм"

    match = re.search(r"(\d{1,2}(?:[.,]\d)?)\s*(?:мм|mm)\b", text, re.IGNORECASE)
    if match:
        return f"{match.group(1).replace('.', ',')} мм"

    return None


def _extract_color_from_name(name: str | None) -> str | None:

    text = _normalize_text(name)

    if not text:
        return None

    dimensions = _extract_dimensions_from_text(text)
    if dimensions:
        text = text.replace(dimensions, "").strip(" -/,")

    prefixes = [
        "ДСП",
        "ЛДСП",
        "МДФ",
        "ДВП",
        "HDF",
        "Kronospan",
        "Swiss Krono",
        "Egger",
        "SAVIOLA",
        "Vanguard",
    ]

    for prefix in prefixes:
        text = re.sub(rf"^\s*{re.escape(prefix)}\s*", "", text, flags=re.IGNORECASE)

    text = re.sub(r"^\s*[A-ZА-ЯІЇЄ0-9\-_/]+\s+", "", text, flags=re.IGNORECASE)
    text = _normalize_text(text)

    return text or None


def _short_material_name(value: str | None) -> str | None:

    text = _normalize_text(value)

    if not text:
        return None

    text = re.sub(
        r"\s+\d{2,4}\s*[xXхХ×]\s*\d{2,4}\s*[xXхХ×]\s*\d{1,3}\s*(?:мм|mm)?\b.*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" -/,")

    return text or None


def _clean_material_description(description: str | None, name: str | None) -> str | None:

    text = _normalize_text(description)
    short_name = _short_material_name(name) or _normalize_text(name)

    if not text:
        return short_name or None

    lowered = text.lower()
    promo_markers = [
        "інтернет-магазин",
        "пропонує замовити",
        "з доставкою по україні",
        "телефонуйте",
        "купити",
    ]

    if any(marker in lowered for marker in promo_markers):
        return short_name or None

    if short_name and lowered == short_name.lower():
        return short_name

    return text


def _resolve_product_url_from_search_html(html: str, article: str) -> str | None:

    soup = BeautifulSoup(html, "html.parser")
    requested_article = _normalize_article(article)

    link_selectors = [
        ".product-item__name",
        "a[href*='/ua/catalog/']",
        "a[href*='/catalog/']",
    ]
    links = []

    for selector in link_selectors:
        links.extend(soup.select(selector))

    if soup.select_one("h1") and not links:
        return None

    fallback_href = None

    for link in links:
        href = _normalize_text(link.get("href"))
        if href and not fallback_href:
            fallback_href = href

        container = link
        for _ in range(5):
            container = container.parent
            if container is None:
                break
            code_node = container.select_one(
                ".text-code.text-weight-bolder, span.text-code.text-weight-bolder, .text-code"
            )
            if not code_node:
                continue
            found_article = _normalize_article(code_node.get_text(" ", strip=True))
            if requested_article and found_article == requested_article:
                return href

        link_text_article = _normalize_article(link.get_text(" ", strip=True))
        if requested_article and link_text_article == requested_article:
            return href

        if requested_article and requested_article in _normalize_article(link.parent.get_text(" ", strip=True) if link.parent else ""):
            return href

    article_pattern = re.compile(rf"\b{re.escape(requested_article)}\b")

    for text_node in soup.find_all(string=article_pattern):
        current = text_node.parent
        for _ in range(6):
            if current is None:
                break
            anchor = current if getattr(current, "name", None) == "a" else current.find("a", href=True)
            if anchor:
                href = _normalize_text(anchor.get("href"))
                if href:
                    return href
            current = current.parent

    return fallback_href


def _build_request_headers(
    city: str | None = None,
    cookie_override: str | None = None,
) -> dict[str, str]:

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
        "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": f"{VIYAR_BASE_URL}/ua/",
    }

    cookie_parts = []
    filial = CITY_COOKIES.get((city or "").strip().lower())

    if filial:
        cookie_parts.append(f"filial={filial}")

    if cookie_override:
        cookie_parts.append(cookie_override.strip())

    if cookie_parts:
        headers["Cookie"] = "; ".join(part for part in cookie_parts if part)

    return headers


def _fetch_html(
    url: str,
    city: str | None = None,
    cookie_override: str | None = None,
) -> str:

    request = Request(
        url,
        headers=_build_request_headers(
            city=city,
            cookie_override=cookie_override,
        ),
    )

    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def _fetch_binary(
    url: str,
    city: str | None = None,
    cookie_override: str | None = None,
) -> tuple[bytes, str | None, str]:

    request = Request(
        url,
        headers={
            **_build_request_headers(
                city=city,
                cookie_override=cookie_override,
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )

    with urlopen(request, timeout=20) as response:
        return (
            response.read(),
            response.headers.get("Content-Type"),
            response.geturl(),
        )


def resolve_material_image_payload(
    article: str,
    stored_image: str | None = None,
    source_url: str | None = None,
    city: str | None = None,
    cookie_override: str | None = None,
) -> dict | None:

    normalized_article = _normalize_article(article)
    candidates: list[str] = []

    for value in [
        stored_image,
        f"https://www.viyar.ua/store/Items/photos/ph{normalized_article}.jpg" if normalized_article else None,
        f"https://viyar.ua/store/Items/photos/ph{normalized_article}.jpg" if normalized_article else None,
        f"https://viyar.ua/upload/resize_cache/photos/512_512_1/ph{normalized_article}.jpg" if normalized_article else None,
        f"https://www.viyar.ua/upload/resize_cache/photos/512_512_1/ph{normalized_article}.jpg" if normalized_article else None,
    ]:
        normalized_value = _normalize_asset_url(value)
        if normalized_value and normalized_value not in candidates:
            candidates.append(normalized_value)

    for candidate in candidates:
        try:
            image_bytes, content_type, resolved_url = _fetch_binary(
                candidate,
                city=city,
                cookie_override=cookie_override,
            )
        except Exception:
            continue

        if not image_bytes:
            continue

        normalized_content_type = (content_type or "").split(";")[0].strip().lower()

        if normalized_content_type and not normalized_content_type.startswith("image/"):
            continue

        return {
            "bytes": image_bytes,
            "content_type": normalized_content_type or "image/jpeg",
            "resolved_url": resolved_url,
        }

    # Product-page parsing is considerably slower and can be unavailable while
    # the image CDN still works. Use it only after every known image URL failed.
    if source_url:
        try:
            material = _extract_material_from_product_html(
                _fetch_html(
                    source_url,
                    city=city,
                    cookie_override=cookie_override,
                ),
                normalized_article or article,
                source_url,
            )
            candidate = _normalize_asset_url(material.get("image") if material else None)

            if candidate:
                image_bytes, content_type, resolved_url = _fetch_binary(
                    candidate,
                    city=city,
                    cookie_override=cookie_override,
                )
                normalized_content_type = (content_type or "").split(";")[0].strip().lower()

                if image_bytes and (
                    not normalized_content_type
                    or normalized_content_type.startswith("image/")
                ):
                    return {
                        "bytes": image_bytes,
                        "content_type": normalized_content_type or "image/jpeg",
                        "resolved_url": resolved_url,
                    }
        except Exception:
            pass

    return None


def prefetch_material_image_cache(
    article: str,
    stored_image: str | None = None,
    source_url: str | None = None,
    city: str | None = None,
    cookie_override: str | None = None,
) -> dict | None:

    return resolve_material_image_payload(
        article=article,
        stored_image=stored_image,
        source_url=source_url,
        city=city,
        cookie_override=cookie_override,
    )


def fetch_remote_image_payload(
    image_url: str | None,
    city: str | None = None,
    cookie_override: str | None = None,
) -> dict | None:
    normalized_url = _normalize_asset_url(image_url)

    if not normalized_url:
        return None

    try:
        image_bytes, content_type, resolved_url = _fetch_binary(
            normalized_url,
            city=city,
            cookie_override=cookie_override,
        )
    except Exception:
        return None

    normalized_content_type = (content_type or "").split(";")[0].strip().lower()

    if not image_bytes or (
        normalized_content_type
        and not normalized_content_type.startswith("image/")
    ):
        return None

    return {
        "bytes": image_bytes,
        "content_type": normalized_content_type or "image/jpeg",
        "resolved_url": resolved_url,
    }


def warm_material_image_cache_for_item(
    material: dict,
    city: str | None = None,
    cookie_override: str | None = None,
) -> dict | None:

    if not material or material.get("image_cached_bytes"):
        return None

    return prefetch_material_image_cache(
        article=material.get("article", ""),
        stored_image=material.get("image"),
        source_url=material.get("source_url"),
        city=city,
        cookie_override=cookie_override,
    )


def _resolve_product_url(
    article: str,
    city: str | None = None,
    cookie_override: str | None = None,
) -> str | None:

    search_url = f"{VIYAR_BASE_URL}/ua/search/?q={quote(article)}"
    html = _fetch_html(
        search_url,
        city=city,
        cookie_override=cookie_override,
    )
    soup = BeautifulSoup(html, "html.parser")

    if soup.select_one("h1") and not soup.select_one(".product-item__name"):
        return search_url

    href = _resolve_product_url_from_search_html(html, article)

    if not href:
        return None

    if href.startswith("http"):
        return href

    return f"{VIYAR_BASE_URL}{href}"


def _extract_material_from_product_html(
    html: str,
    article: str,
    source_url: str,
) -> dict | None:

    soup = BeautifulSoup(html, "html.parser")
    name = _first_text(
        soup,
        [
            "h1.text.text-weight-dark",
            "h1",
            ".vr-card-info h1",
            ".card-info-head_title h1",
        ],
    ) or article

    article_text = _first_text(
        soup,
        [
            ".text-code.text-weight-bolder",
            "span.text-code.text-weight-bolder",
            ".text-code",
        ],
    )

    if article_text and any(symbol.isdigit() for symbol in article_text):
        article = article_text

    image = (
        _first_attr(
            soup,
            [
                ".vr-about-product img",
                ".vr-card-slider img",
                "img.main-image",
                "[itemprop='image']",
                "picture img",
                "meta[property='og:image']",
            ],
            "src",
        )
        or _first_attr(
            soup,
            [
                ".vr-about-product img",
                ".vr-card-slider img",
                "img.main-image",
                "[itemprop='image']",
                "picture img",
            ],
            "data-src",
        )
        or _first_attr(
            soup,
            [
                ".vr-about-product img",
                ".vr-card-slider img",
                "img.main-image",
                "[itemprop='image']",
                "picture img",
                "picture source",
            ],
            "srcset",
        )
        or _first_attr(
            soup,
            [
                ".vr-about-product img",
                ".vr-card-slider img",
                "img.main-image",
                "[itemprop='image']",
                "picture img",
                "picture source",
            ],
            "data-srcset",
        )
        or _first_attr(
            soup,
            [
                "meta[property='og:image']",
            ],
            "content",
        )
    )

    image = _normalize_asset_url(image)

    price_text = _first_text(
        soup,
        [
            'span[id*="_price"]',
            ".price-actual",
            ".card-info-prices__price-actual",
            ".price-current",
        ],
    )
    unit_text = _first_text(
        soup,
        [
            ".card-info-prices__price-row .text-unit",
            ".text-unit",
        ],
    )
    price = _extract_price(price_text)
    description = (
        _first_attr(
            soup,
            [
                "meta[name='description']",
                "meta[property='og:description']",
            ],
            "content",
        )
        or _first_text(
            soup,
            [
                ".card-info-head_description",
                ".vr-card-info__description",
                ".product-about__description",
            ],
        )
        or name
    )
    description = _clean_material_description(description, name)
    dimensions = _extract_dimensions_from_text(name)
    thickness = (
        _extract_thickness_from_text(name)
        or _extract_thickness_from_text(html)
    )
    color = _extract_color_from_name(name)

    return {
        "article": article,
        "name": name,
        "description": description,
        "color": color,
        "dimensions": dimensions,
        "thickness": thickness,
        "image": image,
        "price": price,
        "price_raw": price_text or None,
        "unit": unit_text or None,
        "source_url": source_url,
    }


def _extract_material_from_search_html(
    html: str,
    article: str,
    source_url: str,
) -> dict | None:

    soup = BeautifulSoup(html, "html.parser")
    price_pattern = re.compile(r"\d[\d\s,.]*\s*(?:грн|₴|uah)?", re.IGNORECASE)

    for text_node in soup.find_all(string=price_pattern):
        price_text = _normalize_text(text_node)
        container = text_node.parent

        for _ in range(6):
            if container is None:
                break

            anchor = container if getattr(container, "name", None) == "a" else container.find("a", href=True)
            image_node = container.find("img")

            name_candidates = []
            if anchor:
                name_candidates.append(_normalize_text(anchor.get_text(" ", strip=True)))

            for selector in ["strong", "h3", "h2", ".product-item__name", ".search-product__title"]:
                node = container.select_one(selector) if hasattr(container, "select_one") else None
                if node:
                    name_candidates.append(_normalize_text(node.get_text(" ", strip=True)))

            name = next((item for item in name_candidates if len(item) >= 8), "")
            href = _normalize_text(anchor.get("href")) if anchor and anchor.get("href") else ""

            if name and price_text:
                if href and not href.startswith("http"):
                    href = f"{VIYAR_BASE_URL}{href}"

                image = None
                if image_node:
                    image = (
                        image_node.get("src")
                        or image_node.get("data-src")
                        or image_node.get("srcset")
                        or image_node.get("data-srcset")
                    )
                image = _normalize_asset_url(image)

                return {
                    "article": article,
                    "name": name,
                    "image": image,
                    "price": _extract_price(price_text),
                    "price_raw": price_text,
                    "unit": None,
                    "source_url": href or source_url,
                }

            container = container.parent

    return None


def _extract_material_from_search_html_v2(
    html: str,
    article: str,
    source_url: str,
) -> dict | None:

    soup = BeautifulSoup(html, "html.parser")
    requested_article = _normalize_article(article)
    candidates: list[dict] = []

    for anchor in soup.select("a[href*='/catalog/'], a[href*='/ua/catalog/']"):
        href = _normalize_text(anchor.get("href"))
        if not href:
            continue

        container = anchor
        for _ in range(6):
            next_parent = container.parent
            if next_parent is None:
                break
            container = next_parent

        container_text = _normalize_text(container.get_text(" ", strip=True))
        if not container_text:
            continue

        name_candidates = [_normalize_text(anchor.get_text(" ", strip=True))]
        for selector in ["strong", "h3", "h2", ".product-item__name", ".search-product__title"]:
            node = container.select_one(selector)
            if node:
                name_candidates.append(_normalize_text(node.get_text(" ", strip=True)))

        name = next((item for item in name_candidates if len(item) >= 8), "")
        price_candidates = re.findall(r"\d[\d\s,.]*\s*(?:грн|₴|uah)?", container_text, re.IGNORECASE)
        price_text = next((item for item in price_candidates if _extract_price(item) is not None), "")

        image_node = container.find("img")
        image = None
        if image_node:
            image = (
                image_node.get("src")
                or image_node.get("data-src")
                or image_node.get("srcset")
                or image_node.get("data-srcset")
            )
        image = _normalize_asset_url(image)

        normalized_href = href if href.startswith("http") else f"{VIYAR_BASE_URL}{href}"
        href_digits = _normalize_article(href)
        text_digits = _normalize_article(container_text)

        score = 0
        if requested_article and requested_article in href_digits:
            score += 5
        if requested_article and requested_article in text_digits:
            score += 4
        if requested_article and f"ms_q={requested_article}" in normalized_href:
            score += 6
        if name:
            score += 1
        if price_text:
            score += 1
        if image:
            score += 1

        if name and price_text:
            candidates.append(
                {
                    "article": article,
                    "name": name,
                    "image": image,
                    "price": _extract_price(price_text),
                    "price_raw": price_text,
                    "unit": None,
                    "source_url": normalized_href or source_url,
                    "_score": score,
                }
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (item.get("_score", 0), len(item.get("name", ""))),
        reverse=True,
    )
    best = candidates[0]

    if len(candidates) == 1 or best.get("_score", 0) > candidates[1].get("_score", 0):
        return {
            "article": best["article"],
            "name": best["name"],
            "image": best["image"],
            "price": best["price"],
            "price_raw": best["price_raw"],
            "unit": best["unit"],
            "source_url": best["source_url"],
        }

    return None


def _looks_like_error_page(html: str, material: dict | None) -> bool:

    haystack = _normalize_text(html).lower()
    name = _normalize_text(material.get("name") if material else "").lower()
    joined = f"{name} {haystack[:1200]}"

    error_markers = [
        "error code 522",
        "connection timed out",
        "cloudflare",
        "web server is down",
        "host error",
    ]

    return any(marker in joined for marker in error_markers)


def _error_page_reason(html: str, material: dict | None) -> str | None:

    if not _looks_like_error_page(html, material):
        return None

    haystack = _normalize_text(html).lower()

    if "error code 522" in haystack or "connection timed out" in haystack:
        return "Viyar host returned Cloudflare 522 (connection timed out)"

    if "cloudflare" in haystack:
        return "Viyar page is blocked by Cloudflare or temporarily unavailable"

    if "web server is down" in haystack or "host error" in haystack:
        return "Viyar host is temporarily unavailable"

    return "Viyar returned an error page"


def _normalize_material_error(error: Exception) -> str:

    text = _normalize_text(str(error))

    if "HTTP Error 522" in text or text.startswith("HTTP Error 522"):
        return (
            "Viyar тимчасово не відповідає. Спробуйте ще раз трохи пізніше. "
            "Сторінка матеріалу зараз недоступна."
        )

    if isinstance(error, HTTPError):
        return f"Viyar повернув HTTP {error.code}"

    if isinstance(error, URLError):
        return "Не вдалося підключитися до Viyar з боку сервера"

    return text or "Не вдалося завантажити матеріал з Viyar"


def _normalize_material_error_clean(error: Exception) -> str:

    text = _normalize_text(str(error))

    if "HTTP Error 522" in text or text.startswith("HTTP Error 522"):
        return (
            "Viyar тимчасово не відповідає. Спробуйте ще раз трохи пізніше. "
            "Сторінка матеріалу зараз недоступна."
        )

    if isinstance(error, HTTPError):
        return f"Viyar повернув HTTP {error.code}"

    if isinstance(error, URLError):
        return "Не вдалося підключитися до Viyar з боку сервера"

    return text or "Не вдалося завантажити матеріал з Viyar"


def _normalize_material_error_message(error: Exception) -> str:

    text = _normalize_text(str(error))

    if "HTTP Error 522" in text or text.startswith("HTTP Error 522"):
        return (
            "Viyar тимчасово не відповідає. Спробуйте ще раз трохи пізніше. "
            "Сторінка матеріалу зараз недоступна."
        )

    if isinstance(error, HTTPError):
        return f"Viyar повернув HTTP {error.code}"

    if isinstance(error, URLError):
        return "Не вдалося підключитися до Viyar з боку сервера"

    return text or "Не вдалося завантажити матеріал з Viyar"


async def _fetch_page_with_retry(page, url: str, retries: int = 3) -> str | None:

    for attempt in range(retries):
        try:
            await page.goto(url, timeout=15000)
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1000 + attempt * 400)
            return await page.content()
        except Exception:
            if attempt == retries - 1:
                return None
            await page.wait_for_timeout(1800)

    return None


async def _search_from_homepage_async(page, article: str, trace: list[dict]) -> str | None:

    homepage_url = f"{VIYAR_BASE_URL}/ua/"
    _push_trace(trace, "async.homepage", url=homepage_url)

    if not await _fetch_page_with_retry(page, homepage_url):
        return None

    input_selectors = [
        "input[type='search']",
        "input[name='q']",
        "input[placeholder*='Пошук']",
        "input[placeholder*='Search']",
    ]

    search_input = None
    for selector in input_selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count():
                search_input = locator
                break
        except Exception:
            continue

    if search_input is None:
        _push_trace(trace, "async.homepage.no_input")
        return None

    await search_input.fill(article)
    _push_trace(trace, "async.homepage.filled", article=article)

    button_selectors = [
        "button:has-text('Шукати')",
        "button:has-text('Search')",
        "button[type='submit']",
    ]

    for selector in button_selectors:
        button = page.locator(selector).first
        try:
            if await button.count():
                await button.click()
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(1200)
                _push_trace(trace, "async.homepage.clicked", selector=selector, final_url=page.url)
                return await page.content()
        except Exception:
            continue

    try:
        await search_input.press("Enter")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1200)
        _push_trace(trace, "async.homepage.enter", final_url=page.url)
        return await page.content()
    except Exception:
        _push_trace(trace, "async.homepage.submit_failed")
        return None


async def _fetch_viyar_material_by_article_async_traced(
    article: str,
    city: str | None = None,
    cookie_override: str | None = None,
    preferred_url: str | None = None,
    trace: list[dict] | None = None,
) -> tuple[dict, dict]:

    trace = trace or []
    normalized_article = _normalize_text(article)
    search_url = f"{VIYAR_BASE_URL}/ua/search/?q={quote(normalized_article)}"

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="uk-UA",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
        )

        cookies = []
        filial = CITY_COOKIES.get((city or "").strip().lower())

        if filial:
            cookies.append(
                {
                    "name": "filial",
                    "value": filial,
                    "domain": ".viyar.ua",
                    "path": "/",
                }
            )

        for chunk in str(cookie_override or "").split(";"):
            part = chunk.strip()
            if not part or "=" not in part:
                continue
            name, value = part.split("=", 1)
            cookies.append(
                {
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".viyar.ua",
                    "path": "/",
                }
            )

        if cookies:
            await context.add_cookies(cookies)
            _push_trace(trace, "async.cookies", count=len(cookies), city=city)

        page = await context.new_page()
        source_url = preferred_url
        html = None

        if preferred_url:
            _push_trace(trace, "async.preferred_url", url=preferred_url)
            html = await _fetch_page_with_retry(page, preferred_url)
            _push_trace(trace, "async.preferred_url.result", loaded=bool(html), final_url=page.url or preferred_url)

        if not html:
            _push_trace(trace, "async.search", url=search_url)
            html = await _fetch_page_with_retry(page, search_url)

            if not html:
                html = await _search_from_homepage_async(page, normalized_article, trace)
                if not html:
                    await context.close()
                    await browser.close()
                    raise RuntimeError("Viyar search page did not load")

            resolved_href = _resolve_product_url_from_search_html(html, normalized_article)
            _push_trace(trace, "async.search.resolved", href=resolved_href)
            search_error_reason = _error_page_reason(html, None)
            if search_error_reason:
                _push_trace(trace, "async.search.error_page", final_url=page.url or search_url, reason=search_error_reason)
                await context.close()
                await browser.close()
                raise RuntimeError(search_error_reason)

            if resolved_href:
                target_url = (
                    resolved_href
                    if resolved_href.startswith("http")
                    else f"{VIYAR_BASE_URL}{resolved_href}"
                )
                html = await _fetch_page_with_retry(page, target_url)
                _push_trace(trace, "async.product", url=target_url, loaded=bool(html), final_url=page.url or target_url)
                if not html:
                    await context.close()
                    await browser.close()
                    raise RuntimeError("Viyar material page did not load")
                source_url = page.url
            else:
                source_url = page.url or search_url
                search_material = _extract_material_from_search_html_v2(
                    html=html,
                    article=normalized_article,
                    source_url=source_url,
                )
                _push_trace(
                    trace,
                    "async.search.extract",
                    source_url=source_url,
                    name=search_material.get("name") if search_material else None,
                    price=search_material.get("price") if search_material else None,
                    has_image=bool(search_material.get("image")) if search_material else False,
                )
                if search_material:
                    await context.close()
                    await browser.close()
                    return search_material, {
                        "strategy": "async_search_results",
                        "source_url": search_material.get("source_url") or source_url,
                        "trace": trace,
                    }
        else:
            source_url = page.url or preferred_url

        material = _extract_material_from_product_html(
            html=html,
            article=normalized_article,
            source_url=source_url,
        )
        material_error_reason = _error_page_reason(html, material)
        _push_trace(
            trace,
            "async.extract",
            source_url=source_url,
            name=material.get("name") if material else None,
            article=material.get("article") if material else None,
            price=material.get("price") if material else None,
            has_image=bool(material.get("image")) if material else False,
            error_page=bool(material_error_reason),
            error_reason=material_error_reason,
        )

        await context.close()
        await browser.close()

        if not material or not material.get("name") or material_error_reason:
            raise LookupError(material_error_reason or "Material details were not found on Viyar")

        return material, {
            "strategy": "async_playwright",
            "source_url": source_url,
            "trace": trace,
        }


async def _fetch_viyar_material_by_article_async(
    article: str,
    city: str | None = None,
    cookie_override: str | None = None,
    preferred_url: str | None = None,
) -> dict:

    normalized_article = _normalize_text(article)
    search_url = f"{VIYAR_BASE_URL}/ua/search/?q={quote(normalized_article)}"

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="uk-UA",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
        )

        cookies = []
        filial = CITY_COOKIES.get((city or "").strip().lower())

        if filial:
            cookies.append(
                {
                    "name": "filial",
                    "value": filial,
                    "domain": ".viyar.ua",
                    "path": "/",
                }
            )

        for chunk in str(cookie_override or "").split(";"):
            part = chunk.strip()
            if not part or "=" not in part:
                continue
            name, value = part.split("=", 1)
            cookies.append(
                {
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".viyar.ua",
                    "path": "/",
                }
            )

        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()
        source_url = preferred_url
        html = None

        if preferred_url:
            html = await _fetch_page_with_retry(page, preferred_url)

        if not html:
            html = await _fetch_page_with_retry(page, search_url)

            if not html:
                await context.close()
                await browser.close()
                raise RuntimeError("Viyar search page did not load")

            resolved_href = _resolve_product_url_from_search_html(html, normalized_article)

            if resolved_href:
                target_url = (
                    resolved_href
                    if resolved_href.startswith("http")
                    else f"{VIYAR_BASE_URL}{resolved_href}"
                )
                html = await _fetch_page_with_retry(page, target_url)
                if not html:
                    await context.close()
                    await browser.close()
                    raise RuntimeError("Viyar material page did not load")
                source_url = page.url
            else:
                source_url = search_url
        else:
            source_url = page.url or preferred_url

        material = _extract_material_from_product_html(
            html=html,
            article=normalized_article,
            source_url=source_url,
        )

        await context.close()
        await browser.close()

        if not material or not material.get("name") or _looks_like_error_page(html, material):
            raise LookupError("Material details were not found on Viyar")

        return material


def _fetch_viyar_material_by_article_subprocess(
    article: str,
    city: str | None = None,
    cookie_override: str | None = None,
    preferred_url: str | None = None,
) -> tuple[dict, dict]:

    payload = {
        "article": article,
        "city": city,
        "cookie": cookie_override,
        "preferred_url": preferred_url,
    }

    try:
        completed = subprocess.run(
            [sys.executable, str(WORKER_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=WORKER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"Viyar material worker timed out after {WORKER_TIMEOUT_SECONDS} seconds"
        )

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if not stdout:
        raise RuntimeError(stderr or "Viyar material worker did not return data")

    result = json.loads(stdout)

    if not isinstance(result, dict):
        raise RuntimeError("Invalid Viyar material worker payload")

    debug_payload = result.get("debug") if isinstance(result.get("debug"), dict) else {}

    if not result.get("success"):
        raise MaterialImportError(
            result.get("error") or stderr or "Unknown Viyar worker error",
            trace=debug_payload.get("trace") or [],
            strategy=debug_payload.get("strategy") or "worker_playwright",
            source_url=debug_payload.get("source_url"),
        )

    return result["material"], {
        "strategy": debug_payload.get("strategy") or "worker_playwright",
        "source_url": debug_payload.get("source_url") or result["material"].get("source_url"),
        "trace": debug_payload.get("trace") or [],
    }


def fetch_viyar_material_by_article(
    article: str,
    city: str | None = None,
    cookie_override: str | None = None,
) -> dict:

    normalized_article = _normalize_text(article)

    if not normalized_article:
        raise ValueError("Article is required")

    direct_error = None

    try:
        product_url = _resolve_product_url(
            normalized_article,
            city=city,
            cookie_override=cookie_override,
        )

        if product_url:
            html = _fetch_html(
                product_url,
                city=city,
                cookie_override=cookie_override,
            )
            material = _extract_material_from_product_html(
                html=html,
                article=normalized_article,
                source_url=product_url,
            )

            if material and material.get("name") and not _looks_like_error_page(html, material):
                return material
    except Exception as error:  # pragma: no cover - fallback path
        direct_error = error

    try:
        material, _debug_payload = _fetch_viyar_material_by_article_subprocess(
            normalized_article,
            city=city,
            cookie_override=cookie_override,
        )
        return material
    except Exception as worker_error:
        if direct_error:
            raise RuntimeError(_normalize_material_error(direct_error)) from worker_error
        raise RuntimeError(_normalize_material_error(worker_error)) from worker_error


async def fetch_viyar_material_by_article_live(
    article: str,
    city: str | None = None,
    cookie_override: str | None = None,
    preferred_url: str | None = None,
) -> dict:

    normalized_article = _normalize_text(article)

    if not normalized_article:
        raise ValueError("Article is required")

    direct_error = None

    try:
        product_url = await asyncio.to_thread(
            _resolve_product_url,
            normalized_article,
            city,
            cookie_override,
        )

        if preferred_url:
            product_url = preferred_url

        if product_url:
            html = await asyncio.to_thread(
                _fetch_html,
                product_url,
                city,
                cookie_override,
            )
            material = _extract_material_from_product_html(
                html=html,
                article=normalized_article,
                source_url=product_url,
            )

            if material and material.get("name") and not _looks_like_error_page(html, material):
                return material
    except Exception as error:
        direct_error = error

    try:
        return await _fetch_viyar_material_by_article_async(
            normalized_article,
            city=city,
            cookie_override=cookie_override,
            preferred_url=preferred_url,
        )
    except Exception as async_error:
        try:
            material, _debug_payload = await asyncio.to_thread(
                _fetch_viyar_material_by_article_subprocess,
                normalized_article,
                city,
                cookie_override,
            )
            return material
        except Exception as worker_error:
            final_error = direct_error or async_error or worker_error
            raise RuntimeError(_normalize_material_error(final_error)) from worker_error


async def fetch_viyar_material_by_article_live_traced(
    article: str,
    city: str | None = None,
    cookie_override: str | None = None,
    preferred_url: str | None = None,
) -> tuple[dict, dict]:

    normalized_article = _normalize_text(article)
    trace: list[dict] = []

    if not normalized_article:
        raise ValueError("Article is required")

    direct_error = None

    try:
        product_url = preferred_url

        if not product_url:
            _push_trace(trace, "direct.resolve_search", article=normalized_article, city=city)
            product_url = await asyncio.to_thread(
                _resolve_product_url,
                normalized_article,
                city,
                cookie_override,
            )
            _push_trace(trace, "direct.resolve_search.result", product_url=product_url)
        else:
            _push_trace(trace, "direct.preferred_url", product_url=product_url)

        if product_url:
            html = await asyncio.to_thread(
                _fetch_html,
                product_url,
                city,
                cookie_override,
            )
            material = _extract_material_from_product_html(
                html=html,
                article=normalized_article,
                source_url=product_url,
            )
            is_error_page = _looks_like_error_page(html, material)
            _push_trace(
                trace,
                "direct.extract",
                product_url=product_url,
                name=material.get("name") if material else None,
                article=material.get("article") if material else None,
                price=material.get("price") if material else None,
                has_image=bool(material.get("image")) if material else False,
                error_page=is_error_page,
            )

            if material and material.get("name") and not is_error_page:
                return material, {
                    "strategy": "direct_html",
                    "source_url": product_url,
                    "trace": trace,
                }
    except Exception as error:
        direct_error = error
        _push_trace(
            trace,
            "direct.error",
            error=type(error).__name__,
            message=_normalize_material_error_message(error),
        )

    try:
        material, debug_payload = await _fetch_viyar_material_by_article_async_traced(
            normalized_article,
            city=city,
            cookie_override=cookie_override,
            preferred_url=preferred_url,
            trace=trace,
        )
        return material, debug_payload
    except Exception as async_error:
        _push_trace(
            trace,
            "async.error",
            error=type(async_error).__name__,
            message=_normalize_material_error_message(async_error),
        )
        try:
            _push_trace(trace, "worker.start", article=normalized_article)
            material, debug_payload = await asyncio.to_thread(
                _fetch_viyar_material_by_article_subprocess,
                normalized_article,
                city,
                cookie_override,
                preferred_url,
            )
            for entry in debug_payload.get("trace") or []:
                trace.append(entry)
            return material, {
                "strategy": debug_payload.get("strategy") or "worker_playwright",
                "source_url": debug_payload.get("source_url") or material.get("source_url"),
                "trace": trace,
            }
        except Exception as worker_error:
            worker_trace = getattr(worker_error, "trace", None) or []
            for entry in worker_trace:
                trace.append(entry)
            _push_trace(
                trace,
                "worker.error",
                error=type(worker_error).__name__,
                message=_normalize_material_error_message(worker_error),
            )
            final_error = direct_error or async_error or worker_error
            raise MaterialImportError(
                _normalize_material_error_message(final_error),
                trace=trace,
                strategy=getattr(worker_error, "strategy", "all_fallbacks_failed"),
                source_url=getattr(worker_error, "source_url", preferred_url),
            ) from worker_error


async def fetch_viyar_product_details_by_url_traced(
    source_url: str,
    city: str | None = None,
    cookie_override: str | None = None,
    article_hint: str | None = None,
) -> tuple[dict, dict]:

    normalized_url = _normalize_text(source_url)
    trace: list[dict] = []

    if not normalized_url:
        raise ValueError("Source URL is required")

    try:
        _push_trace(trace, "direct.product_url", product_url=normalized_url, city=city)
        html = await asyncio.to_thread(
            _fetch_html,
            normalized_url,
            city,
            cookie_override,
        )
        material = _extract_material_from_product_html(
            html=html,
            article=article_hint or normalized_url,
            source_url=normalized_url,
        )
        is_error_page = _looks_like_error_page(html, material)
        _push_trace(
            trace,
            "direct.extract",
            product_url=normalized_url,
            name=material.get("name") if material else None,
            article=material.get("article") if material else None,
            price=material.get("price") if material else None,
            has_image=bool(material.get("image")) if material else False,
            error_page=is_error_page,
        )
        if material and material.get("name") and not is_error_page:
            return material, {
                "strategy": "direct_url_html",
                "source_url": normalized_url,
                "trace": trace,
            }
    except Exception as error:
        _push_trace(
            trace,
            "direct.error",
            error=type(error).__name__,
            message=_normalize_material_error_message(error),
        )

    raise MaterialImportError(
        "Material details were not found by URL",
        trace=trace,
        strategy="direct_url_html",
        source_url=normalized_url,
    )
