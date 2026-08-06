from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database.repositories.service_catalog_repository import (
    sync_viyar_service_catalog,
)
from services.mt_parser import run_mt_parser
from services.run_parser import main as run_viyar_parser
from services.catalog_auto_refresh_service import (
    refresh_stale_viyar_service_prices,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Europe/Kyiv"
DEFAULT_MISFIRE_GRACE_SECONDS = 300

_scheduler: AsyncIOScheduler | None = None
_mt_parser_lock = asyncio.Lock()


def _parse_env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s=%r, using default %s", name, raw, default)
        return default


def _parse_env_days(name: str, default: str) -> str:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    parts = [
        part.strip().lower()
        for part in raw.split(",")
        if part.strip()
    ]
    if not parts:
        return default
    return ",".join(parts)


def _get_timezone() -> ZoneInfo:
    tz_name = os.getenv("PARSER_TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(tz_name)
    except Exception:
        logger.warning(
            "Invalid parser timezone %r, falling back to %s",
            tz_name,
            DEFAULT_TIMEZONE,
        )
        return ZoneInfo(DEFAULT_TIMEZONE)


def _build_cron_trigger(*, days: str, hour: int, minute: int, timezone: ZoneInfo) -> CronTrigger:
    return CronTrigger(
        day_of_week=days,
        hour=hour,
        minute=minute,
        timezone=timezone,
    )


def _short_error(error: Exception) -> str:
    return f"{error.__class__.__name__}: {error}"


def _summarize_result(result: Any) -> Any:
    if isinstance(result, tuple):
        return {
            "success_count": result[0] if len(result) > 0 else None,
            "failed_count": result[1] if len(result) > 1 else None,
        }

    if isinstance(result, dict):
        keys = (
            "imported_count",
            "service_count",
            "priced_count",
            "skipped_count",
            "deactivated_suspicious_count",
            "catalog_imported_count",
            "catalog_service_count",
            "catalog_deactivated_suspicious_count",
            "price_users_synced",
        )
        summary = {
            key: result[key]
            for key in keys
            if key in result
        }
        if summary:
            return summary
        return {
            "keys": sorted(result.keys()),
        }

    if result is None:
        return None

    return {
        "result_type": type(result).__name__,
    }


async def _run_logged_job(
    *,
    job_id: str,
    source: str,
    action: str,
    runner: Callable[[], Awaitable[Any]],
) -> Any:
    started_at = datetime.now(tz=_get_timezone())
    logger.info(
        "scheduler job started id=%s source=%s action=%s started_at=%s",
        job_id,
        source,
        action,
        started_at.isoformat(),
    )

    try:
        result = await runner()
    except Exception as error:
        logger.warning(
            "scheduler job failed id=%s source=%s action=%s error=%s",
            job_id,
            source,
            action,
            _short_error(error),
        )
        logger.debug("scheduler job traceback id=%s", job_id, exc_info=True)
        return None

    finished_at = datetime.now(tz=_get_timezone())
    duration_seconds = round((finished_at - started_at).total_seconds(), 3)
    summary = _summarize_result(result)

    logger.info(
        "scheduler job finished id=%s source=%s action=%s finished_at=%s duration_seconds=%s result=%s",
        job_id,
        source,
        action,
        finished_at.isoformat(),
        duration_seconds,
        summary,
    )
    return result


async def run_viyar_parser_job(source: str = "scheduler") -> Any:
    return await _run_logged_job(
        job_id="viyar-parser",
        source=source,
        action="parse-viyar-catalog",
        runner=run_viyar_parser,
    )


async def run_mt_parser_job(source: str = "scheduler") -> Any:
    async with _mt_parser_lock:
        return await _run_logged_job(
            job_id="mt-parser",
            source=source,
            action="parse-mt-catalog",
            runner=run_mt_parser,
        )


async def run_viyar_service_sync_job(source: str = "scheduler") -> Any:
    async def _runner() -> dict[str, Any]:
        catalog_result = await asyncio.to_thread(
            sync_viyar_service_catalog,
            True,
            None,
            False,
        )
        price_users_synced = await refresh_stale_viyar_service_prices()
        return {
            "catalog_imported_count": catalog_result.get("imported_count"),
            "catalog_service_count": catalog_result.get("service_count"),
            "catalog_deactivated_suspicious_count": catalog_result.get("deactivated_suspicious_count"),
            "price_users_synced": price_users_synced,
        }

    return await _run_logged_job(
        job_id="viyar-service-sync",
        source=source,
        action="sync-viyar-service-catalog-and-prices",
        runner=_runner,
    )


def _register_cron_job(
    scheduler: AsyncIOScheduler,
    *,
    job_id: str,
    enabled: bool,
    source: str,
    action_name: str,
    runner: Callable[[], Awaitable[Any]],
    days_env: str,
    default_days: str,
    hour_env: str,
    default_hour: int,
    minute_env: str,
    default_minute: int,
) -> None:
    if not enabled:
        logger.info("Scheduler job disabled id=%s source=%s action=%s", job_id, source, action_name)
        return

    timezone = _get_timezone()
    days = _parse_env_days(days_env, default_days)
    hour = _parse_env_int(hour_env, default_hour)
    minute = _parse_env_int(minute_env, default_minute)
    trigger = _build_cron_trigger(
        days=days,
        hour=hour,
        minute=minute,
        timezone=timezone,
    )

    scheduler.add_job(
        runner,
        id=job_id,
        name=job_id,
        trigger=trigger,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=DEFAULT_MISFIRE_GRACE_SECONDS,
    )

    logger.info(
        "Scheduler job registered id=%s source=%s action=%s timezone=%s days=%s time=%02d:%02d",
        job_id,
        source,
        action_name,
        timezone.key,
        days,
        hour,
        minute,
    )


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler

    if _scheduler is not None and getattr(_scheduler, "running", False):
        logger.info("Scheduler already running")
        return _scheduler

    timezone = _get_timezone()
    scheduler = AsyncIOScheduler(
        timezone=timezone,
    )

    _register_cron_job(
        scheduler,
        job_id="viyar-parser",
        enabled=_parse_env_bool("VIYAR_PARSER_ENABLED", True),
        source="scheduler",
        action_name="parse-viyar-catalog",
        runner=run_viyar_parser_job,
        days_env="VIYAR_PARSER_DAYS",
        default_days="tue,fri",
        hour_env="VIYAR_PARSER_HOUR",
        default_hour=3,
        minute_env="VIYAR_PARSER_MINUTE",
        default_minute=10,
    )

    _register_cron_job(
        scheduler,
        job_id="mt-parser",
        enabled=_parse_env_bool("MT_PARSER_ENABLED", True),
        source="scheduler",
        action_name="parse-mt-catalog",
        runner=run_mt_parser_job,
        days_env="MT_PARSER_DAYS",
        default_days="wed",
        hour_env="MT_PARSER_HOUR",
        default_hour=3,
        minute_env="MT_PARSER_MINUTE",
        default_minute=40,
    )

    _register_cron_job(
        scheduler,
        job_id="viyar-service-sync",
        enabled=_parse_env_bool("VIYAR_SERVICE_SYNC_ENABLED", True),
        source="scheduler",
        action_name="sync-viyar-service-catalog-and-prices",
        runner=run_viyar_service_sync_job,
        days_env="VIYAR_SERVICE_SYNC_DAYS",
        default_days="mon-sun",
        hour_env="VIYAR_SERVICE_SYNC_HOUR",
        default_hour=4,
        minute_env="VIYAR_SERVICE_SYNC_MINUTE",
        default_minute=10,
    )

    scheduler.start()
    _scheduler = scheduler

    logger.info(
        "Scheduler started timezone=%s job_defaults=%s",
        timezone.key,
        {
            "max_instances": 1,
            "coalesce": True,
            "misfire_grace_time": DEFAULT_MISFIRE_GRACE_SECONDS,
        },
    )

    return scheduler
