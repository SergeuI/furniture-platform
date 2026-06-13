import json
import os
import re
import sys
import traceback

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


VIYAR_BASE_URL = "https://www.viyar.ua"
CITY_COOKIES = {
    "kyiv": "KYIV",
    "lviv": "LVIV",
    "dnipro": "DNIPRO",
    "odessa": "ODESA",
    "kharkiv": "KHARKIV",
    "khmelnytskyi": "KHMELNYTSKYI",
    "rivne": "RIVNE",
}


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

    if "," in asset:
        asset = asset.split(",")[0].split(" ")[0].strip()

    if asset.startswith("//"):
        return f"https:{asset}"

    if asset.startswith("http"):
        return asset

    if asset.startswith("/"):
        return f"{VIYAR_BASE_URL}{asset}"

    return f"{VIYAR_BASE_URL}/{asset.lstrip('/')}"


def _normalize_article(value: str | None) -> str:

    return "".join(re.findall(r"\d+", str(value or "")))


def _cookie_pairs(raw_cookie: str | None) -> list[dict]:

    cookies = []

    for chunk in str(raw_cookie or "").split(";"):
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

    return cookies


def _extract_material_from_html(html: str, article: str, source_url: str) -> dict:

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

    return {
        "article": article,
        "name": name,
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


def _resolve_result_href_from_search_html(html: str, article: str) -> str | None:

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


def _goto_with_retry(page, url: str, retries: int = 3) -> bool:

    for attempt in range(retries):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500 + (attempt * 400))
            return True
        except Exception:
            if attempt == retries - 1:
                return False
            page.wait_for_timeout(1800)

    return False


def _search_from_homepage(page, article: str, trace: list[dict]) -> bool:

    homepage_url = f"{VIYAR_BASE_URL}/ua/"
    _push_trace(trace, "worker.homepage", url=homepage_url)

    if not _goto_with_retry(page, homepage_url):
        return False

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
            if locator.count():
                search_input = locator
                break
        except Exception:
            continue

    if search_input is None:
        _push_trace(trace, "worker.homepage.no_input")
        return False

    search_input.fill(article)
    _push_trace(trace, "worker.homepage.filled", article=article)

    button_selectors = [
        "button:has-text('Шукати')",
        "button:has-text('Search')",
        "button[type='submit']",
    ]

    for selector in button_selectors:
        button = page.locator(selector).first
        try:
            if button.count():
                button.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(1200)
                _push_trace(trace, "worker.homepage.clicked", selector=selector, final_url=page.url)
                return True
        except Exception:
            continue

    try:
        search_input.press("Enter")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1200)
        _push_trace(trace, "worker.homepage.enter", final_url=page.url)
        return True
    except Exception:
        _push_trace(trace, "worker.homepage.submit_failed")
        return False


def _fetch_material(
    article: str,
    city: str | None = None,
    cookie: str | None = None,
    trace: list[dict] | None = None,
    headless: bool = True,
    preferred_url: str | None = None,
) -> tuple[dict, list[dict]]:

    search_url = f"{VIYAR_BASE_URL}/ua/search/?q={article}"
    if trace is None:
        trace = []

    with sync_playwright() as playwright:
        _push_trace(trace, "worker.browser_mode", headless=headless)
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="uk-UA",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
        )

        cookies = _cookie_pairs(cookie)
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

        if cookies:
            context.add_cookies(cookies)
            _push_trace(trace, "worker.cookies", count=len(cookies), city=city)

        page = context.new_page()
        target_search_url = preferred_url or search_url
        _push_trace(trace, "worker.search", url=target_search_url, preferred=bool(preferred_url))

        if not _goto_with_retry(page, target_search_url):
            if not _search_from_homepage(page, article, trace):
                context.close()
                browser.close()
                raise RuntimeError("Viyar search page did not load")

        current_url = page.url
        search_html = page.content()
        search_error_reason = _error_page_reason(search_html, None)
        _push_trace(
            trace,
            "worker.search.loaded",
            final_url=current_url,
            title=_normalize_text(page.title()),
            has_h1=bool(page.locator("h1").count()),
            error_reason=search_error_reason,
        )
        if search_error_reason:
            _push_trace(trace, "worker.search.error_page", final_url=current_url, reason=search_error_reason)
            context.close()
            browser.close()
            raise RuntimeError(search_error_reason)
        resolved_href = _resolve_result_href_from_search_html(search_html, article)
        _push_trace(trace, "worker.search.resolved", href=resolved_href)

        if not resolved_href:
            search_material = _extract_material_from_search_html_v2(
                search_html,
                article=article,
                source_url=current_url,
            )
            _push_trace(
                trace,
                "worker.search.extract",
                source_url=current_url,
                name=search_material.get("name") if search_material else None,
                price=search_material.get("price") if search_material else None,
                has_image=bool(search_material.get("image")) if search_material else False,
            )
            if search_material:
                context.close()
                browser.close()
                return search_material, trace

        if resolved_href:
            target_url = (
                resolved_href
                if resolved_href.startswith("http")
                else f"{VIYAR_BASE_URL}{resolved_href}"
            )
            _push_trace(trace, "worker.product", url=target_url)

            if not _goto_with_retry(page, target_url):
                context.close()
                browser.close()
                raise RuntimeError("Viyar material page did not load")

            current_url = page.url
            _push_trace(
                trace,
                "worker.product.loaded",
                final_url=current_url,
                title=_normalize_text(page.title()),
                has_h1=bool(page.locator("h1").count()),
            )

        if not page.locator("h1").count():
            _push_trace(
                trace,
                "worker.no_h1",
                final_url=current_url,
                title=_normalize_text(page.title()),
            )
            raise LookupError("Material details were not found on Viyar")

        html = page.content()
        material = _extract_material_from_html(
            html=html,
            article=article,
            source_url=current_url,
        )
        material_error_reason = _error_page_reason(html, material)
        _push_trace(
            trace,
            "worker.extract",
            source_url=current_url,
            name=material.get("name"),
            article=material.get("article"),
            price=material.get("price"),
            has_image=bool(material.get("image")),
            error_page=bool(material_error_reason),
            error_reason=material_error_reason,
            title=_normalize_text(page.title()),
        )

        context.close()
        browser.close()

        if not material.get("name") or material_error_reason:
            _push_trace(
                trace,
                "worker.invalid_material",
                source_url=current_url,
                reason=material_error_reason or "Material details were not found on Viyar",
            )
            raise LookupError(material_error_reason or "Material details were not found on Viyar")

        return material, trace


def main() -> int:

    trace: list[dict] = []
    allow_headful_fallback = (
        os.getenv("MATERIAL_WORKER_HEADFUL_FALLBACK", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )

    try:
        payload = json.loads(sys.stdin.read() or "{}")
        article = _normalize_text(payload.get("article"))
        city = _normalize_text(payload.get("city"))
        cookie = payload.get("cookie")
        preferred_url = _normalize_text(payload.get("preferred_url"))

        if not article:
            print(json.dumps({"success": False, "error": "Article is required"}))
            return 1

        try:
            material, trace = _fetch_material(
                article,
                city=city or None,
                cookie=cookie,
                trace=trace,
                headless=True,
                preferred_url=preferred_url or None,
            )
            strategy = "worker_playwright"
        except Exception as first_error:
            _push_trace(
                trace,
                "worker.headless_fallback",
                error=type(first_error).__name__,
                message=_normalize_text(str(first_error)),
                allowed=allow_headful_fallback,
            )
            if not allow_headful_fallback:
                raise first_error

            material, trace = _fetch_material(
                article,
                city=city or None,
                cookie=cookie,
                trace=trace,
                headless=False,
                preferred_url=preferred_url or None,
            )
            strategy = "worker_playwright_headful"

        print(
            json.dumps(
                {
                    "success": True,
                    "material": material,
                    "debug": {
                        "strategy": strategy,
                        "source_url": material.get("source_url"),
                        "trace": trace,
                    },
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as error:
        message = _normalize_text(str(error))
        if not message:
            message = "".join(
                traceback.format_exception_only(error.__class__, error)
            ).strip() or "Unknown Viyar material worker error"
        print(
            json.dumps(
                {
                    "success": False,
                    "error": message,
                    "debug": {
                        "strategy": "worker_playwright",
                        "trace": trace,
                    },
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
