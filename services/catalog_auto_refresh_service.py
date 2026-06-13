import asyncio
import logging
import os
from datetime import datetime, timedelta

from database.repositories.inventory_repository import (
    list_material_price_refresh_targets,
)
from database.repositories.service_catalog_repository import (
    list_users_needing_viyar_service_price_sync,
    sync_viyar_service_catalog,
    sync_viyar_service_prices,
)
from database.repositories.user_repository import (
    update_user_viyar_session,
)
from services.credential_cipher import decrypt_secret
from services.material_import_queue_service import enqueue_material_import_job
from services.viyar_auth_service import login_viyar_and_get_cookie


AUTO_REFRESH_INTERVAL_SECONDS = int(os.getenv("AUTO_REFRESH_INTERVAL_SECONDS", "1800"))
AUTO_REFRESH_STALE_HOURS = int(os.getenv("AUTO_REFRESH_STALE_HOURS", "24"))
AUTO_REFRESH_MATERIAL_LIMIT = int(os.getenv("AUTO_REFRESH_MATERIAL_LIMIT", "20"))
AUTO_REFRESH_USER_LIMIT = int(os.getenv("AUTO_REFRESH_USER_LIMIT", "10"))
AUTO_REFRESH_SERVICE_CATALOG_HOURS = int(os.getenv("AUTO_REFRESH_SERVICE_CATALOG_HOURS", "24"))

_auto_refresh_task = None
_last_service_catalog_sync_at = None
_auto_refresh_status = {
    "last_cycle_started_at": None,
    "last_cycle_finished_at": None,
    "last_success_at": None,
    "last_error": None,
    "material_jobs_queued": 0,
    "service_users_synced": 0,
    "service_catalog_synced": False,
}


async def _resolve_user_cookie(user_payload: dict) -> str | None:

    if user_payload.get("viyar_cookie"):
        return user_payload["viyar_cookie"]

    viyar_email = user_payload.get("viyar_email")
    viyar_password_secret = user_payload.get("viyar_password_secret")

    if not viyar_email or not viyar_password_secret:
        return None

    password = decrypt_secret(viyar_password_secret)

    if not password:
        return None

    auth_result = await login_viyar_and_get_cookie(
        email=viyar_email,
        password=password,
    )

    if auth_result.get("success") and auth_result.get("cookie"):
        update_user_viyar_session(
            user_id=user_payload["id"],
            viyar_cookie=auth_result["cookie"],
            status="connected",
            error=None,
        )
        return auth_result["cookie"]

    update_user_viyar_session(
        user_id=user_payload["id"],
        viyar_cookie=None,
        status="error",
        error=auth_result.get("error"),
    )
    return None


async def refresh_stale_material_prices() -> int:

    targets = list_material_price_refresh_targets(
        stale_hours=AUTO_REFRESH_STALE_HOURS,
        limit=AUTO_REFRESH_MATERIAL_LIMIT,
    )

    queued_count = 0

    for target in targets:
        try:
            await enqueue_material_import_job(
                article=target["article"],
                category=target["category"],
                city=target["city"],
                preferred_url=target.get("source_url"),
            )
            queued_count += 1
        except Exception as error:
            logging.warning("Auto-refresh material enqueue failed for %s: %s", target.get("article"), error)

    return queued_count


async def refresh_stale_viyar_service_prices() -> int:

    users = list_users_needing_viyar_service_price_sync(
        stale_hours=AUTO_REFRESH_STALE_HOURS,
        limit=AUTO_REFRESH_USER_LIMIT,
    )

    synced_users = 0

    for user in users:
        try:
            cookie_override = await _resolve_user_cookie(user)
            await asyncio.to_thread(
                sync_viyar_service_prices,
                user["id"],
                cookie_override,
                True,
            )
            synced_users += 1
        except Exception as error:
            logging.warning("Auto-refresh Viyar service prices failed for %s: %s", user.get("email"), error)

    return synced_users


async def refresh_viyar_service_catalog_if_due() -> bool:
    global _last_service_catalog_sync_at

    now = datetime.utcnow()

    if (
        _last_service_catalog_sync_at
        and now - _last_service_catalog_sync_at < timedelta(hours=max(1, AUTO_REFRESH_SERVICE_CATALOG_HOURS))
    ):
        return False

    try:
        await asyncio.to_thread(
            sync_viyar_service_catalog,
            True,
            None,
        )
        _last_service_catalog_sync_at = now
        return True
    except Exception as error:
        logging.warning("Auto-refresh Viyar service catalog failed: %s", error)
        return False


async def catalog_auto_refresh_loop():

    while True:
        cycle_started_at = datetime.utcnow()

        try:
            _auto_refresh_status["last_cycle_started_at"] = cycle_started_at
            _auto_refresh_status["last_error"] = None

            service_catalog_synced = await refresh_viyar_service_catalog_if_due()
            material_jobs_queued = await refresh_stale_material_prices()
            service_users_synced = await refresh_stale_viyar_service_prices()

            cycle_finished_at = datetime.utcnow()
            _auto_refresh_status["last_cycle_finished_at"] = cycle_finished_at
            _auto_refresh_status["last_success_at"] = cycle_finished_at
            _auto_refresh_status["material_jobs_queued"] = material_jobs_queued
            _auto_refresh_status["service_users_synced"] = service_users_synced
            _auto_refresh_status["service_catalog_synced"] = service_catalog_synced
        except Exception as error:
            _auto_refresh_status["last_cycle_finished_at"] = datetime.utcnow()
            _auto_refresh_status["last_error"] = str(error)
            logging.warning("Catalog auto-refresh loop failed: %s", error)

        await asyncio.sleep(max(300, AUTO_REFRESH_INTERVAL_SECONDS))


def start_catalog_auto_refresh_loop():
    global _auto_refresh_task

    if _auto_refresh_task and not _auto_refresh_task.done():
        return _auto_refresh_task

    _auto_refresh_task = asyncio.create_task(catalog_auto_refresh_loop())
    return _auto_refresh_task


def stop_catalog_auto_refresh_loop():
    global _auto_refresh_task

    if _auto_refresh_task and not _auto_refresh_task.done():
        _auto_refresh_task.cancel()

    _auto_refresh_task = None


def get_catalog_auto_refresh_status() -> dict:

    return {
        "loop_running": bool(_auto_refresh_task and not _auto_refresh_task.done()),
        "interval_seconds": AUTO_REFRESH_INTERVAL_SECONDS,
        "stale_hours": AUTO_REFRESH_STALE_HOURS,
        "service_catalog_hours": AUTO_REFRESH_SERVICE_CATALOG_HOURS,
        "last_cycle_started_at": _auto_refresh_status["last_cycle_started_at"],
        "last_cycle_finished_at": _auto_refresh_status["last_cycle_finished_at"],
        "last_success_at": _auto_refresh_status["last_success_at"],
        "last_error": _auto_refresh_status["last_error"],
        "last_service_catalog_sync_at": _last_service_catalog_sync_at,
        "material_jobs_queued": _auto_refresh_status["material_jobs_queued"],
        "service_users_synced": _auto_refresh_status["service_users_synced"],
        "service_catalog_synced": _auto_refresh_status["service_catalog_synced"],
    }
