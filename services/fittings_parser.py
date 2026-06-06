import logging
import asyncio

from playwright.async_api import async_playwright
import aiosqlite

from bs4 import BeautifulSoup

from services.fittings_map import (
    FITTINGS_MAP
)

from services.fittings_repository import (
    save_fitting
)


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

DB_NAME = "furniture_platform.db"


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
# EXTRACT HTML
# =====================================================

def extract(html):

    soup = BeautifulSoup(

        html,
        "html.parser"
    )

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

    price = soup.select_one(
        'span[id*="_price"]'
    )

    price = (
        price.text.strip()
        if price
        else None
    )

    return name, price


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

            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64)"
            )
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

        # ==========================================
        # FITTINGS
        # ==========================================

        for code, item in FITTINGS_MAP.items():

            article = item["article"]

            print(
                f"🔩 {city} | "
                f"{code} | "
                f"{article}"
            )

            try:

                url = (
                    f"https://www.viyar.ua/ua/search/"
                    f"?q={article}"
                )

                html = await fetch_with_retry(
                    page,
                    url
                )

                if not html:

                    print(
                        f"❌ FULL FAIL {article}"
                    )

                    continue

                try:

                    await page.wait_for_selector(
                        ".product-item__name",
                        timeout=5000
                    )

                except:

                    print(
                        f"➡️ Прямий товар "
                        f"{article}"
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
                            f"❌ LINK FAIL "
                            f"{article}"
                        )

                        continue

                    full_url = (
                        "https://www.viyar.ua"
                        + link
                    )

                    await page.goto(
                        full_url,
                        timeout=15000
                    )

                await page.wait_for_load_state(
                    "domcontentloaded"
                )

                if not await page.locator(
                    "h1"
                ).count():

                    print(
                        f"❌ НЕ товар "
                        f"{article}"
                    )

                    continue

                html = await page.content()

                name, price = extract(html)

                if not price:

                    print(
                        f"❌ PRICE FAIL "
                        f"{article}"
                    )

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

                    print(
                        f"❌ PRICE CONVERT "
                        f"{article}"
                    )

                    continue

                await save_fitting(

                    city=city,

                    code=code,

                    article=article,

                    name=name,

                    price=price
                )

                print(
                    f"✅ FITTING SAVED | "
                    f"{name} | "
                    f"{price}"
                )

                await asyncio.sleep(1)

            except Exception as e:

                print(
                    f"❌ FITTING ERROR "
                    f"{article}: {e}"
                )

                continue

    except Exception as e:

        print(
            f"❌ CITY ERROR "
            f"{city}: {e}"
        )

    finally:

        if context:

            try:
                await context.close()

            except:
                pass


# =====================================================
# MAIN PARSER
# =====================================================

async def run_fittings_parser():

    async with async_playwright() as p:

        browser = await p.chromium.launch(

            headless=True
        )

        for city, cookie in CITY_COOKIES.items():

            print(
                f"\n🏙 START CITY: {city}"
            )

            await parse_city(

                browser,
                city,
                cookie
            )

        await browser.close()


if __name__ == "__main__":

    asyncio.run(
        run_fittings_parser()
    )
