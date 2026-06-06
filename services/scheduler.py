import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.run_parser import main as run_viyar_parser
from services.mt_parser import run_mt_parser


def start_scheduler():

    scheduler = AsyncIOScheduler()

    # =====================================
    # VIYAR PARSER
    # =====================================

    scheduler.add_job(
        run_viyar_parser,
        trigger="interval",
        hours=24,
        next_run_time=None
    )

    # =====================================
    # MT PARSER
    # =====================================

    scheduler.add_job(
        run_mt_parser,
        trigger="interval",
        hours=24,
        next_run_time=None
    )

    scheduler.start()

    logging.info(
        "Scheduler started"
    )
