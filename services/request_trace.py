from __future__ import annotations

from contextvars import ContextVar
from time import perf_counter
from uuid import uuid4


_request_id_var: ContextVar[str | None] = ContextVar("material_request_id", default=None)
_request_started_at_var: ContextVar[float | None] = ContextVar("material_request_started_at", default=None)


def start_request_trace(request_id: str | None = None) -> str:
    normalized_request_id = str(request_id or "").strip() or uuid4().hex[:12]
    _request_id_var.set(normalized_request_id)
    _request_started_at_var.set(perf_counter())
    return normalized_request_id


def get_request_id() -> str:
    return _request_id_var.get() or ""


def get_request_started_at() -> float | None:
    return _request_started_at_var.get()


def elapsed_ms_since_start() -> int:
    started_at = get_request_started_at()
    if started_at is None:
        return 0
    return int((perf_counter() - started_at) * 1000)
