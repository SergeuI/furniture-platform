import logging
import asyncio
import json
import re
from urllib.parse import unquote, urlencode, urljoin, urlsplit

from playwright.async_api import async_playwright
import aiosqlite
from bs4 import BeautifulSoup
from services.legacy_db_config import DEFAULT_DB_PATH
from services.material_manufacturer_rules import MISSING_MANUFACTURER_NAME


# =====================================================
# LOGGER
# =====================================================

logging.basicConfig(
    filename="parser.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# =====================================================
# DATABASE
# =====================================================

DB_NAME = DEFAULT_DB_PATH


# =====================================================
# CITY MAP
# =====================================================

CITY_MAP = {
    "🏙 Київ": "kyiv",
    "🏰 Львів": "lviv",
    "🌉 Дніпро": "dnipro",
    "🌊 Одеса": "odessa",
    "🏢 Харків": "kharkiv"
}


# =====================================================
# CITY COOKIES
# =====================================================

CITY_COOKIES = {
    "kyiv": "KYIV",
    "lviv": "LVIV",
    "dnipro": "DNIPRO",
    "odessa": "ODESA",
    "kharkiv": "KHARKIV",
}


# =====================================================
# MATERIALS + FITTINGS
# =====================================================

CATEGORIES = {

    # =================================================
    # ДСП
    # =================================================

    "dsp": [
        "215557",
        "43102",
        "45791",
        "77792"
    ],

    # =================================================
    # КРАЙКА 0.4
    # =================================================

    "edge_04": [
        "176199",
        "128037",
        "120821",
        "45696"
    ],

    # =================================================
    # КРАЙКА 0.8
    # =================================================

    "edge_08": [
        "72704",
        "53164",
        "120822",
        "87168"
    ],

    # =================================================
    # РУЧКИ
    # =================================================

    "handles": [
        "117213",
        "213752",
        "11728",
        "69690"
    ],

    # =================================================
    # НАПРЯМНІ BASIC
    # =================================================

    "slides_basic": [
        "36949",
        "96069",
        "96173",
        "96070",
        "96071",
        "96072",
        "96073",
        "96074"
    ],

    # =================================================
    # НАПРЯМНІ TIP-ON
    # =================================================

    "slides_tipon": [
        "132439",
        "33549",
        "33550",
        "33551",
        "33552",
        "33553"
    ],

    # =================================================
    # НАПРЯМНІ SOFTCLOSE
    # =================================================

    "slides_softclose": [
        "117547",
        "25391",
        "25392",
        "25393",
        "25394",
        "25395",
        "25396",
        "162052"
    ],
}


# =====================================================
# SERVICES
# =====================================================

SERVICES = {

    # ==========================================
    # ПОРІЗКА
    # ==========================================

    "cutting": [
        "19026"
    ],

    # ==========================================
    # КРАЙКУВАННЯ
    # ==========================================

    "edgebanding": [
        "19007"
    ],

    # ==========================================
    # СВЕРДЛІННЯ
    # ==========================================

    "drilling": [
        "00011"
    ]
}


# =====================================================
# UPDATE DB
# =====================================================

async def update_db():

    async with aiosqlite.connect(DB_NAME) as db:

        try:
            await db.execute(
                "ALTER TABLE materials ADD COLUMN category TEXT;"
            )
        except:
            pass

        await db.commit()


# =====================================================
# EXTRACT HTML
# =====================================================


def extract(html):

    soup = BeautifulSoup(html, "html.parser")

    # ==========================================
    # NAME
    # ==========================================

    name = soup.select_one("h1")

    name = (
        name.text.strip()
        if name
        else "Не знайдено"
    )

    # ==========================================
    # PRICE
    # ==========================================

    price = soup.select_one('span[id*="_price"]')

    price = (
        price.text.strip()
        if price
        else None
    )

    # ==========================================
    # IMAGE
    # ==========================================

    image = None

    source = soup.select_one("picture source")

    if source and source.get("srcset"):

        image = source.get("srcset")
        image = image.split(",")[0].split(" ")[0]

    if not image:

        img = soup.select_one("picture img")

        if img:
            image = (
                img.get("src")
                or img.get("data-src")
            )

    if image:

        if "?" in image:
            image = image.split("?")[0]

        if not image.startswith("http"):
            image = "https://viyar.ua" + image

    return name, price, image


# =====================================================
# EXTRACT RECOMMENDED EDGES
# =====================================================

VIYAR_EDGE_SECTION_SELECTOR = (
    '[data-section_name="Крайка"]'
    '[data-list_name="Крайки та пластики"]'
)

VIYAR_RECOMMENDED_EDGE_HYDRATION_TIMEOUT_MS = 5000
VIYAR_RECOMMENDED_EDGE_HYDRATION_POLL_MS = 250


def _find_viyar_edge_section(soup):

    # The current VIYAR page hydrates this section by id after the initial
    # document has loaded. Keep the legacy data attributes below for older
    # pages and fixtures.
    hydrated_section = soup.select_one("#rekomenduemayakromka")
    if hydrated_section:
        return hydrated_section

    section = soup.select_one(VIYAR_EDGE_SECTION_SELECTOR)
    if section:
        return section

    for candidate in soup.select("[data-section_name]"):

        section_name = _normalize_viyar_edge_text(candidate.get("data-section_name"))
        if not section_name or "крайк" not in section_name.casefold():
            continue

        list_name = _normalize_viyar_edge_text(candidate.get("data-list_name"))
        if list_name and "пластик" not in list_name.casefold():
            continue

        if candidate.select_one("a.vr-card__link[href]"):
            return candidate

    return None


def _extract_viyar_edge_article(value):

    if not value:
        return None

    text = _normalize_viyar_edge_text(value)

    if not text:
        return None

    match = re.match(r"^(\d+)\b", text)

    if match:
        return match.group(1)

    return None


def _extract_viyar_edge_product_code(value):

    if not value:
        return None

    text = _normalize_viyar_edge_text(value)

    if not text:
        return None

    match = re.match(r"^(\d+[A-Za-z0-9]*)\b", text)

    if not match:
        match = re.search(
            r"(?<![A-Za-z0-9])([A-Za-z]{1,8}\d+[A-Za-z0-9]*(?:/[A-Za-z0-9]+)?)\b",
            text,
        )

    if match:
        return match.group(1)

    return None


def _extract_viyar_edge_brand_candidate(value):

    if not value:
        return None

    text = _normalize_viyar_edge_text(value)

    if not text:
        return None

    tokens = re.findall(r"[^\s/]+", text)
    blocked_tokens = {
        "мм",
        "мм.",
        "м.п.",
        "м.п",
        "шт",
        "шт.",
        "см",
        "м",
        "m.p.",
        "m.p",
    }

    for token in reversed(tokens):
        candidate = token.strip("()[]{}.,;:!?")
        if not candidate:
            continue
        if candidate.lower() in blocked_tokens:
            continue
        if re.search(r"\d\s*[xх×]\s*\d", candidate, re.IGNORECASE):
            continue
        if any(char.isdigit() for char in candidate):
            continue
        if not any(ch.isalpha() for ch in candidate):
            continue

        if candidate.isupper():
            return candidate.title()

        if candidate[0].isalpha():
            return candidate[0].upper() + candidate[1:]

        return candidate

    return None


def _extract_viyar_edge_brand(soup, title=None, source_url=None):

    for selector in (
        "[data-brand]",
        "[itemprop='brand']",
        "meta[property='product:brand']",
        "meta[name='brand']",
        "meta[itemprop='brand']",
    ):
        node = soup.select_one(selector)
        if not node:
            continue
        value = (
            node.get("data-brand")
            or node.get("content")
            or node.get_text(" ", strip=True)
        )
        brand = _extract_viyar_edge_brand_candidate(value)
        if brand:
            return brand

    for candidate in (
        title,
        (_normalize_viyar_edge_url(source_url) or "").rstrip("/").rsplit("/", 1)[-1] if source_url else None,
    ):
        brand = _extract_viyar_edge_brand_candidate(candidate)
        if brand and re.search(r"[A-Za-z]", brand):
            return brand

    return None


def _viyar_manufacturer_source_evidence(soup, characteristics, product):
    structured_brand = (product.get("brand") or {}).get("name") if isinstance(product, dict) else None
    if _normalize_viyar_edge_text(structured_brand):
        return {"field_present": True, "value_present": True, "source": "structured_brand"}

    for key, value in (characteristics or {}).items():
        if str(key or "").strip().casefold() in {"виробник", "manufacturer", "brand"}:
            return {
                "field_present": True,
                "value_present": bool(_normalize_viyar_edge_text(value)),
                "source": "characteristics",
            }

    for selector in (
        "[data-brand]",
        "[itemprop='brand']",
        "meta[property='product:brand']",
        "meta[name='brand']",
        "meta[itemprop='brand']",
    ):
        node = soup.select_one(selector)
        if node is not None:
            value = node.get("data-brand") or node.get("content") or node.get_text(" ", strip=True)
            return {
                "field_present": True,
                "value_present": bool(_normalize_viyar_edge_text(value)),
                "source": selector,
            }

    return {"field_present": False, "value_present": False, "source": None}


def _extract_viyar_edge_material_type(characteristics, title=None, source_url=None):

    candidates = [
        characteristics.get("Тип товару") if characteristics else None,
        characteristics.get("Тип") if characteristics else None,
        characteristics.get("Тип/матеріал") if characteristics else None,
        characteristics.get("Матеріал") if characteristics else None,
        title,
        source_url,
    ]

    for candidate in candidates:
        text = _normalize_viyar_edge_text(candidate)
        if not text:
            continue
        if re.search(r"\bABS\b", text, re.IGNORECASE):
            return "ABS"
        if re.search(r"\bPVC\b|\bПВХ\b", text, re.IGNORECASE):
            return "PVC"
        if re.search(r"\bMDF\b", text, re.IGNORECASE):
            return "MDF"
        if re.search(r"\bHDF\b", text, re.IGNORECASE):
            return "HDF"

    return None


def _normalize_viyar_edge_technology(characteristics):
    value = _normalize_viyar_edge_text(
        (characteristics or {}).get("Тип крайки")
        or (characteristics or {}).get("Тип кромки")
    )
    if not value:
        return None
    normalized = value.casefold()
    if "лазер" in normalized:
        return "laser_abs_pro"
    if normalized in {"abs", "standard abs", "стандартна abs", "стандартная abs"}:
        return "standard_abs"
    return None


def _extract_viyar_edge_image_url(soup):

    for selector in (
        ".productImageBlock__slider [data-large]",
        ".productImageBlock__slider [data-src]",
        "meta[property='og:image']",
        "meta[name='twitter:image']",
        ".productImageBlock__slider img",
        ".productImageBlock [data-large]",
        ".productImageBlock [data-src]",
        ".productImageBlock img",
        "picture source",
        "picture img",
        "[itemprop='image']",
        "img.main-image",
    ):
        node = soup.select_one(selector)
        if not node:
            continue

        candidate = (
            node.get("data-large")
            or node.get("data-src")
            or node.get("src")
            or node.get("content")
            or node.get("srcset")
        )

        if candidate and "," in candidate:
            candidate = candidate.split(",")[0].split(" ")[0]

        image = _normalize_viyar_edge_url(candidate)
        if image:
            return image

    return None


def _extract_viyar_json_ld(soup):

    products = []

    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                candidates.extend(item for item in graph if isinstance(item, dict))
            item_type = candidate.get("@type")
            if item_type == "Product" or (isinstance(item_type, list) and "Product" in item_type):
                products.append(candidate)

    return products


def _extract_viyar_labeled_characteristics(soup):

    characteristics = {}

    def add(key, value):
        normalized_key = _normalize_viyar_edge_text(key)
        normalized_value = _normalize_viyar_edge_text(value)
        if normalized_key and normalized_value:
            characteristics[normalized_key.rstrip(":")] = normalized_value

    for row in soup.select("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) >= 2:
            add(cells[0].get_text(" ", strip=True), cells[1].get_text(" ", strip=True))

    for label in (
        "Товщина, мм",
        "Ширина, мм",
        "Виробник",
        "Країна-виробник",
        "Країна виробник",
        "Тип основи",
        "Тип крайки",
        "Декор (лицьова)",
        "Декор",
        "Колір",
        "Вага, кг",
        "Крайкування зі сходинкою",
    ):
        for node in soup.find_all(attrs={"title": label}):
            container = node
            value_node = container.find("button") or container.find("p")
            text = _normalize_viyar_edge_text(
                value_node.get_text(" ", strip=True)
                if value_node
                else container.get_text(" ", strip=True)
            )
            if text:
                value = text.replace(label, "", 1).strip()
                if value:
                    add(label, value)

    return characteristics


def _extract_viyar_json_ld_image_urls(products):

    urls = []
    for product in products:
        images = product.get("image")
        if isinstance(images, str):
            images = [images]
        for image in images or []:
            normalized = _normalize_viyar_edge_url(image)
            if normalized and normalized not in urls:
                urls.append(normalized)
    return urls


def _dedupe_viyar_image_urls(urls):

    result = []
    seen_families = set()
    for value in urls:
        normalized = _normalize_viyar_edge_url(value)
        if not normalized:
            continue
        if _is_viyar_rejected_image(normalized):
            continue
        family = _viyar_image_family(normalized)
        family = re.sub(r"(?:_main|_large|_small|_thumb)(?=\.[A-Za-z]+$)", "", family)
        if family in seen_families:
            continue
        seen_families.add(family)
        result.append(normalized)
    return result


def _is_viyar_rejected_image(value):

    normalized = _normalize_viyar_edge_url(value)
    if not normalized:
        return True

    lowered = normalized.casefold()
    if re.search(r"placeholder|photo[-_ ]?not[-_ ]?found|no[-_ ]?image|default[-_ ]?image", lowered):
        return True
    if lowered.startswith("data:image/svg"):
        return True
    if re.search(r"(?:bonus|gift|promo|promotion|payment|delivery|logo|privat)", lowered):
        return True

    return False


def _viyar_image_family(value):

    normalized = _normalize_viyar_edge_url(value) or ""
    # CDN resize wrappers point at the same underlying VIYAR asset.
    wrapped = re.search(r"/https?://.+$", normalized)
    if wrapped:
        normalized = wrapped.group(0)[1:]

    filename = normalized.rsplit("/", 1)[-1].split("?", 1)[0].casefold()
    article_match = re.search(r"(?:^|[^0-9])(ph\d+)(?:[_\-.]|$)", filename)
    if article_match:
        return article_match.group(1)

    return re.sub(r"(?:_[A-Za-z0-9]{4,})?(?=\.[A-Za-z]+$)", "", filename)


def _select_viyar_product_image_urls(urls, supplier_article=None, trusted_urls=None):

    candidates = []
    seen = set()
    article = str(supplier_article or "").casefold()
    trusted = {
        _normalize_viyar_edge_url(value)
        for value in (trusted_urls or [])
        if _normalize_viyar_edge_url(value)
    }

    for value in urls:
        normalized = _normalize_viyar_edge_url(value)
        if not normalized or _is_viyar_rejected_image(normalized):
            continue
        family = _viyar_image_family(normalized)
        if family in seen:
            continue
        seen.add(family)

        filename = normalized.rsplit("/", 1)[-1].casefold()
        score = 0
        if normalized in trusted:
            score += 200
        if article and re.search(rf"(?:^|\D)ph{re.escape(article)}(?:\D|$)", filename):
            score += 100
        if score == 0:
            continue
        candidates.append((score, len(candidates), normalized))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in candidates]


def _extract_viyar_dom_image_urls(soup, preferred_families=None):

    urls = []
    for node in soup.select("img, source, [itemprop='image']"):
        candidate = (
            node.get("data-large")
            or node.get("data-src")
            or node.get("src")
            or node.get("content")
            or node.get("srcset")
        )
        if not candidate:
            continue
        if node.get("src") or node.get("data-src") or node.get("data-large") or node.get("content"):
            candidates = [str(candidate).strip()]
        else:
            candidates = re.findall(r"(?:https?:)?//.*?(?=\s+\d+w(?:\s*,|$)|$)", str(candidate))
        if preferred_families:
            candidates = [
                value
                for value in candidates
                if any(family in value.lower() for family in preferred_families)
            ]
        urls.extend(candidates)
    return urls


def _extract_viyar_edge_dimensions_from_text(value):

    if not value:
        return None, None

    text = _normalize_viyar_edge_text(value)

    if not text:
        return None, None

    match = re.search(
        r"(?P<width>\d+(?:[.,]\d+)?)\s*[xх×]\s*(?P<thickness>\d+(?:[.,]\d+)?)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return None, None

    width = float(match.group("width").replace(",", "."))
    thickness = float(match.group("thickness").replace(",", "."))

    return width, thickness


def extract_recommended_edge_cards(html):

    soup = BeautifulSoup(html, "html.parser")
    section = _find_viyar_edge_section(soup)

    if not section:
        return []

    cards = []
    seen_keys = set()

    links = section.select("a.vr-card__link[href]")
    if not links and section.get("id") == "rekomenduemayakromka":
        links = [
            link
            for link in section.select("a[href]")
            if "/catalog/" in (link.get("href") or "")
        ]

    for link in links:

        href = (link.get("href") or "").strip()

        if not href:
            continue

        source_url = urljoin("https://viyar.ua", href)
        source_url = source_url.split("?")[0]
        source_url = source_url.split("#")[0]

        card_container = link
        supplier_article = None
        for _ in range(7):
            numeric_spans = card_container.find_all(
                lambda node: node.name == "span"
                and re.fullmatch(r"\d{4,}", _normalize_viyar_edge_text(node.get_text(" ", strip=True)) or "")
            )
            if numeric_spans:
                supplier_article = _normalize_viyar_edge_text(numeric_spans[0].get_text(" ", strip=True))
                break
            parent = card_container.parent
            if not parent or parent is section:
                break
            card_container = parent

        candidate_links = card_container.select("a[href]") if card_container is not link else [link]
        title_candidates = []
        for candidate_link in candidate_links:
            candidate_title = candidate_link.get("title")
            candidate_name = candidate_link.get_text(" ", strip=True)
            candidate_image = candidate_link.select_one("img")
            candidate_alt = candidate_image.get("alt") if candidate_image else None
            for value in (candidate_name, candidate_title, candidate_alt):
                value = _normalize_viyar_edge_text(value)
                if value:
                    title_candidates.append(value)

        name = max(title_candidates, key=len) if title_candidates else None
        title = name
        manufacturer_article = _extract_viyar_edge_product_code(name)
        article = supplier_article or _extract_viyar_edge_article(name)

        if article is None and source_url:
            tail = source_url.rstrip("/").rsplit("/", 1)[-1]
            article = _extract_viyar_edge_article(tail)

        dedupe_key = supplier_article or source_url
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        image = None

        image_tag = link.select_one("img") or card_container.select_one("img")

        if image_tag:
            image = (
                image_tag.get("src")
                or image_tag.get("data-src")
                or image_tag.get("data-large")
                or image_tag.get("srcset")
            )

            if image and "," in image:
                image = image.split(",", 1)[0].split()[0]

        if image and not image.startswith("http"):
            image = urljoin("https://viyar.ua", image)

        card_text = card_container.get_text(" ", strip=True)
        width_mm, thickness_mm = _extract_viyar_edge_dimensions_from_text(name)
        price_text_match = re.search(
            r"\d[\d\s,.]*\s*(?:₴|грн|UAH)(?:\s*/\s*[^\s]+)?",
            card_text,
            re.IGNORECASE,
        )
        price, currency, unit = _parse_viyar_edge_price(
            price_text_match.group(0) if price_text_match else None
        )
        availability = "В наявності" if re.search(r"\bв\s+наявності\b", card_text, re.IGNORECASE) else None

        cards.append(
            {
                "article": article,
                # A card's visible article may be the manufacturer article;
                # leave this unset unless the card explicitly exposes the
                # supplier article so source validation cannot compare the
                # wrong identity.
                "supplier_article": supplier_article,
                "manufacturer_article": manufacturer_article,
                "name": name,
                "title": title,
                "source_url": source_url,
                "image_url": image,
                "width_mm": width_mm,
                "thickness_mm": thickness_mm,
                "price": price,
                "currency": currency,
                "unit": unit,
                "availability": availability,
                "source": "viyar",
            }
        )

    return cards


async def _fetch_viyar_recommended_edge_cards_from_api(page, material_url, diagnostics=None):

    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update({
            "status": None,
            "recommendation_status": None,
            "reason": None,
            "candidate_count": 0,
        })

    request = getattr(page, "request", None)
    if request is None or not hasattr(request, "get"):
        return None

    path_parts = [part for part in urlsplit(material_url).path.split("/") if part]
    if not path_parts:
        return None
    slug = unquote(path_parts[-1])

    product_filter = json.dumps({"slug": slug}, ensure_ascii=False, separators=(",", ":"))
    product_url = "https://viyar.ua/apiNew/products?" + urlencode(
        {"lang": "uk", "filter_query": product_filter}
    )
    product_response = await asyncio.wait_for(request.get(product_url), timeout=15000 / 1000)
    if diagnostics is not None:
        diagnostics["status"] = product_response.status
    if product_response.status != 200:
        if diagnostics is not None:
            diagnostics["reason"] = "material_api_http_error"
        return None
    product_payload = await product_response.json()
    product_items = product_payload.get("items") if isinstance(product_payload, dict) else None
    if not product_items:
        if diagnostics is not None:
            diagnostics["reason"] = "material_api_empty"
        return None

    recommendation_ids = product_items[0].get("bend_recommendation_ids") or []
    if not recommendation_ids:
        if diagnostics is not None:
            diagnostics["reason"] = "recommendation_ids_empty"
        return []

    recommendation_filter = json.dumps(
        {"product_id": {"$in": list(dict.fromkeys(str(value) for value in recommendation_ids))}},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    recommendations_url = "https://viyar.ua/apiNew/products?" + urlencode(
        {
            "limit": "200",
            "lang": "uk",
            "extend_additional": "true",
            "filter_query": recommendation_filter,
            "view": "short",
            "city_id": "67d2fa32a2f1420664e13d8a",
        }
    )
    recommendations_response = await asyncio.wait_for(request.get(recommendations_url), timeout=15000 / 1000)
    if diagnostics is not None:
        diagnostics["recommendation_status"] = recommendations_response.status
    if recommendations_response.status != 200:
        if diagnostics is not None:
            diagnostics["reason"] = "recommendation_api_http_error"
        return None
    recommendations_payload = await recommendations_response.json()
    recommendations = recommendations_payload.get("items") if isinstance(recommendations_payload, dict) else None
    if not recommendations:
        if diagnostics is not None:
            diagnostics["reason"] = "recommendation_api_empty"
        return []

    by_id = {str(item.get("id")): item for item in recommendations if item.get("id")}
    by_product_id = {str(item.get("product_id")): item for item in recommendations if item.get("product_id")}
    cards = []
    seen_articles = set()
    seen_product_ids = set()
    for recommendation_id in recommendation_ids:
        item = by_id.get(str(recommendation_id)) or by_product_id.get(str(recommendation_id))
        if not item:
            continue
        article = _normalize_viyar_edge_text(item.get("product_code"))
        product_id = _normalize_viyar_edge_text(item.get("id") or item.get("product_id"))
        dedupe_key = article or product_id
        if not dedupe_key or dedupe_key in seen_articles or product_id in seen_product_ids:
            continue
        seen_articles.add(dedupe_key)
        if product_id:
            seen_product_ids.add(product_id)

        title = _normalize_viyar_edge_text(item.get("product_title"))
        slug_value = _normalize_viyar_edge_text(item.get("slug"))
        source_url = urljoin("https://viyar.ua", f"/ua/catalog/{slug_value}/") if slug_value else None
        image_url = item.get("preview_path_old") or item.get("preview_path")
        width_mm, thickness_mm = _extract_viyar_edge_dimensions_from_text(title)
        cards.append(
            {
                "article": article,
                "supplier_article": article,
                "manufacturer_article": _extract_viyar_edge_product_code(title),
                "name": title,
                "title": title,
                "source_url": source_url,
                "image_url": image_url,
                "width_mm": width_mm,
                "thickness_mm": thickness_mm,
                "source": "viyar_api",
                "api_product_id": product_id,
            }
        )

    if diagnostics is not None:
        diagnostics["candidate_count"] = len(cards)
        diagnostics["reason"] = None if cards else "recommendation_api_no_usable_items"
    return cards


# =====================================================
# EXTRACT VIYAR EDGE DETAIL
# =====================================================

def _normalize_viyar_edge_text(value):

    if value is None:
        return None

    text = " ".join(str(value).replace("\xa0", " ").split()).strip()

    return text or None


def _normalize_viyar_edge_url(value):

    if not value:
        return None

    url = str(value).strip()

    if not url:
        return None

    url = url.split("?")[0]
    url = url.split("#")[0]

    if not url.startswith("http"):
        url = urljoin("https://viyar.ua", url)

    return url


def _parse_viyar_edge_price(text):

    if not text:
        return None, None, None

    normalized = _normalize_viyar_edge_text(text)
    if not normalized:
        return None, None, None

    price = None
    currency = None
    unit = None

    price_match = None

    for token in normalized.replace(",", ".").split():
        try:
            price = float(token)
            price_match = token
            break
        except:
            continue

    if "UAH" in normalized or "грн" in normalized or "₴" in normalized:
        currency = "UAH"

    if "/ м.п." in normalized or "м.п." in normalized:
        unit = "м.п."
    elif "/ шт." in normalized or "шт." in normalized:
        unit = "шт."

    return price, currency, unit


def _extract_viyar_edge_characteristics(soup):

    characteristics = {}

    for row in soup.select("tr.vr-block-char__tr"):

        key_node = row.select_one(".vr-block-char__name")
        value_node = row.select_one(".vr-block-char__value")

        key = _normalize_viyar_edge_text(key_node.get_text(" ", strip=True) if key_node else None)
        value = _normalize_viyar_edge_text(value_node.get_text(" ", strip=True) if value_node else None)

        if key and value:
            characteristics[key.rstrip(":")] = value

    for row in soup.select(".productAttr"):

        key_node = row.select_one(".productAttr__key")
        value_node = row.select_one(".productAttr__value")

        key = _normalize_viyar_edge_text(key_node.get_text(" ", strip=True) if key_node else None)
        value = _normalize_viyar_edge_text(value_node.get_text(" ", strip=True) if value_node else None)

        if key and value:
            characteristics[key.rstrip(":")] = value

    return characteristics


def _extract_viyar_supplier_article(characteristics):
    """Return the explicit VIYAR product code, never a title-derived code."""
    for key in ("Код", "Код товару", "Код товару VIYAR"):
        value = _normalize_viyar_edge_text((characteristics or {}).get(key))
        if value:
            return value
    return None


def parse_viyar_edge_detail(
    html,
    source_url=None,
    fallback_image_url=None,
    fallback_image_trusted=False,
):

    soup = html if hasattr(html, "select_one") else BeautifulSoup(html, "html.parser")

    products = _extract_viyar_json_ld(soup)
    product = products[0] if products else {}
    offers = product.get("offers") if isinstance(product, dict) else {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    offers = offers if isinstance(offers, dict) else {}

    title = (
        soup.select_one("h1")
        or soup.select_one("[itemprop='name']")
        or soup.select_one("title")
    )
    title = _normalize_viyar_edge_text(title.get_text(" ", strip=True) if title else None)

    product_id = _normalize_viyar_edge_text(product.get("sku")) or _normalize_viyar_edge_text(
        soup.select_one("[data-owner-id]").get("data-owner-id") if soup.select_one("[data-owner-id]") else None
    )
    characteristics = _extract_viyar_edge_characteristics(soup)
    for key, value in _extract_viyar_labeled_characteristics(soup).items():
        characteristics[key] = value
    explicit_supplier_article = _extract_viyar_supplier_article(characteristics)
    product_id = explicit_supplier_article or product_id

    structured_brand = (product.get("brand") or {}).get("name") if isinstance(product.get("brand"), dict) else None
    brand = (
        characteristics.get("Виробник")
        or structured_brand
        or _extract_viyar_edge_brand(soup, title=title, source_url=source_url)
    )
    brand = _extract_viyar_edge_brand_candidate(brand)
    manufacturer_evidence = _viyar_manufacturer_source_evidence(soup, characteristics, product)
    manufacturer_missing_at_source = not brand and not manufacturer_evidence["field_present"]
    manufacturer_parse_failed = not brand and manufacturer_evidence["field_present"]

    price = None
    currency = None
    unit = None

    structured_price = offers.get("price")
    if structured_price not in (None, ""):
        try:
            price = float(str(structured_price).replace(",", "."))
        except (TypeError, ValueError):
            price = None
    structured_currency = offers.get("priceCurrency")
    if structured_currency in {"UAH", "грн", "₴"}:
        currency = "UAH"

    price_node = (
        soup.select_one("#product_price")
        or soup.select_one("[itemprop='price']")
        or soup.select_one(".card-info-prices__price-row .price-actual")
        or soup.select_one(".price-actual")
    )

    if price_node and price is None:
        price, currency, unit = _parse_viyar_edge_price(price_node.get_text(" ", strip=True))

    if price is None:
        price_text = soup.get_text(" ", strip=True)
        price_match = re.search(
            r"\d[\d\s,.]*\s*(?:₴|грн|UAH)(?:\s*/\s*[^\s]+)?",
            price_text,
            re.IGNORECASE,
        )
        if price_match:
            price, parsed_currency, parsed_unit = _parse_viyar_edge_price(price_match.group(0))
            currency = currency or parsed_currency
            unit = unit or parsed_unit

    if currency is None:
        currency_node = (
            soup.select_one("[itemprop='priceCurrency']")
            or soup.select_one(".price-currency")
        )
        currency_text = _normalize_viyar_edge_text(
            currency_node.get("content") if currency_node and currency_node.get("content") else (
                currency_node.get_text(" ", strip=True) if currency_node else None
            )
        )
        if currency_text in {"UAH", "грн", "₴"}:
            currency = "UAH"

    if unit is None:
        unit_node = soup.select_one(".text-unit")
        unit = _normalize_viyar_edge_text(unit_node.get_text(" ", strip=True) if unit_node else None)

    if unit is None:
        unit_match = re.search(r"(?:₴|грн|UAH)\s*/\s*(м\.п\.|шт\.?|лист)", soup.get_text(" ", strip=True), re.IGNORECASE)
        unit = unit_match.group(1) if unit_match else None

    availability_node = (
        soup.select_one(".productLabel")
        or soup.select_one("[itemprop='availability']")
        or soup.select_one(".availability")
    )
    availability = _normalize_viyar_edge_text(availability_node.get_text(" ", strip=True) if availability_node else None)
    structured_availability = str(offers.get("availability") or "")
    if not availability and structured_availability:
        availability = "В наявності" if structured_availability.rsplit("/", 1)[-1].lower() in {"instock", "limitedavailability"} else None
    if not availability:
        visible_text = soup.get_text(" ", strip=True)
        if re.search(r"\b(?:є\s+)?в\s+наявності\b", visible_text, re.IGNORECASE):
            availability = "В наявності"
    if availability:
        lowered = availability.lower()
        if "скоро у продажу" in lowered:
            availability = "Скоро у продажу"
        elif "в наявності" in lowered or "є в наявності" in lowered:
            availability = "В наявності"

    structured_image_urls = _extract_viyar_json_ld_image_urls(
        [
            product
            for product in products
            if str(product.get("sku") or "").strip() == str(product_id or "").strip()
        ]
    )
    structured_image_families = {
        re.sub(r"(?:_[A-Za-z0-9]{4,})?(?=\.[A-Za-z]+$)", "", url.rsplit("/", 1)[-1].lower())
        for url in structured_image_urls
    }
    image_urls = _select_viyar_product_image_urls(
        _dedupe_viyar_image_urls(
            structured_image_urls
            + _extract_viyar_dom_image_urls(soup, preferred_families=structured_image_families)
            + [_extract_viyar_edge_image_url(soup), fallback_image_url]
        ),
        supplier_article=product_id,
        trusted_urls=(structured_image_urls + ([fallback_image_url] if fallback_image_trusted else [])),
    )
    image = image_urls[0] if image_urls else None

    manufacturer_article = None
    if title:
        manufacturer_article = _extract_viyar_edge_product_code(title)

    if manufacturer_article is None and source_url:
        tail = _normalize_viyar_edge_url(source_url)
        if tail:
            slug = tail.rstrip("/").rsplit("/", 1)[-1]
            manufacturer_article = _extract_viyar_edge_product_code(slug)

    material_type = _extract_viyar_edge_material_type(
        characteristics,
        title=title,
        source_url=source_url,
    )
    technology_code = _normalize_viyar_edge_technology(characteristics)

    thickness_value = next(
        (characteristics.get(key) for key in ("Товщина, мм", "Товщина", "Товщина мм") if characteristics.get(key)),
        None,
    )
    thickness_mm = None
    if thickness_value:
        thickness_match = re.search(r"(\d+(?:[.,]\d+)?)", thickness_value.replace(",", "."))
        if thickness_match:
            thickness_mm = float(thickness_match.group(1))

    width_value = next(
        (characteristics.get(key) for key in ("Ширина, мм", "Ширина", "Ширина мм") if characteristics.get(key)),
        None,
    )
    width_mm = None
    if width_value:
        width_match = re.search(r"(\d+(?:[.,]\d+)?)", width_value.replace(",", "."))
        if width_match:
            width_mm = float(width_match.group(1))

    package_length = next(
        (characteristics.get(key) for key in ("Довжина рулону", "Довжина", "Довжина, м.п.") if characteristics.get(key)),
        None,
    )
    if package_length is None and title:
        roll_match = re.search(r"\((\d+(?:[.,]\d+)?)\s*(?:м\.п\.|m\.p\.)", title, re.IGNORECASE)
        package_length = roll_match.group(1).replace(",", ".") if roll_match else None
    package_length = _normalize_viyar_edge_text(package_length)

    color = (
        characteristics.get("Декор (лицьова)")
        or characteristics.get("Декор")
        or characteristics.get("Колір")
    )
    color = _normalize_viyar_edge_text(color)

    finish = (
        characteristics.get("Напрямок текстури")
        or characteristics.get("Текстура")
        or characteristics.get("Фініш")
    )
    finish = _normalize_viyar_edge_text(finish)

    full_name = _normalize_viyar_edge_text(title)

    title_width_mm, title_thickness_mm = _extract_viyar_edge_dimensions_from_text(title)

    technical_width = width_mm
    technical_thickness = thickness_mm

    return {
        "canonical_candidate": {
            "manufacturer": brand,
            "manufacturer_article": manufacturer_article,
            "name": full_name,
            "decor_code": None,
            "color": color,
            "material_type": material_type,
            "technology_code": technology_code,
            "width_mm": technical_width if technical_width is not None else title_width_mm,
            "thickness_mm": technical_thickness if technical_thickness is not None else title_thickness_mm,
            "nominal_width_mm": title_width_mm,
            "roll_length": package_length,
            "country": characteristics.get("Країна-виробник") or characteristics.get("Країна виробник"),
            "finish": finish,
            "image_url": image,
            "image_urls": image_urls,
        },
        "supplier_offer_candidate": {
            "supplier": "viyar",
            "article": product_id,
            "external_product_id": None,
            "source_url": _normalize_viyar_edge_url(source_url),
            "unit": unit,
            "availability": availability,
            "price": price,
            "currency": currency,
            "package_length": package_length,
            "source_payload": {
                "title": full_name,
                "brand": brand,
                "characteristics": characteristics,
                "image_url": image,
                "image_urls": image_urls,
                "price_text": _normalize_viyar_edge_text(
                    price_node.get_text(" ", strip=True) if price_node else None
                ),
            },
        },
        "raw_characteristics": characteristics,
        "manufacturer_missing_at_source": manufacturer_missing_at_source,
        "manufacturer_parse_failed": manufacturer_parse_failed,
        "manufacturer_source_evidence": manufacturer_evidence,
    }


def _build_viyar_edge_preview_entry(card, parsed, status, error=None, reason=None, missing_fields=None):

    return {
        "status": status,
        "error": error,
        "discovered_card": card,
        "canonical_candidate": parsed.get("canonical_candidate") if isinstance(parsed, dict) else None,
        "supplier_offer_candidate": parsed.get("supplier_offer_candidate") if isinstance(parsed, dict) else None,
        "raw_characteristics": parsed.get("raw_characteristics") if isinstance(parsed, dict) else {},
        "reason": reason,
        "missing_fields": list(missing_fields or []),
        "manufacturer_missing_at_source": bool(parsed.get("manufacturer_missing_at_source")) if isinstance(parsed, dict) else False,
        "manufacturer_parse_failed": bool(parsed.get("manufacturer_parse_failed")) if isinstance(parsed, dict) else False,
    }


def _classify_viyar_edge_preview_status(parsed):

    canonical = parsed.get("canonical_candidate") or {}
    supplier = parsed.get("supplier_offer_candidate") or {}

    required_canonical_fields = (
        "manufacturer",
        "manufacturer_article",
        "name",
        "material_type",
        "width_mm",
        "thickness_mm",
    )
    required_supplier_fields = (
        "supplier",
        "article",
        "source_url",
        "unit",
    )

    canonical_missing = [
        field
        for field in required_canonical_fields
        if canonical.get(field) in (None, "")
    ]

    if canonical_missing == ["manufacturer"] and parsed.get("manufacturer_missing_at_source"):
        canonical["manufacturer"] = MISSING_MANUFACTURER_NAME
        parsed["canonical_candidate"] = canonical
        return {
            "status": "parsed",
            "reason": "supplier_manufacturer_not_specified",
            "missing_fields": [],
        }

    if canonical_missing == ["manufacturer"] and parsed.get("manufacturer_parse_failed"):
        return {
            "status": "needs_review",
            "reason": "manufacturer_parse_failed",
            "missing_fields": canonical_missing,
        }
    supplier_missing = [
        field
        for field in required_supplier_fields
        if supplier.get(field) in (None, "")
    ]

    if canonical_missing:
        return {
            "status": "needs_review",
            "reason": "missing_identity_fields",
            "missing_fields": canonical_missing,
        }

    if supplier_missing:
        return {
            "status": "needs_review",
            "reason": "missing_supplier_fields",
            "missing_fields": supplier_missing,
        }

    return {
        "status": "parsed",
        "reason": None,
        "missing_fields": [],
    }


async def preview_viyar_edge_product(
    product_url,
    page,
    *,
    fetcher=None,
    expected_supplier_article=None,
):

    if fetcher is None:
        fetcher = fetch_with_retry

    normalized_product_url = _normalize_viyar_edge_url(product_url)
    product_html = await fetcher(page, normalized_product_url)

    if not product_html:
        return {
            "success": False,
            "error": "Edge page could not be fetched",
            "source_url": normalized_product_url,
            "items": [],
            "preview_count": 0,
        }

    parsed = parse_viyar_edge_detail(product_html, source_url=normalized_product_url)
    source_supplier_article = (
        parsed.get("supplier_offer_candidate", {}).get("article")
        if isinstance(parsed, dict)
        else None
    )
    if expected_supplier_article:
        if str(expected_supplier_article).strip() != str(source_supplier_article or "").strip():
            return {
                "success": False,
                "error": "source_product_mismatch",
                "reason": "source_product_mismatch",
                "requested_supplier_article": str(expected_supplier_article),
                "source_supplier_article": str(source_supplier_article),
                "requested_url": normalized_product_url,
                "final_url": normalized_product_url,
                "items": [],
                "preview_count": 0,
            }
    classification = _classify_viyar_edge_preview_status(parsed)

    if classification["status"] != "parsed":
        return {
            "success": False,
            "error": "Edge candidate could not be parsed",
            "source_url": normalized_product_url,
            "items": [],
            "preview_count": 0,
        }

    canonical = parsed.get("canonical_candidate") or {}
    supplier = parsed.get("supplier_offer_candidate") or {}
    discovered_card = {
        "article": canonical.get("manufacturer_article") or supplier.get("article"),
        "name": canonical.get("name"),
        "source_url": normalized_product_url,
        "image_url": canonical.get("image_url"),
        "source": "viyar",
    }

    return {
        "success": True,
        "source_url": normalized_product_url,
        "items": [
            _build_viyar_edge_preview_entry(
                discovered_card,
                parsed,
                "parsed",
            )
        ],
        "preview_count": 1,
    }


async def preview_viyar_recommended_edges(
    material_url,
    page,
    *,
    fetcher=None,
    progress_callback=None,
):

    if fetcher is None:
        fetcher = fetch_with_retry

    normalized_material_url = _normalize_viyar_edge_url(material_url)
    discovery = {
        "source": "none",
        "api_candidate_count": 0,
        "dom_candidate_count": 0,
        "final_candidate_count": 0,
        "api_reason": None,
        "api_status": None,
        "api_recommendation_status": None,
    }
    cards = None
    if hasattr(page, "request"):
        api_diagnostics = {}
        try:
            cards = await _fetch_viyar_recommended_edge_cards_from_api(
                page,
                normalized_material_url,
                diagnostics=api_diagnostics,
            )
        except Exception as error:
            api_diagnostics["reason"] = f"{type(error).__name__}: {error}"[:240]
            logging.warning("VIYAR recommended edge API discovery failed: %s", error)
        discovery["api_candidate_count"] = int(api_diagnostics.get("candidate_count") or 0)
        discovery["api_reason"] = api_diagnostics.get("reason")
        discovery["api_status"] = api_diagnostics.get("status")
        discovery["api_recommendation_status"] = api_diagnostics.get("recommendation_status")

    material_html = None
    if cards is None:
        material_html = await fetcher(page, normalized_material_url)
        if not material_html:
            return {
                "success": False,
                "error": "Material page could not be fetched",
                "material_url": normalized_material_url,
                "items": [],
                "discovery": discovery,
            }
        cards = extract_recommended_edge_cards(material_html)
        discovery["dom_candidate_count"] = len(cards)

    # Recommended cards are lazy-rendered on the live product page. If the
    # first document snapshot only contains the section shell, let the
    # existing Playwright page hydrate that section and parse the resulting
    # DOM with the same pure HTML extractor.
    if not cards and hasattr(page, "locator"):
        try:
            section = page.locator("#rekomenduemayakromka")
            if await section.count():
                anchor = page.locator('a[href*="#rekomenduemayakromka"]').first
                if await anchor.count():
                    try:
                        await anchor.click(timeout=1500)
                    except Exception:
                        pass
                await section.scroll_into_view_if_needed()
                deadline = asyncio.get_running_loop().time() + (
                    VIYAR_RECOMMENDED_EDGE_HYDRATION_TIMEOUT_MS / 1000
                )
                cards = []
                while True:
                    cards = extract_recommended_edge_cards(await page.content())
                    if cards or asyncio.get_running_loop().time() >= deadline:
                        break
                    await page.wait_for_timeout(VIYAR_RECOMMENDED_EDGE_HYDRATION_POLL_MS)
                discovery["dom_candidate_count"] = len(cards)
        except Exception as error:
            logging.warning("VIYAR recommended edge hydration failed: %s", error)
            discovery["api_reason"] = discovery["api_reason"] or f"dom_hydration_{type(error).__name__}"
    if cards is None:
        cards = []

    if cards:
        discovery["source"] = "api" if discovery["api_candidate_count"] else "hydrated_dom"
    async def notify(event: dict) -> None:
        if progress_callback is None:
            return
        result = progress_callback(event)
        if asyncio.iscoroutine(result):
            await result

    unique_cards = []
    fetched_urls = set()
    fetched_identities = set()
    for card in cards:
        source_url = card.get("source_url")
        if not source_url:
            continue
        supplier_article = _normalize_viyar_edge_text(card.get("supplier_article"))
        product_identity = _normalize_viyar_edge_text(card.get("api_product_id"))
        identity = supplier_article or product_identity or _normalize_viyar_edge_text(card.get("article")) or source_url
        if source_url in fetched_urls or identity in fetched_identities:
            continue
        fetched_urls.add(source_url)
        fetched_identities.add(identity)
        unique_cards.append(card)

    discovery["final_candidate_count"] = len(unique_cards)
    if not unique_cards:
        discovery["source"] = "none"

    await notify({"phase": "recommendations_found", "total": len(unique_cards)})

    async def parse_card(card, detail_page):
        source_url = card.get("source_url")
        fetch_diagnostics = {}
        started_at = asyncio.get_running_loop().time()
        try:
            if fetcher is fetch_with_retry:
                edge_html = await fetcher(
                    detail_page,
                    source_url,
                    diagnostics=fetch_diagnostics,
                )
            else:
                edge_html = await fetcher(detail_page, source_url)
            if not edge_html:
                raise ValueError("Edge detail page could not be fetched")

            parsed = parse_viyar_edge_detail(
                edge_html,
                source_url=source_url,
                fallback_image_url=card.get("image_url"),
                fallback_image_trusted=card.get("source") == "viyar_api",
            )
            # ``article`` is the manufacturer article in legacy cards; only an
            # explicit supplier article is safe to use for source identity.
            expected_supplier_article = card.get("supplier_article")
            supplier_candidate = parsed.get("supplier_offer_candidate") or {}
            source_supplier_article = supplier_candidate.get("article")
            if expected_supplier_article:
                if str(expected_supplier_article).strip() != str(source_supplier_article or "").strip():
                    entry = _build_viyar_edge_preview_entry(
                        card,
                        parsed,
                        "failed",
                        error="source_product_mismatch",
                        reason="source_product_mismatch",
                    )
                    entry.update({
                        "requested_supplier_article": str(expected_supplier_article),
                        "source_supplier_article": str(source_supplier_article),
                        "requested_url": source_url,
                        "final_url": fetch_diagnostics.get("final_url") or source_url,
                    })
                    entry["attempts"] = fetch_diagnostics.get("attempts")
                    entry["elapsed_ms"] = int(
                        (asyncio.get_running_loop().time() - started_at) * 1000
                    )
                    entry["exception_type"] = None
                    entry["fetch_reason"] = "source_product_mismatch"
                    return entry
            classification = _classify_viyar_edge_preview_status(parsed)
            entry = _build_viyar_edge_preview_entry(
                card,
                parsed,
                classification["status"],
                reason=classification["reason"],
                missing_fields=classification["missing_fields"],
            )
            entry["attempts"] = fetch_diagnostics.get("attempts")
            entry["elapsed_ms"] = int(
                (asyncio.get_running_loop().time() - started_at) * 1000
            )
            entry["exception_type"] = None
            entry["fetch_reason"] = None
            entry.update({
                "requested_supplier_article": expected_supplier_article,
                "source_supplier_article": source_supplier_article,
                "requested_url": source_url,
                "final_url": fetch_diagnostics.get("final_url") or source_url,
            })
            return entry
        except Exception as error:
            entry = _build_viyar_edge_preview_entry(
                card,
                {},
                "failed",
                error=str(error) or "Edge preview failed",
            )
            entry["attempts"] = fetch_diagnostics.get("attempts")
            entry["elapsed_ms"] = int(
                (asyncio.get_running_loop().time() - started_at) * 1000
            )
            entry["exception_type"] = (
                fetch_diagnostics.get("exception_type") or type(error).__name__
            )
            entry["fetch_reason"] = (
                fetch_diagnostics.get("reason")
                or ("parser_error" if edge_html else "other")
            )
            entry.update({
                "requested_supplier_article": card.get("supplier_article"),
                "requested_url": source_url,
                "final_url": fetch_diagnostics.get("final_url") or source_url,
            })
            return entry

    page_context = getattr(page, "context", None)
    worker_semaphore = asyncio.Semaphore(min(3, max(1, len(unique_cards))))

    async def new_detail_page():
        if page_context is not None and hasattr(page_context, "new_page"):
            return await page_context.new_page(), True
        return page, False

    checked_count = 0

    async def parse_index(index, card):
        nonlocal checked_count
        started_at = asyncio.get_running_loop().time()
        try:
            async with worker_semaphore:
                detail_page, owned = await new_detail_page()
                try:
                    item = await asyncio.wait_for(
                        parse_card(card, detail_page),
                        timeout=45000 / 1000,
                    )
                    if item.get("reason") == "source_product_mismatch" and owned:
                        retry_page, retry_owned = await new_detail_page()
                        try:
                            item = await asyncio.wait_for(
                                parse_card(card, retry_page),
                                timeout=45000 / 1000,
                            )
                            item["mismatch_retry"] = True
                        finally:
                            if retry_owned and hasattr(retry_page, "close"):
                                await retry_page.close()
                    return item
                finally:
                    if owned and hasattr(detail_page, "close"):
                        await detail_page.close()
        finally:
            checked_count += 1
            await notify({
                "phase": "edge_detail",
                "checked": checked_count,
                "total": len(unique_cards),
                "supplier_article": card.get("supplier_article") or card.get("article"),
                "elapsed_ms": int((asyncio.get_running_loop().time() - started_at) * 1000),
            })

    def build_task_exception_entry(index, card, error):
        cancelled = isinstance(error, asyncio.CancelledError)
        entry = _build_viyar_edge_preview_entry(
            card,
            {},
            "failed",
            error=("Edge preview task was cancelled" if cancelled else str(error) or "Edge preview task failed"),
            reason="task_cancelled" if cancelled else "task_exception",
        )
        entry["candidate_index"] = index
        entry["cancelled"] = cancelled
        entry["exception_type"] = type(error).__name__
        entry["fetch_reason"] = "cancelled" if cancelled else "task_exception"
        entry["attempts"] = None
        entry["elapsed_ms"] = None
        entry.update({
            "requested_supplier_article": card.get("supplier_article"),
            "requested_url": card.get("source_url"),
            "final_url": card.get("source_url"),
        })
        return entry

    if len(unique_cards) == 1:
        items = []
        for index, card in enumerate(unique_cards):
            try:
                item = await parse_index(index, card)
            except BaseException as error:
                item = build_task_exception_entry(index, card, error)
            item["candidate_index"] = index
            items.append(item)
    else:
        gathered_items = list(await asyncio.gather(*(
            parse_index(index, card) for index, card in enumerate(unique_cards)
        ), return_exceptions=True))
        items = [
            (
                build_task_exception_entry(index, card, item)
                if isinstance(item, BaseException)
                else {**item, "candidate_index": index}
            )
            for index, (card, item) in enumerate(zip(unique_cards, gathered_items))
        ]

    result_count = len(items)
    parsed_count = sum(item.get("status") == "parsed" for item in items)
    failed_count = sum(item.get("status") == "failed" for item in items)
    review_count = sum(item.get("status") == "needs_review" for item in items)
    logger = logging.getLogger(__name__)
    logger.info(
        "[MATERIAL_EDGE_PREVIEW_TERMINAL] total=%s result_count=%s parsed=%s failed=%s needs_review=%s missing_indexes=%s",
        len(unique_cards),
        result_count,
        parsed_count,
        failed_count,
        review_count,
        [index for index in range(len(unique_cards)) if index >= result_count],
    )

    return {
        "success": True,
        "material_url": normalized_material_url,
        "recommended_edges_count": len(unique_cards),
        "discovery": discovery,
        "preview_count": len(items),
        "candidate_results_count": result_count,
        "items": items,
    }


# =====================================================
# SAVE MATERIAL
# =====================================================

async def save_to_db(
    article,
    name,
    price,
    image,
    city,
    category
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            INSERT INTO materials (
                article,
                name,
                image,
                category
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(article)
            DO UPDATE SET

                name=excluded.name,
                image=excluded.image,
                category=excluded.category
            """,
            (
                article,
                name,
                image,
                category
            )
        )

        await db.execute(
            """
            INSERT OR REPLACE INTO material_prices (
                article,
                city,
                price
            )
            VALUES (?, ?, ?)
            """,
            (
                article,
                city,
                price
            )
        )

        await db.commit()


# =====================================================
# SAVE SERVICE
# =====================================================

async def save_service_to_db(
    article,
    name,
    price,
    city,
    service_type
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            INSERT INTO services_prices (
                article,
                name,
                city,
                service_type,
                price
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(article, city)
            DO UPDATE SET

                name=excluded.name,
                price=excluded.price,
                service_type=excluded.service_type
            """,
            (
                article,
                name,
                city,
                service_type,
                price
            )
        )

        await db.commit()


# =====================================================
# FETCH WITH RETRY
# =====================================================

async def fetch_with_retry(
    page,
    url,
    retries=3,
    diagnostics=None,
):

    started_at = asyncio.get_running_loop().time()
    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update({
            "attempts": 0,
            "exception_type": None,
            "error": None,
            "reason": None,
            "status": None,
        })

    for i in range(retries):

        try:

            response = await page.goto(
                url,
                timeout=15000
            )

            if diagnostics is not None:
                diagnostics["attempts"] = i + 1
                diagnostics["status"] = getattr(response, "status", None)

            await page.wait_for_load_state(
                "domcontentloaded"
            )

            await asyncio.sleep(1)

            content = await page.content()
            if diagnostics is not None:
                diagnostics["elapsed_ms"] = int(
                    (asyncio.get_running_loop().time() - started_at) * 1000
                )
                diagnostics["final_url"] = getattr(page, "url", None) or url
                diagnostics["reason"] = None
            return content

        except Exception as e:

            if diagnostics is not None:
                diagnostics["attempts"] = i + 1
                diagnostics["exception_type"] = type(e).__name__
                diagnostics["error"] = str(e) or None
                message = (str(e) or "").lower()
                if isinstance(e, asyncio.TimeoutError) or "timeout" in message:
                    diagnostics["reason"] = "timeout"
                elif any(
                    marker in message
                    for marker in (
                        "err_",
                        "connection",
                        "connect eacces",
                        "network",
                        "socket",
                    )
                ):
                    diagnostics["reason"] = "network_error"
                else:
                    diagnostics["reason"] = "other"

            logging.warning(
                f"Retry {i+1} → {e}"
            )

            await asyncio.sleep(2)

    if diagnostics is not None:
        diagnostics["elapsed_ms"] = int(
            (asyncio.get_running_loop().time() - started_at) * 1000
        )
    return None


# =====================================================
# CHECK PRICE CHANGED
# =====================================================

async def is_price_changed(
    db,
    article,
    city,
    new_price
):

    cursor = await db.execute(
        """
        SELECT price
        FROM material_prices
        WHERE article=? AND city=?
        """,
        (
            article,
            city
        )
    )

    row = await cursor.fetchone()

    if not row:
        return True

    try:
        return float(row[0]) != float(new_price)
    except:
        return True


# =====================================================
# PARSE CITY
# =====================================================

async def parse_city(
    browser,
    city,
    cookie_value
):

    context = None

    try:

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )

        await context.add_cookies([
            {
                "name": "filial",
                "value": cookie_value,
                "domain": ".viyar.ua",
                "path": "/"
            }
        ])

        page = await context.new_page()

        # =================================================
        # MATERIALS
        # =================================================

        for category, articles in CATEGORIES.items():

            articles = list(set(articles))

            print(f"\n📦 CATEGORY: {category}")

            for article in articles:

                print(
                    f"👉 {city} | {category} | {article}"
                )

                try:

                    url = (
                        f"https://www.viyar.ua/ua/search/?q={article}"
                    )

                    html = await fetch_with_retry(
                        page,
                        url
                    )

                    if not html:

                        print(f"❌ FULL FAIL {article}")
                        continue

                    try:

                        await page.wait_for_selector(
                            ".product-item__name",
                            timeout=5000
                        )

                    except:

                        print(
                            f"➡️ Прямий товар → {article}"
                        )

                    items = page.locator(
                        ".product-item__name"
                    )

                    if await items.count() > 0:

                        link = await items.first.get_attribute(
                            "href"
                        )

                        if not link:

                            print(
                                f"❌ Нема link → {article}"
                            )

                            continue

                        full_url = (
                            "https://www.viyar.ua" + link
                        )

                        await page.goto(
                            full_url,
                            timeout=15000
                        )

                    await page.wait_for_load_state(
                        "domcontentloaded"
                    )

                    if not await page.locator("h1").count():

                        print(f"❌ НЕ товар → {article}")
                        continue

                    html = await page.content()

                    name, price, image = extract(html)

                    async with aiosqlite.connect(DB_NAME) as db:

                        changed = await is_price_changed(
                            db,
                            article,
                            city,
                            price
                        )

                        cursor = await db.execute(
                            """
                            SELECT tg_file_id
                            FROM materials
                            WHERE article = ?
                            """,
                            (article,)
                        )

                        row = await cursor.fetchone()

                    tg_exists = row and row[0]

                    if not changed and tg_exists:

                        logging.info(
                            f"SKIP {article} | {city}"
                        )

                        continue

                    await save_to_db(
                        article,
                        name,
                        price,
                        image,
                        city,
                        category
                    )

                    print(
                        f"✅ SAVED {article} | {price}"
                    )

                    await asyncio.sleep(1)

                except Exception as e:

                    print(
                        f"❌ ERROR {article}: {e}"
                    )

                    continue

        # =================================================
        # SERVICES
        # =================================================

        for service_type, articles in SERVICES.items():

            print(f"\n🛠 SERVICE: {service_type}")

            for article in articles:

                print(
                    f"👉 {city} | "
                    f"{service_type} | "
                    f"{article}"
                )

                try:

                    url = (
                        f"https://www.viyar.ua/ua/search/?q={article}"
                    )

                    html = await fetch_with_retry(
                        page,
                        url
                    )

                    if not html:
                        continue

                    name, price, image = extract(html)

                    if not price:
                        continue

                    try:

                        price = (
                            str(price)
                            .replace(" ", "")
                            .replace("грн", "")
                            .replace(",", ".")
                        )

                        price = float(price)

                    except:
                        continue

                    await save_service_to_db(
                        article=article,
                        name=name,
                        price=price,
                        city=city,
                        service_type=service_type
                    )

                    print(
                        f"✅ SERVICE SAVED: "
                        f"{name} | {price}"
                    )

                except Exception as e:

                    print(
                        f"❌ SERVICE ERROR "
                        f"{article}: {e}"
                    )

    except Exception as e:

        print(f"❌ CITY ERROR {city}: {e}")

    finally:

        if context:

            try:
                await context.close()
            except:
                pass


# =====================================================
# MAIN PARSER
# =====================================================

async def run_parser():

    await update_db()

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        for city, cookie in CITY_COOKIES.items():

            print(f"\n🏙 START CITY: {city}")

            await parse_city(
                browser,
                city,
                cookie
            )

        await browser.close()
