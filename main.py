from os import getenv
import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
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


def configure_file_logging() -> None:
    log_path = Path(__file__).resolve().parent / "product_center_app.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s %(message)s"
        )
    )
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)


async def main():
    configure_file_logging()

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
    logging.info("BOT_STATUS: online")
    await bot.delete_webhook(drop_pending_updates=True)
    while True:
        try:
            await dp.start_polling(bot)
            break
        except TelegramUnauthorizedError:
            logging.error(
                "BOT_STATUS: unauthorized"
            )
            logging.error(
                "BOT_TOKEN is invalid or revoked. Check the .env file and replace the token."
            )
            return
        except TelegramNetworkError as exc:
            logging.error("BOT_STATUS: reconnecting")
            logging.exception(
                "Bot polling failed because Telegram is unreachable; retrying in 15 seconds"
            )
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Bot polling failed unexpectedly")
            raise


if __name__ == "__main__":
    asyncio.run(main())
