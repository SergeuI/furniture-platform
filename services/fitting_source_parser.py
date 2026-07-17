import asyncio
import json
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
}

MT_AUTH_PATH = Path(__file__).with_name("mt_auth.json")


def _material_catalog_service():
    # Import lazily to avoid a module-level cycle with material_catalog_service.
    from services import material_catalog_service

    return material_catalog_service


def _format_browser_runtime_error(error: Exception) -> str:
    message = " ".join(str(error or type(error).__name__).split()).strip()
    lowered = message.lower()

    if "error while loading shared libraries" in lowered or "libatk-1.0.so.0" in lowered:
        return (
            "Браузерний парсер тимчасово недоступний: на сервері не встановлені "
            "системні залежності Playwright Chromium. Виконайте "
            "`sudo ./venv/bin/playwright install-deps chromium` і повторіть імпорт."
        )

    if "executable doesn't exist" in lowered or "browser executable" in lowered:
        return (
            "На сервері не встановлено Chromium для Playwright. Виконайте "
            "`./venv/bin/playwright install chromium` і повторіть імпорт."
        )

    if len(message) > 600:
        return f"{message[:597]}..."

    return message


def _clean_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


_PROMOTIONAL_PHRASE_PATTERNS = (
    r"\bкупити\b",
    r"\bкупить\b",
    r"\bзамовити\b",
    r"\bза\s+\d+(?:[.,]\d+)?\b",
    r"\bдоставка\b",
    r"\bтелефон\w*\b",
    r"\bконсультац\w*\b",
    r"\bлучшие\s+цены\b",
    r"\bцены\b",
    r"\bціни\b",
    r"\bвыбор\b",
    r"\bотличное\s+качество\b",
)


def _looks_like_promotional_copy(value: str | None) -> bool:
    text = _clean_text(value).lower()
    if not text:
        return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in _PROMOTIONAL_PHRASE_PATTERNS)


def _clean_product_name(value: str | None) -> str:
    text = _clean_text(value)
    if not text:
        return ""

    cut_points: list[int] = []
    for pattern in _PROMOTIONAL_PHRASE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            cut_points.append(match.start())

    for separator in (r"\s+[—–-]\s+", r"\s+\|\s+", r"\s+/\s+"):
        match = re.search(separator, text)
        if not match:
            continue
        tail = _clean_text(text[match.end():])
        if tail and _looks_like_promotional_copy(tail):
            cut_points.append(match.start())

    if cut_points:
        text = text[: min(cut_points)].strip(" -—–|/,:;.()[]")

    return _clean_text(text)


def _normalize_asset_url(value: str | None, base_url: str) -> str | None:
    asset = _clean_text(value)

    if not asset:
        return None

    if "," in asset:
        asset = asset.split(",")[0].split(" ")[0].strip()

    if asset.startswith("//"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme or 'https'}:{asset}"

    return urljoin(base_url, asset)


def _extract_price(value: str | None) -> float | None:
    normalized = (
        _clean_text(value)
        .replace("грн", "")
        .replace("₴", "")
        .replace("€", "")
        .replace("$", "")
        .replace("/лист", "")
        .replace("/шт", "")
        .replace("/компл", "")
        .replace(" ", "")
        .replace(",", ".")
    )

    if not normalized:
        return None

    match = re.search(r"\d+(?:\.\d+)?", normalized)
    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        text = _clean_text(node.get_text(" ", strip=True))
        if text:
            return text
    return ""


def _first_meta_content(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        value = _clean_text(node.get("content"))
        if value:
            return value
    return ""


def _extract_description(soup: BeautifulSoup, fallback_name: str) -> str | None:
    description = (
        _first_meta_content(
            soup,
            [
                "meta[name='description']",
                "meta[property='og:description']",
                "meta[name='twitter:description']",
            ],
        )
        or _first_text(
            soup,
            [
                ".card-info-head_description",
                ".vr-card-info__description",
                ".product-about__description",
                ".product-description",
                ".description",
            ],
        )
        or fallback_name
    )
    description = _clean_text(description)
    if not description:
        return None
    if description == _clean_product_name(fallback_name):
        return None
    if _looks_like_promotional_copy(description):
        return None
    return description or None


def _strip_jsonld_image_size(value: str | None) -> str | None:
    image_url = _clean_text(value)
    if not image_url:
        return None

    parsed = urlparse(image_url)
    if not parsed.query:
        return image_url

    query_items = [
        (key, item_value)
        for key, item_value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() != "size"
    ]
    return parsed._replace(query=urlencode(query_items, doseq=True)).geturl()


def _normalize_image_url_for_list(value: object) -> str | None:
    image_url = _clean_text(value if isinstance(value, str) else None)
    if not image_url:
        return None

    parsed = urlparse(image_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None

    query_items = [
        (key, item_value)
        for key, item_value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() != "size"
    ]
    return parsed._replace(query=urlencode(query_items, doseq=True), fragment="").geturl()


def _jsonld_type_is_product(type_value: object) -> bool:
    if isinstance(type_value, str):
        return type_value.rsplit("/", 1)[-1].lower() == "product"
    if isinstance(type_value, list):
        return any(_jsonld_type_is_product(item) for item in type_value)
    return False


def _iter_jsonld_product_nodes(value: object):
    if isinstance(value, list):
        for item in value:
            yield from _iter_jsonld_product_nodes(item)
        return

    if not isinstance(value, dict):
        return

    if _jsonld_type_is_product(value.get("@type")):
        yield value

    graph = value.get("@graph")
    if isinstance(graph, (dict, list)):
        yield from _iter_jsonld_product_nodes(graph)

    for key, nested_value in value.items():
        if key == "@graph":
            continue
        if isinstance(nested_value, (dict, list)):
            yield from _iter_jsonld_product_nodes(nested_value)


def _normalize_jsonld_availability(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None

    token = text.rsplit("/", 1)[-1].lower()
    if token == "instock":
        return "В наявності"
    if token == "outofstock":
        return "Немає в наявності"
    if token == "preorder":
        return "Під замовлення"
    return None


def _normalize_jsonld_image(value: object) -> str | None:
    if isinstance(value, list):
        for item in value:
            image_url = _normalize_jsonld_image(item)
            if image_url:
                return image_url
        return None

    if isinstance(value, dict):
        return _strip_jsonld_image_size(
            value.get("url")
            or value.get("@id")
            or value.get("contentUrl")
            or value.get("image")
        )

    return _normalize_image_url_for_list(value)


def _normalize_jsonld_image_list(value: object) -> list[str]:
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            normalized.extend(_normalize_jsonld_image_list(item))
        return _dedupe_preserve_order(normalized)

    if isinstance(value, dict):
        for key in ("url", "@id", "contentUrl", "image"):
            normalized = _normalize_jsonld_image_list(value.get(key))
            if normalized:
                return normalized
        return []

    image_url = _normalize_image_url_for_list(value)
    return [image_url] if image_url else []


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []

    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)

    return deduped


def _normalize_fitting_image_urls(result: dict) -> dict:
    enriched = dict(result)
    normalized_image_urls: list[str] = []

    raw_image_urls = enriched.get("image_urls")
    if isinstance(raw_image_urls, list):
        for item in raw_image_urls:
            normalized = _normalize_image_url_for_list(item)
            if normalized:
                normalized_image_urls.append(normalized)

    normalized_main_image = _normalize_image_url_for_list(enriched.get("image_url"))
    if normalized_main_image:
        normalized_image_urls = [
            normalized_main_image,
            *[value for value in normalized_image_urls if value != normalized_main_image],
        ]
    else:
        normalized_image_urls = _dedupe_preserve_order(normalized_image_urls)

    enriched["image_urls"] = normalized_image_urls
    return enriched


def _normalize_jsonld_brand(value: object) -> str | None:
    if isinstance(value, dict):
        return _clean_text(value.get("name")) or None
    return _clean_text(value) or None


def _iter_jsonld_offer_nodes(value: object):
    if isinstance(value, list):
        for item in value:
            yield from _iter_jsonld_offer_nodes(item)
        return

    if isinstance(value, dict):
        yield value


def _extract_viyar_characteristics(container: BeautifulSoup | object) -> dict[str, str]:
    if not container:
        return {}

    rows = container.select("tr.vr-block-char__tr") if hasattr(container, "select") else []
    characteristics: dict[str, str] = {}

    for row in rows:
        name_node = row.select_one(".vr-block-char__name")
        value_node = row.select_one(".vr-block-char__value")
        if not name_node or not value_node:
            continue

        name = _clean_text(name_node.get_text(" ", strip=True)).rstrip(":").strip()
        value = _clean_text(value_node.get_text(" ", strip=True))
        if not name or not value:
            continue
        if name in characteristics and characteristics[name]:
            continue

        characteristics[name] = value

    return characteristics


def _extract_product_jsonld(
    soup: BeautifulSoup,
    fallback_name: str | None = None,
    fallback_article: str | None = None,
) -> dict:
    best_node: dict | None = None
    best_score = -1
    normalized_fallback_name = _clean_product_name(fallback_name)
    normalized_fallback_article = _clean_text(fallback_article) or None

    for script in soup.select("script[type='application/ld+json']"):
        raw_json = _clean_text(script.string or script.get_text(" ", strip=True))
        if not raw_json:
            continue

        try:
            payload = json.loads(raw_json)
        except Exception:
            continue

        product_nodes = [node for node in _iter_jsonld_product_nodes(payload) if isinstance(node, dict)]
        if not product_nodes:
            continue

        for node in product_nodes:
            score = 0
            candidate_article = _clean_text(
                node.get("sku")
                or node.get("mpn")
                or node.get("productID")
            )
            candidate_name = _clean_product_name(node.get("name"))

            if normalized_fallback_article and candidate_article == normalized_fallback_article:
                score += 3

            if normalized_fallback_name and candidate_name:
                if candidate_name == normalized_fallback_name:
                    score += 2
                elif (
                    normalized_fallback_name in candidate_name
                    or candidate_name in normalized_fallback_name
                ):
                    score += 1

            if score > best_score:
                best_score = score
                best_node = node

    if not best_node:
        return {}

    name = _clean_product_name(best_node.get("name")) or None
    description = _clean_text(best_node.get("description")) or None
    if description and description == name:
        description = None

    image_urls = _normalize_jsonld_image_list(best_node.get("image"))
    image = image_urls[0] if image_urls else None
    brand = _normalize_jsonld_brand(best_node.get("brand"))
    sku = _clean_text(
        best_node.get("sku")
        or best_node.get("mpn")
        or best_node.get("productID")
    ) or None

    price = None
    currency = None
    availability = None
    for offer in _iter_jsonld_offer_nodes(best_node.get("offers")):
        if not isinstance(offer, dict):
            continue
        if price is None:
            offer_price = offer.get("price")
            if isinstance(offer_price, (int, float)):
                price = float(offer_price)
            else:
                price = _extract_price(offer_price if isinstance(offer_price, str) else None)
        if currency is None:
            currency = _clean_text(offer.get("priceCurrency")) or None
        if availability is None:
            availability = _normalize_jsonld_availability(offer.get("availability"))
        if price is not None and currency is not None and availability is not None:
            break

    return {
        "name": name,
        "sku": sku,
        "description": description,
        "brand": brand,
        "image": image,
        "image_urls": image_urls,
        "price": price,
        "currency": currency,
        "availability": availability,
    }


def _first_attr(soup: BeautifulSoup, selectors: list[str], attr: str, base_url: str) -> str | None:
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        value = node.get(attr)
        if not value:
            continue
        normalized = _normalize_asset_url(value, base_url)
        if normalized:
            return normalized
    return None


def _detect_source_site(source_url: str) -> str:
    normalized_url = _clean_text(source_url)
    parsed = urlparse(normalized_url if "://" in normalized_url else f"https://{normalized_url}")
    host = (parsed.netloc or parsed.path or "").lower()

    if "viyar" in host:
        return "viyar"
    if "mt.ua" in host:
        return "mt"
    if "kronas" in host:
        return "kronas"
    return "generic"


def _extract_article_from_text(value: str | None) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    match = re.search(r"\b\d{4,}\b", text)
    return match.group(0) if match else None


def _is_disallowed_kronas_image_url(value: str | None) -> bool:
    url = _clean_text(value).lower()

    if not url:
        return True

    if url.startswith(("data:", "blob:")):
        return True

    blocked_markers = (
        "ajax-loader.gif",
        "lazy",
        "loader.gif",
        "placeholder",
        "favicon",
        "logo",
        "sprite",
    )

    if any(marker in url for marker in blocked_markers):
        return True

    if url.endswith(".svg") or url.endswith(".gif"):
        return True

    return False


def _extract_kronas_main_image_url(soup: BeautifulSoup, final_url: str) -> str | None:
    for selector in [".js-productImage", ".productImage"]:
        container = soup.select_one(selector)
        if not container:
            continue

        candidates: list[str | None] = [
            container.get("data-large"),
            container.get("data-src"),
        ]

        image_node = (
            container.select_one("img[itemprop='image']")
            or container.select_one("img")
        )

        if image_node:
            candidates.extend(
                [
                    image_node.get("data-src"),
                    image_node.get("src"),
                ]
            )

        for candidate in candidates:
            normalized = _normalize_asset_url(candidate, final_url)
            if normalized and not _is_disallowed_kronas_image_url(normalized):
                return normalized

    return None


def _extract_first_node_text(soup: BeautifulSoup, selectors: list[str], attr: str) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        value = _clean_text(node.get(attr) or node.get_text(" ", strip=True))
        if value:
            return value
    return ""


def _normalize_kronas_currency(value: str | None) -> str | None:
    text = _clean_text(value)
    if not text:
        return None

    lowered = text.lower()
    if lowered in {"грн", "гривня", "гривні", "гривень", "uah", "₴"}:
        return "UAH"

    upper = text.upper()
    if upper in {"UAH", "USD", "EUR"}:
        return upper

    return None


def _extract_kronas_price(soup: BeautifulSoup) -> tuple[float | None, str | None]:
    price_node = soup.select_one("[itemprop='price']")
    if price_node:
        raw_price = _clean_text(
            price_node.get("content")
            or price_node.get("data-price")
            or price_node.get_text(" ", strip=True)
        )
        price = _extract_price(raw_price)
        if price is not None:
            return price, raw_price or None

    price_node = soup.select_one("#price[data-price]")
    if price_node:
        raw_price = _clean_text(price_node.get("data-price"))
        price = _extract_price(raw_price)
        if price is not None:
            return price, raw_price or None

    raw_price = _first_text(
        soup,
        [
            ".productPriceBlock__price",
            "[class*='price']",
            ".product-price",
            ".price",
            ".cost",
        ],
    )
    return _extract_price(raw_price), raw_price or None


def _extract_kronas_currency(soup: BeautifulSoup, fallback_text: str | None = None) -> str | None:
    currency = _normalize_kronas_currency(
        _extract_first_node_text(
            soup,
            [
                "meta[itemprop='priceCurrency']",
                "[itemprop='priceCurrency']",
                ".productPriceBlock__currency",
                ".priceCurrency",
            ],
            "content",
        )
    )
    if currency:
        return currency

    if fallback_text and "грн" in _clean_text(fallback_text).lower():
        return "UAH"

    return None


def _extract_kronas_availability(soup: BeautifulSoup) -> str | None:
    raw_value = _extract_first_node_text(
        soup,
        [
            ".productLabel",
            ".productPriceBlock__label",
            ".product-price__label",
        ],
        "content",
    )

    if not raw_value:
        return None

    lowered = raw_value.lower()
    availability_map = {
        "є в наявності": "В наявності",
        "есть в наличии": "В наявності",
        "в наличии": "В наявності",
        "в наявності": "В наявності",
        "немає в наявності": "Немає в наявності",
        "нет в наличии": "Немає в наявності",
        "під замовлення": "Під замовлення",
        "под заказ": "Під замовлення",
    }

    for source_text, target_text in availability_map.items():
        if source_text in lowered:
            return target_text

    return None


def _extract_kronas_characteristics(soup: BeautifulSoup) -> dict[str, str]:
    characteristics: dict[str, str] = {}
    seen_pairs: set[tuple[str, str]] = set()

    for container in soup.select(".productAttr"):
        for key_node in container.select(".productAttr__key"):
            key = _clean_text(key_node.get_text(" ", strip=True)).rstrip(":").strip()
            if not key:
                continue

            value_node = key_node.find_next(class_="productAttr__value")
            if not value_node:
                continue

            value = _clean_text(value_node.get_text(" ", strip=True))
            if not value:
                continue

            normalized_pair = (key, value)
            if normalized_pair in seen_pairs:
                continue

            seen_pairs.add(normalized_pair)
            if key not in characteristics:
                characteristics[key] = value

    return characteristics


def _extract_kronas_description(soup: BeautifulSoup, product_name: str | None) -> str | None:
    description = (
        _first_meta_content(
            soup,
            [
                "meta[itemprop='description']",
                "meta[name='description']",
                "meta[property='og:description']",
            ],
        )
        or _first_text(
            soup,
            [
                ".productTabs__content.is-active .view-text > p:first-of-type",
            ],
        )
    )

    description = _clean_text(description)
    if not description:
        return None

    if product_name and description == _clean_product_name(product_name):
        return None

    if _looks_like_promotional_copy(description):
        return None

    return description or None


def _is_disallowed_kronas_gallery_url(value: str | None) -> bool:
    url = _clean_text(value).lower()
    if not url:
        return True

    if url.startswith(("data:", "blob:")):
        return True

    if "/media/images/catalog/big/" in url:
        return True

    blocked_markers = (
        "ajax-loader.gif",
        "banner",
        "icon",
        "lazy",
        "loader.gif",
        "logo",
        "placeholder",
        "recommend",
        "related",
        "review",
        "sprite",
    )

    return any(marker in url for marker in blocked_markers)


def _extract_kronas_gallery_urls(soup: BeautifulSoup, final_url: str) -> list[str]:
    collected: list[str] = []
    slider = soup.select_one(".productImageBlock__slider")
    if not slider:
        return collected

    for node in slider.select(".js-productImage, img, source"):
        candidates = [
            node.get("data-src"),
            node.get("src"),
            node.get("srcset"),
        ]

        image_node = node.select_one("img[data-src]") or node.select_one("img")
        if image_node:
            candidates.extend(
                [
                    image_node.get("data-src"),
                    image_node.get("src"),
                ]
            )

        for candidate in candidates:
            normalized = _normalize_asset_url(candidate, final_url)
            if normalized and not _is_disallowed_kronas_gallery_url(normalized):
                collected.append(normalized)
                break

    return _dedupe_preserve_order(collected)


def _extract_kronas_article(soup: BeautifulSoup, final_url: str) -> str | None:
    selectors = [
        "#artikul[itemprop='sku']",
        "input[name='artikulu']",
        "[itemprop='mpn']",
        "#artikul",
        ".product-code",
        ".sku",
        "[class*='articul']",
        "[class*='article']",
    ]

    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue

        if node.name == "input":
            candidate = _clean_text(node.get("value"))
        else:
            candidate = _clean_text(node.get("content") or node.get_text(" ", strip=True))

        article = _extract_article_from_text(candidate)
        if article:
            return article

    return _extract_article_from_text(final_url)


async def _fetch_html_with_browser(
    source_url: str,
    *,
    storage_state: dict | str | None = None,
    wait_ms: int = 2000,
) -> tuple[str, str]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            storage_state=storage_state,
            locale="uk-UA",
            user_agent=DEFAULT_HEADERS["User-Agent"],
            viewport={"width": 1366, "height": 900},
        )
        page = await context.new_page()

        try:
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            await page.goto(source_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(wait_ms)
            final_url = page.url
            html = await page.content()
        finally:
            await context.close()
            await browser.close()

    return final_url, html


async def _fetch_html(
    url: str,
) -> tuple[int, str, str]:
    material_catalog_service = _material_catalog_service()

    try:
        html, final_url = await asyncio.to_thread(
            material_catalog_service._fetch_html,
            url,
            None,
            None,
            return_final_url=True,
        )
        return 200, final_url, html
    except HTTPError as error:
        payload = error.read() if hasattr(error, "read") else b""
        charset = None

        try:
            charset = error.headers.get_content_charset() if error.headers else None
        except Exception:
            charset = None

        html = ""
        for encoding in (charset, "utf-8", "utf-8-sig", "windows-1251", "cp1251"):
            if not encoding:
                continue
            try:
                html = payload.decode(encoding, errors="replace")
                break
            except Exception:
                continue

        return int(getattr(error, "code", 0) or 0), getattr(error, "url", url) or url, html


def _parse_viyar_html(html: str, final_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    name = (
        _first_text(
            soup,
            [
                "h1.text.text-weight-dark",
                ".vr-card-info h1",
                ".card-info-head_title h1",
                "h1",
            ],
        )
        or _first_meta_content(
            soup,
            [
                "meta[property='og:title']",
                "meta[name='twitter:title']",
            ],
        )
        or _first_text(soup, ["title"])
    )

    article = _extract_article_from_text(
        _first_text(
            soup,
            [
                ".text-code.text-weight-bolder",
                "span.text-code.text-weight-bolder",
                ".text-code",
            ],
        )
    )

    price_text = _first_text(
        soup,
        [
            'span[id*="_price"]',
            ".price-actual",
            ".card-info-prices__price-actual",
            ".price-current",
        ],
    )
    unit = _first_text(
        soup,
        [
            ".card-info-prices__price-row .text-unit",
            ".text-unit",
        ],
    )
    image_url = (
        _first_attr(
            soup,
            [
                "meta[property='og:image']",
                "meta[name='twitter:image']",
            ],
            "content",
            final_url,
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
            "src",
            final_url,
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
            "data-src",
            final_url,
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
            final_url,
        )
    )
    name = _clean_product_name(name)
    jsonld = _extract_product_jsonld(soup, fallback_name=name, fallback_article=article)
    characteristics = _extract_viyar_characteristics(soup)

    article = article or jsonld.get("sku")
    name = name or jsonld.get("name")
    image_url = image_url or jsonld.get("image")
    jsonld_image_urls = jsonld.get("image_urls")
    image_urls = _normalize_fitting_image_urls(
        {
            "image_url": image_url,
            "image_urls": (
                [
                    *(
                        [image_url]
                        if image_url
                        else []
                    ),
                    *(
                        jsonld_image_urls
                        if isinstance(jsonld_image_urls, list)
                        else []
                    ),
                ]
                if image_url or isinstance(jsonld_image_urls, list)
                else []
            ),
        }
    )["image_urls"]

    if not image_url and image_urls:
        image_url = image_urls[0]

    price = _extract_price(price_text)
    price_raw = price_text or None
    if price is None and jsonld.get("price") is not None:
        price = jsonld.get("price")
        price_raw = str(jsonld.get("price"))

    description = _clean_text(jsonld.get("description")) or None
    normalized_name = _clean_product_name(name)
    if description and normalized_name and description == normalized_name:
        description = None

    brand = jsonld.get("brand") or characteristics.get("Виробник")

    return {
        "success": True,
        "source_site": "viyar",
        "final_url": final_url,
        "name": name or None,
        "description": description,
        "article": article,
        "price": price,
        "price_raw": price_raw,
        "unit": unit or None,
        "image_url": image_url or None,
        "image_urls": image_urls,
        "brand": brand,
        "currency": jsonld.get("currency"),
        "availability": jsonld.get("availability"),
        "characteristics": characteristics,
    }


def _parse_kronas_html(html: str, final_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    name = (
        _first_text(
            soup,
            [
                "h1[itemprop='name']",
                "h1",
                ".product-title",
                ".page-title",
            ],
        )
        or _first_meta_content(
            soup,
            [
                "meta[property='og:title']",
                "meta[name='twitter:title']",
            ],
        )
        or _first_text(soup, ["title"])
    )

    name = _clean_product_name(name)
    article = _extract_kronas_article(soup, final_url)
    price, price_raw = _extract_kronas_price(soup)
    gallery_urls = _extract_kronas_gallery_urls(soup, final_url)
    image_url = gallery_urls[0] if gallery_urls else None
    if not image_url and article:
        image_url = f"https://kronas.com.ua/Media/images/catalog/original/{article}.jpg"
        gallery_urls = [image_url]
    elif image_url and not gallery_urls:
        gallery_urls = [image_url]

    description = _extract_kronas_description(soup, name)
    characteristics = _extract_kronas_characteristics(soup)
    brand = characteristics.get("Производитель") or characteristics.get("Виробник")
    unit = characteristics.get("Единица измерения") or characteristics.get("Одиниця виміру")
    availability = _extract_kronas_availability(soup)
    currency = _extract_kronas_currency(soup, price_raw)
    if not currency and price_raw and "грн" in price_raw.lower():
        currency = "UAH"

    return {
        "success": True,
        "source_site": "kronas",
        "final_url": final_url,
        "name": name or None,
        "description": description,
        "article": article,
        "price": price,
        "price_raw": price_raw,
        "unit": unit or None,
        "image_url": image_url or None,
        "image_urls": gallery_urls,
        "brand": brand or None,
        "currency": currency,
        "availability": availability,
        "characteristics": characteristics,
    }


def _parse_generic_html(html: str, final_url: str, source_site: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    name = (
        _first_text(
            soup,
            [
                "h1",
                ".product-title",
                ".product-name",
                ".page-title",
            ],
        )
        or _first_meta_content(
            soup,
            [
                "meta[property='og:title']",
                "meta[name='twitter:title']",
            ],
        )
        or _first_text(soup, ["title"])
    )

    image_url = (
        _first_attr(
            soup,
            [
                "meta[property='og:image']",
                "meta[name='twitter:image']",
                "[itemprop='image']",
                ".product-gallery img",
                ".product-image img",
                "img",
            ],
            "content",
            final_url,
        )
        or _first_attr(
            soup,
            [
                "[itemprop='image']",
                ".product-gallery img",
                ".product-image img",
                "img",
            ],
            "src",
            final_url,
        )
    )

    price_text = _first_text(
        soup,
        [
            "[class*='price']",
            ".product-price",
            ".price",
            ".cost",
        ],
    )
    name = _clean_product_name(name)
    description = _extract_description(soup, name)

    return {
        "success": True,
        "source_site": source_site,
        "final_url": final_url,
        "name": name or None,
        "description": description,
        "article": None,
        "price": _extract_price(price_text),
        "price_raw": price_text or None,
        "unit": None,
        "image_url": image_url or None,
    }


def _attach_page_diagnostics(
    result: dict,
    *,
    requested_url: str,
    final_url: str,
    http_status: int | None,
    transport: str,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict:
    enriched = _normalize_fitting_image_urls(result)
    normalized_requested_url = _clean_text(requested_url)
    normalized_final_url = _clean_text(final_url) or normalized_requested_url

    enriched["requested_url"] = normalized_requested_url
    enriched["final_url"] = normalized_final_url
    enriched["http_status"] = http_status
    enriched["redirect"] = normalized_final_url != normalized_requested_url
    enriched["transport"] = transport
    enriched["error_login_required"] = "error=login_required" in normalized_final_url.lower()
    enriched["warnings"] = warnings or []
    enriched["errors"] = errors or []
    return enriched


async def _fetch_html(url: str) -> tuple[int, str, str]:
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout, headers=DEFAULT_HEADERS) as session:
        async with session.get(url, allow_redirects=True) as response:
            html = await response.text()
            return response.status, str(response.url), html


async def _parse_mt_source(source_url: str) -> dict:
    if not MT_AUTH_PATH.exists():
        return {
            "success": False,
            "error": "MT authorization state was not found",
            "source_site": "mt",
        }

    final_url, html = await _fetch_html_with_browser(
        source_url,
        storage_state=json.loads(MT_AUTH_PATH.read_text(encoding="utf-8")),
        wait_ms=2000,
    )

    soup = BeautifulSoup(html, "html.parser")

    name = (
        _first_text(
            soup,
            [
                "h1",
                ".product-title",
                ".product-name",
                ".page-title",
            ],
        )
        or _first_meta_content(
            soup,
            [
                "meta[property='og:title']",
                "meta[name='twitter:title']",
            ],
        )
        or _first_text(soup, ["title"])
    )
    name = _clean_product_name(name)

    article = _extract_article_from_text(final_url)

    if not article:
        page_text = soup.get_text(" ", strip=True)
        article_match = re.search(r"\bКод[:\s]*([0-9]{4,})\b", page_text, re.IGNORECASE)
        if article_match:
            article = article_match.group(1)

    price_text = _first_text(
        soup,
        [
            ".product-page-price",
            ".product-price",
            ".price-current",
            ".price",
            "[data-price]",
        ],
    )

    if not price_text:
        node = soup.select_one("[data-price]")
        if node:
            price_text = _clean_text(node.get("data-price"))

    if not price_text:
        for script in soup.find_all("script"):
            script_text = script.string or script.get_text(" ", strip=True) or ""
            if "dataLayer.push" not in script_text:
                continue

            article_hint = article or _extract_article_from_text(final_url)
            target_id_match = re.search(r"item_id:\s*'?(?P<id>\d{4,})'?", script_text)
            price_match = re.search(r"price:\s*(?P<price>\d+(?:\.\d+)?)", script_text)

            if article_hint and target_id_match and target_id_match.group("id") != article_hint:
                continue

            if price_match:
                price_text = price_match.group("price")
                if target_id_match and not article:
                    article = target_id_match.group("id")
                break

    image_url = (
        _first_attr(
            soup,
            [
                "meta[property='og:image']",
                "meta[name='twitter:image']",
            ],
            "content",
            final_url,
        )
        or _first_attr(
            soup,
            [
                ".product-gallery img",
                ".product-image img",
                ".main-image img",
                "img[src]",
            ],
            "src",
            final_url,
        )
        or _first_attr(
            soup,
            [
                ".product-gallery img",
                ".product-image img",
                ".main-image img",
                "img[data-src]",
            ],
            "data-src",
            final_url,
        )
    )
    description = _extract_description(soup, name)

    return {
        "success": True,
        "source_site": "mt",
        "final_url": final_url,
        "name": name or None,
        "description": description,
        "article": article,
        "price": _extract_price(price_text),
        "price_raw": price_text or None,
        "unit": None,
        "image_url": image_url or None,
    }


async def parse_fitting_source_metadata(source_url: str) -> dict:
    normalized_url = _clean_text(source_url)

    if not normalized_url:
        return {
            "success": False,
            "error": "Source URL is empty",
        }

    source_site = _detect_source_site(normalized_url)

    try:
        if source_site == "mt":
            result = await _parse_mt_source(normalized_url)
            return _attach_page_diagnostics(
                result,
                requested_url=normalized_url,
                final_url=result.get("final_url") or normalized_url,
                http_status=200 if result.get("success") else 0,
                transport="Playwright",
            )

        fetch_error: Exception | None = None
        transport = "HTTP"
        try:
            status, final_url, html = await _fetch_html(normalized_url)
        except Exception as error:
            fetch_error = error
            status, final_url, html = 0, normalized_url, ""

        if status != 200:
            browser_error: Exception | None = None
            try:
                final_url, html = await _fetch_html_with_browser(
                    normalized_url,
                    wait_ms=5000 if source_site == "viyar" else 2000,
                )
                status = 200
                fetch_error = None
                transport = "Playwright"
            except Exception as error:
                browser_error = error
                transport = "Playwright"

            if status != 200:
                raw_error = browser_error or fetch_error
                error_message = _format_browser_runtime_error(raw_error) if raw_error else f"Unable to load source page: HTTP {status}"
                return _attach_page_diagnostics(
                    {
                        "success": False,
                        "error": error_message,
                        "source_site": source_site,
                    },
                    requested_url=normalized_url,
                    final_url=final_url,
                    http_status=status,
                    transport=transport,
                    errors=[error_message],
                )

        if "error=login_required" in (final_url or "").lower():
            return _attach_page_diagnostics(
                {
                    "success": False,
                    "error": "login_required",
                    "source_site": source_site,
                },
                requested_url=normalized_url,
                final_url=final_url,
                http_status=status,
                transport=transport,
                errors=["login_required"],
            )

        if source_site == "viyar":
            result = _parse_viyar_html(html, final_url)
            return _attach_page_diagnostics(
                result,
                requested_url=normalized_url,
                final_url=final_url,
                http_status=status,
                transport=transport,
            )
        elif source_site == "kronas":
            result = _parse_kronas_html(html, final_url)
        else:
            result = _parse_generic_html(html, final_url, source_site)

        return _attach_page_diagnostics(
            result,
            requested_url=normalized_url,
            final_url=final_url,
            http_status=status,
            transport=transport,
        )
    except asyncio.TimeoutError:
        return _attach_page_diagnostics(
            {
                "success": False,
                "error": "Source page timed out",
                "source_site": source_site,
            },
            requested_url=normalized_url,
            final_url=normalized_url,
            http_status=0,
            transport="HTTP",
            errors=["Source page timed out"],
        )
    except Exception as error:
        return _attach_page_diagnostics(
            {
                "success": False,
                "error": _format_browser_runtime_error(error),
                "source_site": source_site,
            },
            requested_url=normalized_url,
            final_url=normalized_url,
            http_status=0,
            transport="HTTP",
            errors=[_format_browser_runtime_error(error)],
        )
