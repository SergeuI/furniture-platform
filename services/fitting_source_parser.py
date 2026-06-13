import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

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


def _clean_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


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

    return {
        "success": True,
        "source_site": "viyar",
        "final_url": final_url,
        "name": name or None,
        "article": article,
        "price": _extract_price(price_text),
        "price_raw": price_text or None,
        "unit": unit or None,
        "image_url": image_url or None,
    }


def _parse_kronas_html(html: str, final_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    name = (
        _first_text(
            soup,
            [
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

    article = (
        _extract_article_from_text(
            _first_text(
                soup,
                [
                    ".product-code",
                    ".sku",
                    "[class*='articul']",
                    "[class*='article']",
                ],
            )
        )
        or _extract_article_from_text(final_url)
    )

    price_text = (
        _first_meta_content(
            soup,
            [
                "[itemprop='price']",
            ],
        )
        or _first_text(
            soup,
            [
                ".productPriceBlock__price",
                "[class*='price']",
                ".product-price",
                ".price",
                ".cost",
            ],
        )
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
                ".product-gallery img",
                ".product-image img",
                "[itemprop='image']",
                "img",
            ],
            "src",
            final_url,
        )
        or _first_attr(
            soup,
            [
                ".product-gallery img",
                ".product-image img",
                "[itemprop='image']",
                "img",
            ],
            "data-src",
            final_url,
        )
    )

    return {
        "success": True,
        "source_site": "kronas",
        "final_url": final_url,
        "name": name or None,
        "article": article,
        "price": _extract_price(price_text),
        "price_raw": price_text or None,
        "unit": None,
        "image_url": image_url or None,
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

    return {
        "success": True,
        "source_site": source_site,
        "final_url": final_url,
        "name": name or None,
        "article": None,
        "price": _extract_price(price_text),
        "price_raw": price_text or None,
        "unit": None,
        "image_url": image_url or None,
    }


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

    return {
        "success": True,
        "source_site": "blum",
        "final_url": final_url,
        "name": name or None,
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
            return await _parse_mt_source(normalized_url)

        try:
            status, final_url, html = await _fetch_html(normalized_url)
        except Exception:
            status, final_url, html = 0, normalized_url, ""

        if source_site == "kronas" and status in {0, 403}:
            final_url, html = await _fetch_html_with_browser(
                normalized_url,
                wait_ms=5000,
            )
            status = 200

        if status != 200:
            return {
                "success": False,
                "error": f"Unable to load source page: HTTP {status}",
                "source_site": source_site,
            }

        if source_site == "viyar":
            return _parse_viyar_html(html, final_url)
        if source_site == "kronas":
            return _parse_kronas_html(html, final_url)
        return _parse_generic_html(html, final_url, source_site)
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "Source page timed out",
            "source_site": source_site,
        }
    except Exception as error:
        return {
            "success": False,
            "error": str(error) or type(error).__name__,
            "source_site": source_site,
        }
