import json
import sys
import traceback

from playwright.sync_api import sync_playwright


VIYAR_AUTH_URL = (
    "https://auth.viyar.tech/auth/realms/ViyarAuth/protocol/openid-connect/auth"
    "?response_type=code"
    "&redirect_uri=https://viyar.ua/ua/catalog/uslugi/"
    "&client_id=viyarsites"
)

VIYAR_TARGET_URL = "https://viyar.ua/ua/catalog/uslugi/"


def _normalize_viyar_error(raw_error) -> str:
    text = str(raw_error or "").strip()

    if not text:
        if isinstance(raw_error, BaseException):
            details = "".join(
                traceback.format_exception_only(raw_error.__class__, raw_error)
            ).strip()
            if details:
                return details
            return f"Unhandled Viyar authorization error: {raw_error.__class__.__name__}"
        return (
            "Viyar authorization failed without a detailed error. "
            "Please verify your Viyar credentials and site availability."
        )

    return text


def _compose_error_with_context(
    message: str,
    *,
    url: str | None = None,
    title: str | None = None,
    excerpt: str | None = None,
) -> str:
    parts = [message.strip()]

    if title:
        parts.append(f"Page: {title.strip()}")

    if url:
        parts.append(f"URL: {url.strip()}")

    if excerpt:
        parts.append(f"Snippet: {excerpt.strip()}")

    return " | ".join(part for part in parts if part)


def _build_cookie_header(cookies: list[dict]) -> str:
    filtered = []

    for cookie in cookies:
        domain = str(cookie.get("domain", ""))
        if "viyar.ua" not in domain:
            continue
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        filtered.append(f"{name}={value}")

    return "; ".join(filtered)


def _first_available(page, selectors: list[str]):
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count():
            return locator.first
    return None


def _extract_feedback_text(page) -> str | None:
    feedback = _first_available(
        page,
        [
            "#input-error",
            ".kc-feedback-text",
            ".alert-error",
            ".error",
            "[role='alert']",
            ".invalid-feedback",
        ],
    )

    if not feedback:
        return None

    try:
        text = feedback.inner_text().strip()
    except Exception:
        return None

    return text or None


def _extract_page_excerpt(page) -> str | None:
    try:
        text = page.locator("body").inner_text()
    except Exception:
        return None

    normalized = " ".join(str(text or "").split())
    if not normalized:
        return None

    return normalized[:280]


def _login_viyar_and_get_cookie_sync(email: str, password: str) -> dict:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                locale="uk-UA",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/137.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            page.goto(
                VIYAR_AUTH_URL,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            username_field = _first_available(
                page,
                [
                    "#username",
                    "input[name='username']",
                    "input[name='email']",
                    "input[type='email']",
                    "input[type='text']",
                ],
            )
            password_field = _first_available(
                page,
                [
                    "#password",
                    "input[name='password']",
                    "input[type='password']",
                ],
            )

            if not username_field or not password_field:
                result = {
                    "success": False,
                    "error": "Viyar login form was not detected",
                }
                context.close()
                browser.close()
                return result

            username_field.fill(email)
            password_field.fill(password)

            submit_button = _first_available(
                page,
                [
                    "#kc-login",
                    "button[type='submit']",
                    "input[type='submit']",
                ],
            )

            if submit_button:
                submit_button.click()
            else:
                password_field.press("Enter")

            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                page.wait_for_timeout(2000)

            auth_url = page.url
            try:
                auth_title = page.title()
            except Exception:
                auth_title = None
            auth_feedback = _extract_feedback_text(page)
            auth_excerpt = _extract_page_excerpt(page)

            if auth_feedback:
                result = {
                    "success": False,
                    "error": _normalize_viyar_error(
                        _compose_error_with_context(
                            auth_feedback,
                            url=auth_url,
                            title=auth_title,
                            excerpt=auth_excerpt,
                        )
                    ),
                }
                context.close()
                browser.close()
                return result

            if "auth.viyar.tech" in auth_url:
                result = {
                    "success": False,
                    "error": _normalize_viyar_error(
                        _compose_error_with_context(
                            "Viyar login did not leave the authorization page",
                            url=auth_url,
                            title=auth_title,
                            excerpt=auth_excerpt,
                        )
                    ),
                }
                context.close()
                browser.close()
                return result

            page.goto(
                VIYAR_TARGET_URL,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            html = page.content()
            url = page.url
            try:
                title = page.title()
            except Exception:
                title = None
            excerpt = _extract_page_excerpt(page)

            if "login_required" in url or "Увійти в особистий кабінет" in html:
                error_text = _extract_feedback_text(page)
                result = {
                    "success": False,
                    "error": _normalize_viyar_error(
                        _compose_error_with_context(
                            error_text or "Viyar authorization failed",
                            url=url,
                            title=title,
                            excerpt=excerpt,
                        )
                    ),
                }
                context.close()
                browser.close()
                return result

            cookies = context.cookies(
                [
                    "https://viyar.ua",
                    "https://www.viyar.ua",
                ]
            )
            cookie_header = _build_cookie_header(cookies)

            if not cookie_header:
                result = {
                    "success": False,
                    "error": _normalize_viyar_error(
                        _compose_error_with_context(
                            "Viyar session cookies were not created",
                            url=url,
                            title=title,
                            excerpt=excerpt,
                        )
                    ),
                }
                context.close()
                browser.close()
                return result

            result = {
                "success": True,
                "cookie": cookie_header,
            }
            context.close()
            browser.close()
            return result

    except Exception as exc:
        return {
            "success": False,
            "error": _normalize_viyar_error(exc),
        }


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        email = str(payload.get("email", "")).strip()
        password = str(payload.get("password", ""))

        if not email or not password:
            result = {
                "success": False,
                "error": "Email and password are required for Viyar authorization",
            }
        else:
            result = _login_viyar_and_get_cookie_sync(email, password)
    except Exception as exc:
        result = {
            "success": False,
            "error": _normalize_viyar_error(exc),
        }

    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
