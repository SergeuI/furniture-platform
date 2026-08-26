import logging
import asyncio
import json
import re
from urllib.parse import urljoin

from playwright.async_api import async_playwright
import aiosqlite
from bs4 import BeautifulSoup
from services.legacy_db_config import DEFAULT_DB_PATH


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
        if brand:
            return brand

    return None


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
    section = soup.select_one(VIYAR_EDGE_SECTION_SELECTOR)

    if not section:
        return []

    cards = []
    seen_urls = set()

    for link in section.select("a.vr-card__link[href]"):

        href = (link.get("href") or "").strip()

        if not href:
            continue

        source_url = urljoin("https://viyar.ua", href)
        source_url = source_url.split("?")[0]
        source_url = source_url.split("#")[0]

        if source_url in seen_urls:
            continue

        seen_urls.add(source_url)

        title = link.get("title")
        name = link.get_text(" ", strip=True) or title or None
        article = _extract_viyar_edge_article(title) or _extract_viyar_edge_article(name)

        if article is None and source_url:
            tail = source_url.rstrip("/").rsplit("/", 1)[-1]
            article = _extract_viyar_edge_article(tail)

        image = None

        image_tag = link.select_one("img")

        if image_tag:
            image = (
                image_tag.get("src")
                or image_tag.get("data-src")
                or image_tag.get("data-large")
            )

        if image and not image.startswith("http"):
            image = urljoin("https://viyar.ua", image)

        cards.append(
            {
                "article": article,
                "name": name,
                "title": title,
                "source_url": source_url,
                "image_url": image,
                "source": "viyar",
            }
        )

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


def parse_viyar_edge_detail(html, source_url=None):

    soup = html if hasattr(html, "select_one") else BeautifulSoup(html, "html.parser")

    title = (
        soup.select_one("h1")
        or soup.select_one("[itemprop='name']")
        or soup.select_one("title")
    )
    title = _normalize_viyar_edge_text(title.get_text(" ", strip=True) if title else None)

    product_id = _normalize_viyar_edge_text(
        soup.select_one("[data-owner-id]").get("data-owner-id") if soup.select_one("[data-owner-id]") else None
    )
    brand = _extract_viyar_edge_brand(soup, title=title, source_url=source_url)

    price = None
    currency = None
    unit = None

    price_node = (
        soup.select_one("#product_price")
        or soup.select_one("[itemprop='price']")
        or soup.select_one(".card-info-prices__price-row .price-actual")
        or soup.select_one(".price-actual")
    )

    if price_node:
        price, currency, unit = _parse_viyar_edge_price(price_node.get_text(" ", strip=True))

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

    availability_node = (
        soup.select_one(".productLabel")
        or soup.select_one("[itemprop='availability']")
        or soup.select_one(".availability")
    )
    availability = _normalize_viyar_edge_text(
        availability_node.get_text(" ", strip=True) if availability_node else None
    )
    if availability:
        lowered = availability.lower()
        if "скоро у продажу" in lowered:
            availability = "Скоро у продажу"
        elif "в наявності" in lowered or "є в наявності" in lowered:
            availability = "В наявності"

    image = _extract_viyar_edge_image_url(soup)

    characteristics = _extract_viyar_edge_characteristics(soup)

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

    thickness_value = (
        characteristics.get("Товщина")
        or characteristics.get("Товщина, мм")
        or characteristics.get("Товщина мм")
    )
    thickness_mm = None
    if thickness_value:
        import re

        thickness_match = re.search(r"(\d+(?:[.,]\d+)?)", thickness_value.replace(",", "."))
        if thickness_match:
            thickness_mm = float(thickness_match.group(1))

    width_value = (
        characteristics.get("Ширина")
        or characteristics.get("Ширина, мм")
        or characteristics.get("Ширина мм")
    )
    width_mm = None
    if width_value:
        import re

        width_match = re.search(r"(\d+(?:[.,]\d+)?)", width_value.replace(",", "."))
        if width_match:
            width_mm = float(width_match.group(1))

    package_length = (
        characteristics.get("Довжина рулону")
        or characteristics.get("Довжина")
        or characteristics.get("Довжина, м.п.")
    )
    package_length = _normalize_viyar_edge_text(package_length)

    color = (
        characteristics.get("Колір")
        or characteristics.get("Декор")
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

    return {
        "canonical_candidate": {
            "manufacturer": brand,
            "manufacturer_article": manufacturer_article,
            "name": full_name,
            "decor_code": None,
            "color": color,
            "material_type": material_type,
            "width_mm": title_width_mm if title_width_mm is not None else width_mm,
            "thickness_mm": title_thickness_mm if title_thickness_mm is not None else thickness_mm,
            "finish": finish,
            "image_url": image,
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
                "price_text": _normalize_viyar_edge_text(
                    price_node.get_text(" ", strip=True) if price_node else None
                ),
            },
        },
        "raw_characteristics": characteristics,
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


async def preview_viyar_recommended_edges(
    material_url,
    page,
    *,
    fetcher=None,
):

    if fetcher is None:
        fetcher = fetch_with_retry

    normalized_material_url = _normalize_viyar_edge_url(material_url)
    material_html = await fetcher(page, normalized_material_url)

    if not material_html:
        return {
            "success": False,
            "error": "Material page could not be fetched",
            "material_url": normalized_material_url,
            "items": [],
        }

    cards = extract_recommended_edge_cards(material_html)
    items = []
    fetched_urls = set()

    for card in cards:

        source_url = card.get("source_url")
        if not source_url:
            items.append(
                _build_viyar_edge_preview_entry(
                    card,
                    {},
                    "failed",
                    error="Missing edge source_url",
                )
            )
            continue

        if source_url in fetched_urls:
            continue

        fetched_urls.add(source_url)

        try:
            edge_html = await fetcher(page, source_url)
            if not edge_html:
                raise ValueError("Edge detail page could not be fetched")

            parsed = parse_viyar_edge_detail(edge_html, source_url=source_url)
            classification = _classify_viyar_edge_preview_status(parsed)
            items.append(
                _build_viyar_edge_preview_entry(
                    card,
                    parsed,
                    classification["status"],
                    reason=classification["reason"],
                    missing_fields=classification["missing_fields"],
                )
            )
        except Exception as error:
            items.append(
                _build_viyar_edge_preview_entry(
                    card,
                    {},
                    "failed",
                    error=str(error) or "Edge preview failed",
                )
            )

    return {
        "success": True,
        "material_url": normalized_material_url,
        "recommended_edges_count": len(cards),
        "preview_count": len(items),
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
    retries=3
):

    for i in range(retries):

        try:

            await page.goto(
                url,
                timeout=15000
            )

            await page.wait_for_load_state(
                "domcontentloaded"
            )

            await asyncio.sleep(1)

            return await page.content()

        except Exception as e:

            logging.warning(
                f"Retry {i+1} → {e}"
            )

            await asyncio.sleep(2)

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

