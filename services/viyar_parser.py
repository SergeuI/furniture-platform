import logging
import asyncio

from playwright.async_api import async_playwright
import aiosqlite
from bs4 import BeautifulSoup


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


