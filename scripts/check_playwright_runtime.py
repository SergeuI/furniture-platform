from playwright.sync_api import sync_playwright


def main() -> int:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content("<title>runtime-check</title>")
            title = page.title()
            browser.close()
    except Exception as error:
        message = " ".join(str(error).split())
        print("Playwright Chromium: FAILED")
        if "libatk-1.0.so.0" in message or "error while loading shared libraries" in message:
            print("Missing Linux runtime dependencies.")
            print("Run: sudo ./venv/bin/playwright install-deps chromium")
        elif "Executable doesn't exist" in message:
            print("Chromium is not installed.")
            print("Run: ./venv/bin/playwright install chromium")
        else:
            print(message[:800])
        return 1

    if title != "runtime-check":
        print("Playwright Chromium: FAILED (unexpected page result)")
        return 1

    print("Playwright Chromium: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
