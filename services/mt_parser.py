# services/mt_parser.py
"""
Парсер MT.ua — збирає ціни всіх товарів у БД.
Запускається раз в тиждень через scheduler.
"""

import asyncio
import aiosqlite
import logging
import os
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

DB_NAME = "mebli_calculator.db"
BASE_URL = "https://mt.ua"

# Список артикулів для парсингу (з KITS + додаткові)
MT_ARTICLES = [
    # Movento TIP-ON BLUMOTION
    "MOV270M40", "MOV300M40", "MOV350M40",
    "MOV400M40", "MOV450M40", "MOV500M40",
    "MOV550M40", "MOV600M40",
    # Movento BLUMOTION
    "MOV250B40", "MOV300B40", "MOV350B40",
    "MOV400B40", "MOV450B40", "MOV500B40",
    "MOV550B40", "MOV600B40",
    # Tandem TIP-ON
    "TDM550F-27T30-st", "TDM550F-30T30-st", "TDM550F-35T30-st",
    "TDM550F-40T30-st", "TDM550F-45T30-st", "TDM550F-50T30-st",
    "TDM550F-55T30-st", "TDM550F-60T30-st",
    # Tandem BLUMOTION
    "TDM550F-27B30-st", "TDM550F-30B30-st", "TDM550F-35B30-st",
    "TDM550F-40B30-st", "TDM550F-45B30-st", "TDM550F-50B30-st",
    "TDM550F-55B30-st", "TDM550F-60B30-st",
]


async def init_mt_db():
    """Створення таблиці для MT товарів"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mt_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article TEXT UNIQUE,
                name TEXT,
                price REAL,
                image TEXT,
                url TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def save_mt_product(article, name, price, image, url):
    """Збереження товару в БД"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO mt_products (article, name, price, image, url)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(article) DO UPDATE SET
                name=excluded.name,
                price=excluded.price,
                image=excluded.image,
                url=excluded.url,
                updated_at=CURRENT_TIMESTAMP
        """, (article, name, price, image, url))
        await db.commit()


async def get_mt_product_from_db(article: str):
    """Отримання товару з БД (миттєво!)"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT name, price, image FROM mt_products WHERE article = ?",
            (article,)
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return {

            "name": row[0],

            "price": row[1],

            "image": row[2],

            "text": f"{row[0]}\n💰 {row[1]} грн",

            "url": ""

        }


async def parse_mt_page(page, article):
    """Парсинг одного товару на MT.ua"""
    try:
        # 🔥 СПРОБА 1: Прямий пошук через URL
        search_url = f"https://mt.ua/ua/search/?q={article}"
        logging.info(f"MT: Перехід на {search_url}")
        
        await page.goto(search_url, timeout=60000)
        await asyncio.sleep(6)
        await page.wait_for_load_state("domcontentloaded")

        html = await page.content()
        print(html[:1000])
        soup = BeautifulSoup(html, "html.parser")

        # Шукаємо посилання на товар в результатах пошуку
        # =====================================================
        # ПОШУК ПОСИЛАНЬ НА ТОВАР
        # =====================================================

        product_links = soup.select(

            "a.product-card__img, "
            "a.product-card__title, "
            ".product-card a, "
            ".catalog-item a, "
            ".product-item a"

        )

        print("FOUND LINKS:", len(product_links))

        if not product_links:

            logging.warning(
                f"MT: Не знайдено результати для {article}"
            )

            return None

        # Беремо перше посилання
        link = product_links[0].get("href")
        if not link:
            logging.warning(f"MT: Немає посилання для {article}")
            return None

        full_url = link if link.startswith("http") else f"https://mt.ua{link}"
        logging.info(f"MT: Перехід на товар {full_url}")

        await page.goto(full_url, timeout=60000)
        await asyncio.sleep(5)
        await page.wait_for_load_state("domcontentloaded")

        # Отримуємо HTML сторінки товару
        html = await page.content()
        print(html[:1000])
        soup = BeautifulSoup(html, "html.parser")

        # 🔥 ПАРСИНГ ЦІНИ — перевіряємо багато варіантів
        price = None
        price_text = None

        # Варіант 1: Селектори ціни
        price_selectors = [
            "div.product-page-price",
            ".product-price",
            "[data-price]",
            ".price-current",
            ".product__price",
            "span.price",
            ".current-price",
            ".price",
            ".cost",
            ".product-cost"
        ]

        for selector in price_selectors:
            elem = soup.select_one(selector)
            if elem:
                price_text = elem.get_text(strip=True)
                if price_text:
                    break

        # Варіант 2: Шукаємо в JSON-LD або meta
        if not price_text:
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, dict) and "offers" in data:
                        price_text = str(data["offers"].get("price", ""))
                        break
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "offers" in item:
                                price_text = str(item["offers"].get("price", ""))
                                break
                except:
                    pass

        if not price_text:
            logging.warning(f"MT: Не знайдено ціну для {article}")
            return None

        # Очищаємо ціну
        price_clean = re.sub(r'[^\d.,]', '', price_text).replace(',', '.')
        try:
            price = float(price_clean)
        except ValueError:
            logging.warning(f"MT: Не вдалося розпарсити ціну '{price_text}' для {article}")
            return None

        # 🔥 ПАРСИНГ НАЗВИ
        name = None
        name_selectors = ["h1", ".product-title", ".product-name", "[data-name]", ".page-title"]
        
        for selector in name_selectors:
            elem = soup.select_one(selector)
            if elem:
                name = elem.get_text(strip=True)
                if name:
                    break

        if not name:
            name = article

        # 🔥 ПАРСИНГ КАРТИНКИ
        image = None
        image_selectors = [
            "img[src*='product']",
            ".product-gallery img",
            ".product-image img",
            "img[data-src]",
            ".main-image img"
        ]

        for selector in image_selectors:
            elem = soup.select_one(selector)
            if elem:
                img_src = elem.get("src") or elem.get("data-src")
                if img_src:
                    image = img_src if img_src.startswith("http") else f"https://mt.ua{img_src}"
                    break

        logging.info(f"✅ MT PARSED {article}: {name} | {price} грн")

        return {
            "article": article,
            "name": name.strip(),
            "price": price,
            "image": image,
            "url": full_url
        }

    except Exception as e:
        logging.error(f"MT ERROR parsing {article}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return None


async def run_mt_parser():
    """Головна функція парсингу MT"""
    logging.info("🚀 START MT PARSER")

    await init_mt_db()

    # Правильний шлях до файлу авторизації
    auth_file = os.path.join(os.path.dirname(__file__), "mt_auth.json")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context_options = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        if os.path.exists(auth_file):
            context_options["storage_state"] = auth_file
            logging.info(f"MT: Використовуємо авторизацію з {auth_file}")
        else:
            logging.warning(f"MT: Файл авторизації не знайдено: {auth_file}")

        context = await browser.new_context(**context_options)
        page = await context.new_page()

        # Таймаути
        page.set_default_timeout(60000)
        page.set_default_navigation_timeout(60000)

        success = 0
        failed = 0

        for article in MT_ARTICLES:
            logging.info(f"👉 MT | {article}")
            data = await parse_mt_page(page, article)

            if data:
                await save_mt_product(
                    data["article"],
                    data["name"],
                    data["price"],
                    data["image"],
                    data["url"]
                )
                logging.info(f"✅ MT SAVED {article} | {data['price']} грн")
                success += 1
            else:
                logging.warning(f"❌ MT FAIL {article}")
                failed += 1

            await asyncio.sleep(3)

        await browser.close()

    logging.info(f"✅ MT DONE: {success} saved, {failed} failed")
    return success, failed


# Сумісність зі старим кодом — тепер бере з БД!
async def get_mt_product(article, city=None):
    """Сумісність зі старим кодом — тепер бере з БД миттєво"""
    return await get_mt_product_from_db(article)

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO
    )

    asyncio.run(
        run_mt_parser()
    )