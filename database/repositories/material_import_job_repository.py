import json
from datetime import datetime

from database.models.material_import_job import MaterialImportJobModel
from database.session import SessionLocal


def _serialize_job(job) -> dict:

    trace_payload = None
    if job.debug_trace:
        try:
            trace_payload = json.loads(job.debug_trace)
        except json.JSONDecodeError:
            trace_payload = [{"stage": "trace_decode_error", "message": job.debug_trace}]

    return {
        "id": str(job.id),
        "article": job.article,
        "category": job.category,
        "city": job.city,
        "owner_user_id": job.owner_user_id,
        "status": job.status,
        "attempt_count": job.attempt_count,
        "max_attempts": job.max_attempts,
        "next_retry_at": job.next_retry_at,
        "last_error": job.last_error,
        "last_strategy": job.last_strategy,
        "last_source_url": job.last_source_url,
        "preferred_url": job.preferred_url,
        "debug_trace": trace_payload or [],
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "completed_at": job.completed_at,
    }


def _apply_debug_payload(
    job,
    *,
    strategy: str | None = None,
    source_url: str | None = None,
    debug_trace: list[dict] | None = None,
):

    if strategy is not None:
        job.last_strategy = strategy

    if source_url is not None:
        job.last_source_url = source_url

    if debug_trace is not None:
        job.debug_trace = json.dumps(debug_trace, ensure_ascii=False)


def get_active_material_import_job(article: str, city: str) -> dict | None:

    db = SessionLocal()

    try:

        job = (
            db.query(MaterialImportJobModel)
            .filter(MaterialImportJobModel.article == article)
            .filter(MaterialImportJobModel.city == city)
            .filter(MaterialImportJobModel.status.in_(["queued", "running", "retry"]))
            .order_by(MaterialImportJobModel.id.desc())
            .first()
        )

        return _serialize_job(job) if job else None

    finally:

        db.close()


def create_material_import_job(
    article: str,
    category: str,
    city: str,
    owner_user_id: str | None = None,
    preferred_url: str | None = None,
    max_attempts: int = 5,
) -> dict:

    db = SessionLocal()

    try:

        now = datetime.utcnow()
        job = MaterialImportJobModel(
            article=article,
            category=category,
            city=city,
            owner_user_id=owner_user_id,
            preferred_url=preferred_url,
            status="queued",
            attempt_count=0,
            max_attempts=max_attempts,
            next_retry_at=now,
            created_at=now,
            updated_at=now,
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        return _serialize_job(job)

    finally:

        db.close()


def get_material_import_job(job_id: int) -> dict | None:

    db = SessionLocal()

    try:

        job = (
            db.query(MaterialImportJobModel)
            .filter(MaterialImportJobModel.id == job_id)
            .first()
        )

        return _serialize_job(job) if job else None

    finally:

        db.close()


def list_due_material_import_jobs(limit: int = 10) -> list[dict]:

    db = SessionLocal()

    try:

        now = datetime.utcnow()
        rows = (
            db.query(MaterialImportJobModel)
            .filter(MaterialImportJobModel.status.in_(["queued", "retry"]))
            .filter(
                (MaterialImportJobModel.next_retry_at.is_(None))
                | (MaterialImportJobModel.next_retry_at <= now)
            )
            .order_by(MaterialImportJobModel.created_at.asc(), MaterialImportJobModel.id.asc())
            .limit(limit)
            .all()
        )

        return [_serialize_job(row) for row in rows]

    finally:

        db.close()


def mark_material_import_job_running(job_id: int) -> dict | None:

    db = SessionLocal()

    try:

        job = (
            db.query(MaterialImportJobModel)
            .filter(MaterialImportJobModel.id == job_id)
            .first()
        )

        if not job:
            return None

        job.status = "running"
        job.attempt_count = (job.attempt_count or 0) + 1
        job.updated_at = datetime.utcnow()
        job.last_error = None

        db.commit()
        db.refresh(job)

        return _serialize_job(job)

    finally:

        db.close()


def mark_material_import_job_success(
    job_id: int,
    *,
    strategy: str | None = None,
    source_url: str | None = None,
    debug_trace: list[dict] | None = None,
) -> dict | None:

    db = SessionLocal()

    try:

        job = (
            db.query(MaterialImportJobModel)
            .filter(MaterialImportJobModel.id == job_id)
            .first()
        )

        if not job:
            return None

        now = datetime.utcnow()
        job.status = "success"
        job.updated_at = now
        job.completed_at = now
        job.next_retry_at = None
        job.last_error = None
        _apply_debug_payload(
            job,
            strategy=strategy,
            source_url=source_url,
            debug_trace=debug_trace,
        )

        db.commit()
        db.refresh(job)

        return _serialize_job(job)

    finally:

        db.close()


def mark_material_import_job_retry(
    job_id: int,
    error: str,
    delay_minutes: int = 5,
    *,
    strategy: str | None = None,
    source_url: str | None = None,
    debug_trace: list[dict] | None = None,
) -> dict | None:

    db = SessionLocal()

    try:

        job = (
            db.query(MaterialImportJobModel)
            .filter(MaterialImportJobModel.id == job_id)
            .first()
        )

        if not job:
            return None

        now = datetime.utcnow()
        job.updated_at = now
        job.last_error = error
        _apply_debug_payload(
            job,
            strategy=strategy,
            source_url=source_url,
            debug_trace=debug_trace,
        )

        if (job.attempt_count or 0) >= (job.max_attempts or 5):
            job.status = "error"
            job.completed_at = now
            job.next_retry_at = None
        else:
            job.status = "retry"
            from datetime import timedelta
            job.next_retry_at = now + timedelta(minutes=delay_minutes)

        db.commit()
        db.refresh(job)

        return _serialize_job(job)

    finally:

        db.close()
