import json
import sys
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)


def _parse_cookie_header(cookie_header: str) -> list[dict]:
    cookies: list[dict] = []

    for chunk in (cookie_header or "").split(";"):
        part = chunk.strip()
        if not part or "=" not in part:
            continue

        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()

        if not name:
            continue

        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": ".viyar.ua",
                "path": "/",
            }
        )

    return cookies


def _render_pages(cookie_header: str, items: list[dict]) -> dict:
    results: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            locale="uk-UA",
            user_agent=USER_AGENT,
        )

        cookies = _parse_cookie_header(cookie_header)
        if cookies:
            context.add_cookies(cookies)

        page = context.new_page()

        for item in items:
            external_code = item.get("external_code")
            url = item.get("source_url")

            if not external_code or not url:
                results.append(
                    {
                        "external_code": external_code,
                        "success": False,
                        "error": "Missing source URL",
                    }
                )
                continue

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                try:
                    page.wait_for_selector(".vr-product__card", timeout=8000)
                except Exception:
                    page.wait_for_timeout(500)

                html = page.content()
                body_text = page.locator("body").inner_text()
                final_url = page.url
                title = page.title()

                results.append(
                    {
                        "external_code": external_code,
                        "success": True,
                        "html": html,
                        "body_text": body_text,
                        "final_url": final_url,
                        "title": title,
                        "host": urlparse(final_url).netloc,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "external_code": external_code,
                        "success": False,
                        "error": str(exc),
                    }
                )

        context.close()
        browser.close()

    return {"success": True, "results": results}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        payload = json.loads(sys.stdin.read() or "{}")
        cookie_header = str(payload.get("cookie", "") or "")
        items = payload.get("items") or []

        if not isinstance(items, list):
            raise ValueError("items must be a list")

        result = _render_pages(cookie_header, items)
    except Exception as exc:
        result = {
            "success": False,
            "error": str(exc),
        }

    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
