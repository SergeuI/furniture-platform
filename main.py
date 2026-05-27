from os import getenv
import asyncio
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from handlers.router import router, seed_materials
from services.scheduler import start_scheduler
from services.mt_kits_parser import init_kits_db, seed_kits
from services.mt_parser import init_mt_db, run_mt_parser, get_mt_product_from_db
from services.database import init_db
from services.production_database_engine import (
    init_production_db
)
from services.production_auth_engine import (
    init_auth_tables
)
load_dotenv()
BOT_TOKEN = getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    await init_kits_db()
    await seed_kits()
    await init_db()
    init_production_db()
    init_auth_tables()
    await seed_materials()
    await init_mt_db()
    logging.info("DATABASE INIT OK")
    # ✅ перевірка MT
    test = await get_mt_product_from_db("TDM550F-40T30-st")

    if not test:
        logging.info("MT БД порожня — запускаємо парсер...")
        await run_mt_parser()
    else:
        logging.info("MT БД вже має дані")

    start_scheduler()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())