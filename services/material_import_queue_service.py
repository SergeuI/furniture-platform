import asyncio

from database.repositories.audit_log_repository import create_audit_log
from database.repositories.inventory_repository import (
    get_material_by_article,
    list_materials,
    upsert_material,
    upsert_material_price,
    update_material_image_cache,
)
from database.repositories.material_import_job_repository import (
    create_material_import_job,
    get_active_material_import_job,
    get_material_import_job,
    list_due_material_import_jobs,
    mark_material_import_job_retry,
    mark_material_import_job_running,
    mark_material_import_job_success,
)
from database.repositories.user_repository import (
    get_user_by_id,
    update_user_viyar_session,
)
from services.credential_cipher import decrypt_secret
from services.material_catalog_service import (
    fetch_material_by_source_live_traced,
    prefetch_material_image_cache,
)
from services.viyar_auth_service import login_viyar_and_get_cookie


_queue_loop_task = None
_queue_lock = asyncio.Lock()


async def _resolve_viyar_cookie_for_job(job: dict) -> str | None:

    owner_user_id = job.get("owner_user_id")

    if not owner_user_id:
        return None

    user = get_user_by_id(owner_user_id)

    if not user:
        return None

    if getattr(user, "viyar_cookie", None):
        return user.viyar_cookie

    viyar_email = getattr(user, "viyar_email", None)
    viyar_password_secret = getattr(user, "viyar_password_secret", None)

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
            user_id=owner_user_id,
            viyar_cookie=auth_result["cookie"],
            status="connected",
            error=None,
        )
        return auth_result["cookie"]

    update_user_viyar_session(
        user_id=owner_user_id,
        viyar_cookie=None,
        status="error",
        error=auth_result.get("error"),
    )
    return None


async def enqueue_material_import_job(
    *,
    article: str,
    category: str,
    city: str,
    owner_user_id: str | None = None,
    preferred_url: str | None = None,
) -> dict:

    active_job = get_active_material_import_job(article=article, city=city)

    if active_job:
        return active_job

    job = create_material_import_job(
        article=article,
        category=category,
        city=city,
        owner_user_id=owner_user_id,
        preferred_url=preferred_url,
    )

    asyncio.create_task(process_material_import_job(int(job["id"])))
    return job


async def process_material_import_job(job_id: int, cookie_override: str | None = None) -> dict | None:

    async with _queue_lock:
        running_job = mark_material_import_job_running(job_id)

        if not running_job:
            return None

        try:
            effective_cookie = cookie_override or await _resolve_viyar_cookie_for_job(running_job)
            material, debug_payload = await fetch_material_by_source_live_traced(
                running_job["article"],
                city=running_job["city"],
                cookie_override=effective_cookie,
                preferred_url=running_job.get("preferred_url") or (get_material_by_article(running_job["article"]) or {}).get("source_url"),
            )

            upsert_material(
                article=material["article"],
                name=material["name"],
                category=running_job["category"],
                image=material.get("image"),
                source_url=material.get("source_url"),
            )
            upsert_material_price(
                article=material["article"],
                city=running_job["city"],
                price=material.get("price"),
            )

            try:
                image_payload = prefetch_material_image_cache(
                    article=material["article"],
                    stored_image=material.get("image"),
                    source_url=material.get("source_url"),
                    city=running_job["city"],
                    cookie_override=effective_cookie,
                )
                if image_payload:
                    update_material_image_cache(
                        article=material["article"],
                        image_bytes=image_payload["bytes"],
                        content_type=image_payload["content_type"],
                    )
            except Exception:
                pass

            mark_material_import_job_success(
                job_id,
                strategy=debug_payload.get("strategy"),
                source_url=debug_payload.get("source_url"),
                debug_trace=debug_payload.get("trace"),
            )

            create_audit_log(
                actor_user_id=running_job["owner_user_id"],
                actor_email="",
                action="catalog.material_import_job_completed",
                entity_type="material",
                entity_id=material["article"],
                details={
                    "article": material["article"],
                    "name": material["name"],
                    "category": running_job["category"],
                    "city": running_job["city"],
                    "price": material.get("price"),
                    "job_id": str(job_id),
                },
            )
        except Exception as error:
            mark_material_import_job_retry(
                job_id,
                str(error),
                strategy=getattr(error, "strategy", None),
                source_url=getattr(error, "source_url", None),
                debug_trace=getattr(error, "trace", None),
            )

        return get_material_import_job(job_id)


async def process_due_material_import_jobs(limit: int = 5) -> list[dict]:

    jobs = list_due_material_import_jobs(limit=limit)
    results = []

    for job in jobs:
        result = await process_material_import_job(int(job["id"]))
        if result:
            results.append(result)

    return results


async def material_import_queue_loop(poll_interval_seconds: int = 90):

    while True:
        try:
            await process_due_material_import_jobs(limit=5)
        except Exception:
            pass
        await asyncio.sleep(poll_interval_seconds)


def start_material_import_queue_loop():
    global _queue_loop_task

    if _queue_loop_task and not _queue_loop_task.done():
        return _queue_loop_task

    _queue_loop_task = asyncio.create_task(material_import_queue_loop())
    return _queue_loop_task


def stop_material_import_queue_loop():
    global _queue_loop_task

    if _queue_loop_task and not _queue_loop_task.done():
        _queue_loop_task.cancel()

    _queue_loop_task = None


def get_material_import_job_result(article: str, city: str) -> dict | None:

    items = list_materials(search=article, city=city)

    for item in items:
        if str(item.get("article", "")).strip() == str(article).strip():
            return item

    return None
