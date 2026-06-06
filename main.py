from os import getenv
import asyncio
import logging

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from handlers.router import (
    router,
    seed_materials,
)
from services.database import init_db
from services.mt_kits_parser import (
    init_kits_db,
    seed_kits,
)
from services.mt_parser import (
    get_mt_product_from_db,
    init_mt_db,
    run_mt_parser,
)
from services.production_auth_engine import (
    init_auth_tables,
)
from services.production_database_engine import (
    init_production_db,
)
from services.scheduler import start_scheduler

load_dotenv()

BOT_TOKEN = getenv("BOT_TOKEN")
RUN_MT_PARSER_ON_START = getenv(
    "RUN_MT_PARSER_ON_START",
    "0"
) == "1"

logging.basicConfig(level=logging.INFO)


async def main():

    bot = Bot(
        token=BOT_TOKEN
    )

    dp = Dispatcher()
    dp.include_router(router)

    logging.info("Bot startup: init kits db")
    await init_kits_db()
    await seed_kits()

    logging.info("Bot startup: init unified sqlite db")
    await init_db()
    init_production_db()
    init_auth_tables()
    await seed_materials()
    await init_mt_db()
    logging.info("Database init complete")

    test = await get_mt_product_from_db(
        "TDM550F-40T30-st"
    )

    if not test:
        if RUN_MT_PARSER_ON_START:
            logging.info(
                "MT DB empty - running parser on startup"
            )
            await run_mt_parser()
        else:
            logging.info(
                "MT DB empty - skipping parser on startup to keep bot responsive"
            )
    else:
        logging.info(
            "MT DB already has data"
        )

    start_scheduler()
    logging.info(
        "Bot startup complete, polling started"
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
