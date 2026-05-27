# services/mt_kits_parser.py

from services.mt_parser import get_mt_product_from_db # ✅ Правильний імпорт з БД
import aiosqlite

DB_NAME = "mebli_calculator.db"

# 🔹 ОПИС КОМПЛЕКТІВ
KITS = {
    # 🔹 MOVENTO TIP-ON
    "movento_270_tipon": {"name": "Movento 270 TIP-ON", "items": [{"article": "MOV270M40", "qty": 1}]},
    "movento_300_tipon": {"name": "Movento 300 TIP-ON", "items": [{"article": "MOV300M40", "qty": 1}]},
    "movento_350_tipon": {"name": "Movento 350 TIP-ON", "items": [{"article": "MOV350M40", "qty": 1}]},
    "movento_400_tipon": {"name": "Movento 400 TIP-ON", "items": [{"article": "MOV400M40", "qty": 1}]},
    "movento_450_tipon": {"name": "Movento 450 TIP-ON", "items": [{"article": "MOV450M40", "qty": 1}]},
    "movento_500_tipon": {"name": "Movento 500 TIP-ON", "items": [{"article": "MOV500M40", "qty": 1}]},
    "movento_550_tipon": {"name": "Movento 550 TIP-ON", "items": [{"article": "MOV550M40", "qty": 1}]},
    "movento_600_tipon": {"name": "Movento 600 TIP-ON", "items": [{"article": "MOV600M40", "qty": 1}]},

    # 🔹 MOVENTO BLUMOTION
    "movento_250": {"name": "Movento 250 BLUMOTION", "items": [{"article": "MOV250B40", "qty": 1}]},
    "movento_300": {"name": "Movento 300 BLUMOTION", "items": [{"article": "MOV300B40", "qty": 1}]},
    "movento_350": {"name": "Movento 350 BLUMOTION", "items": [{"article": "MOV350B40", "qty": 1}]},
    "movento_400": {"name": "Movento 400 BLUMOTION", "items": [{"article": "MOV400B40", "qty": 1}]},
    "movento_450": {"name": "Movento 450 BLUMOTION", "items": [{"article": "MOV450B40", "qty": 1}]},
    "movento_500": {"name": "Movento 500 BLUMOTION", "items": [{"article": "MOV500B40", "qty": 1}]},
    "movento_550": {"name": "Movento 550 BLUMOTION", "items": [{"article": "MOV550B40", "qty": 1}]},
    "movento_600": {"name": "Movento 600 BLUMOTION", "items": [{"article": "MOV600B40", "qty": 1}]},

    # 🔹 TANDEM TIP-ON
    "tandem_270_tipon": {"name": "Tandem 270 TIP-ON", "items": [{"article": "TDM550F-27T30-st", "qty": 1}]},
    "tandem_300_tipon": {"name": "Tandem 300 TIP-ON", "items": [{"article": "TDM550F-30T30-st", "qty": 1}]},
    "tandem_350_tipon": {"name": "Tandem 350 TIP-ON", "items": [{"article": "TDM550F-35T30-st", "qty": 1}]},
    "tandem_400_tipon": {"name": "Tandem 400 TIP-ON", "items": [{"article": "TDM550F-40T30-st", "qty": 1}]},
    "tandem_450_tipon": {"name": "Tandem 450 TIP-ON", "items": [{"article": "TDM550F-45T30-st", "qty": 1}]},
    "tandem_500_tipon": {"name": "Tandem 500 TIP-ON", "items": [{"article": "TDM550F-50T30-st", "qty": 1}]},
    "tandem_550_tipon": {"name": "Tandem 550 TIP-ON", "items": [{"article": "TDM550F-55T30-st", "qty": 1}]},
    "tandem_600_tipon": {"name": "Tandem 600 TIP-ON", "items": [{"article": "TDM550F-60T30-st", "qty": 1}]},

    # 🔹 TANDEM BLUMOTION
    "tandem_270_softclose": {"name": "Tandem 270 BLUMOTION", "items": [{"article": "TDM550F-27B30-st", "qty": 1}]},
    "tandem_300_softclose": {"name": "Tandem 300 BLUMOTION", "items": [{"article": "TDM550F-30B30-st", "qty": 1}]},
    "tandem_350_softclose": {"name": "Tandem 350 BLUMOTION", "items": [{"article": "TDM550F-35B30-st", "qty": 1}]},
    "tandem_400_softclose": {"name": "Tandem 400 BLUMOTION", "items": [{"article": "TDM550F-40B30-st", "qty": 1}]},
    "tandem_450_softclose": {"name": "Tandem 450 BLUMOTION", "items": [{"article": "TDM550F-45B30-st", "qty": 1}]},
    "tandem_500_softclose": {"name": "Tandem 500 BLUMOTION", "items": [{"article": "TDM550F-50B30-st", "qty": 1}]},
    "tandem_550_softclose": {"name": "Tandem 550 BLUMOTION", "items": [{"article": "TDM550F-55B30-st", "qty": 1}]},
    "tandem_600_softclose": {"name": "Tandem 600 BLUMOTION", "items": [{"article": "TDM600F-60B30-st", "qty": 1}]},
}


# 🔹 створення таблиць
async def init_kits_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                name TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS kit_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kit_code TEXT,
                article TEXT,
                qty INTEGER
            )
        """)

        await db.commit()


# 🔹 запис комплектів
async def seed_kits():
    async with aiosqlite.connect(DB_NAME) as db:
        for code, kit in KITS.items():
            await db.execute("""
                INSERT OR IGNORE INTO kits (code, name)
                VALUES (?, ?)
            """, (code, kit["name"]))

            for item in kit["items"]:
                await db.execute("""
                    INSERT OR REPLACE INTO kit_items (kit_code, article, qty)
                    VALUES (?, ?, ?)
                """, (code, item["article"], item["qty"]))

        await db.commit()


# 🔹 отримати комплект з цінами — ТЕПЕР З БД, МИТТЄВО!
async def get_kit_price(kit_code: str, city: str = None):

    print("========== GET KIT PRICE ==========")
    print("KIT CODE:", kit_code)
    print("CITY:", city)

    kit = KITS.get(kit_code)

    print("KIT:", kit)

    if not kit:

        print("KIT NOT FOUND")

        return None

    item = kit["items"][0]

    print("ITEM:", item)

    try:

        product = await get_mt_product_from_db(
            item["article"]
        )

        print("PRODUCT:", product)

    except Exception as e:

        import traceback

        print("GET MT PRODUCT ERROR:")
        print(traceback.format_exc())

        return None

    if not product:

        print("PRODUCT NOT FOUND")

        return None

    result = {

        "name": product["name"],

        "price": product["price"],

        "image": product.get("image")
    }

    print("FINAL RESULT:", result)

    return result