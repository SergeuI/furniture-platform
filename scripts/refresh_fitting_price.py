"""Safe price-only refresh for fittings.

This CLI reads fittings from the main SQLite database in read-only mode,
fetches current commercial data from the stored source URL, and updates only
dynamic fields when --apply is provided.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.repositories.inventory_repository import update_fitting_price_fields
from services.fitting_source_parser import parse_fitting_source_metadata
from services.legacy_db_config import DEFAULT_DB_PATH


SUPPORTED_SOURCE_SITES = {"viyar", "kronas"}
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("FITTING_REFRESH_TIMEOUT_SECONDS", "45"))
DEFAULT_RETRY_COUNT = int(os.getenv("FITTING_REFRESH_RETRY_COUNT", "2"))
DEFAULT_DELAY_SECONDS = float(os.getenv("FITTING_REFRESH_ITEM_DELAY_SECONDS", "1.0"))


if os.name == "nt":
    import msvcrt
else:
    import fcntl


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and optionally store current fitting price-only fields.",
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--article",
        help="Fitting article to refresh.",
    )
    mode_group.add_argument(
        "--batch",
        action="store_true",
        help="Refresh a limited batch of fittings.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Batch size limit. Required for --batch and ignored for single-item mode.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Refresh all available fittings in batch mode.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the refreshed fitting rows back to the database.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-item parser timeout in seconds.",
    )
    parser.add_argument(
        "--retry-count",
        type=int,
        default=DEFAULT_RETRY_COUNT,
        help="How many parser attempts to make for temporary transport issues.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="Delay between items in batch mode.",
    )
    args = parser.parse_args(argv)

    if args.all and not args.batch:
        parser.error("--all is only supported together with --batch.")
    if args.limit is not None and not args.batch:
        parser.error("--limit is only supported together with --batch.")
    if args.batch and args.all and args.limit is not None:
        parser.error("--limit and --all are mutually exclusive.")
    if args.batch and not args.all and args.limit is None:
        parser.error("--limit is required when --batch is used.")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be a positive integer.")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be a positive number.")
    if args.retry_count < 1:
        parser.error("--retry-count must be at least 1.")
    if args.delay_seconds < 0:
        parser.error("--delay-seconds must be zero or positive.")
    return args


def _resolve_database_path() -> Path:
    database_path = Path(DEFAULT_DB_PATH).resolve()
    print(f"Resolved database path: {database_path}")
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")
    return database_path


def _batch_lock_path(database_path: Path) -> Path:
    normalized_path = os.path.normcase(str(database_path.resolve()))
    digest = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"mp-furniture-fitting-price-{digest}.lock"


def _read_batch_lock_metadata(lock_path: Path) -> dict | None:
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def _print_batch_lock_busy(metadata: dict | None) -> None:
    print("Fitting updater is already running in another process.", file=sys.stderr)
    if metadata is not None:
        print(
            "Lock metadata: " + json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            file=sys.stderr,
        )


def _acquire_os_lock(lock_fd: int) -> None:
    os.lseek(lock_fd, 0, os.SEEK_SET)
    if os.name == "nt":
        msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_os_lock(lock_fd: int) -> None:
    os.lseek(lock_fd, 0, os.SEEK_SET)
    if os.name == "nt":
        msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)


def _write_batch_lock_metadata(lock_fd: int, metadata: dict) -> None:
    payload = json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    os.lseek(lock_fd, 0, os.SEEK_SET)
    os.write(lock_fd, payload)
    os.ftruncate(lock_fd, len(payload))
    os.fsync(lock_fd)


@contextmanager
def _batch_process_lock(
    database_path: Path,
    *,
    mode: str,
    batch_kind: str,
) -> tuple[Path, dict]:
    lock_path = _batch_lock_path(database_path)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY

    lock_fd = os.open(lock_path, flags, 0o600)
    try:
        try:
            _acquire_os_lock(lock_fd)
        except OSError:
            metadata = _read_batch_lock_metadata(lock_path)
            _print_batch_lock_busy(metadata)
            raise SystemExit(3)

        metadata = {
            "pid": os.getpid(),
            "started_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "mode": mode,
            "batch_kind": batch_kind,
            "database_path": str(database_path),
            "argv": sys.argv[1:],
        }
        _write_batch_lock_metadata(lock_fd, metadata)
        try:
            yield lock_path, metadata
        finally:
            _release_os_lock(lock_fd)
    finally:
        os.close(lock_fd)


def _open_readonly_connection(database_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)


def _normalize_text(value: object | None) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_float(value: object | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _detect_source_site(source_url: str | None) -> str:
    normalized = _normalize_text(source_url)
    if not normalized:
        return "manual"

    parsed = urlparse(normalized if "://" in normalized else f"https://{normalized}")
    host = (parsed.netloc or parsed.path or "").lower()

    if "viyar" in host:
        return "viyar"
    if "kronas" in host:
        return "kronas"
    if "mt.ua" in host:
        return "mt"
    return "generic"


def _normalize_stock(value: object | None) -> str | None:
    text = _normalize_text(value)
    return text or None


def _read_fitting_snapshot(
    connection: sqlite3.Connection,
    *,
    item_id: int,
) -> dict:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT
            id,
            city,
            article,
            name,
            price,
            stock,
            currency,
            source,
            source_url,
            parsed_at,
            price_updated_at,
            source_payload_json
        FROM fittings
        WHERE id = ?
        """,
        (item_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f"Controlled error: fitting was not found for id={item_id}")
    return dict(row)


def _list_batch_candidates(
    connection: sqlite3.Connection,
    *,
    article: str | None,
    limit: int | None,
) -> list[dict]:
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    base_sql = """
        SELECT
            id,
            city,
            article,
            name,
            price,
            stock,
            currency,
            source,
            source_url,
            parsed_at,
            price_updated_at,
            source_payload_json
        FROM fittings
        WHERE NULLIF(TRIM(COALESCE(source_url, '')), '') IS NOT NULL
    """
    params: list[object] = []
    if article is not None:
        base_sql += " AND article = ?"
        params.append(article)

    base_sql += " ORDER BY id ASC"
    if limit is not None:
        base_sql += " LIMIT ?"
        params.append(limit)

    rows = cursor.execute(base_sql, params).fetchall()
    return [dict(row) for row in rows]


def _merge_dynamic_fields(current: dict, fetched: dict) -> tuple[dict, dict]:
    merged = {
        "price": _normalize_float(current.get("price")),
        "stock": _normalize_stock(current.get("stock")),
        "currency": _normalize_text(current.get("currency")) or None,
    }
    old_values = dict(merged)

    fetched_price = _normalize_float(fetched.get("price"))
    fetched_stock = _normalize_stock(fetched.get("availability"))
    fetched_currency = _normalize_text(fetched.get("currency")) or None

    if fetched_price is not None:
        merged["price"] = fetched_price
    if fetched_stock is not None:
        merged["stock"] = fetched_stock
    if fetched_currency is not None:
        merged["currency"] = fetched_currency

    changes = {
        field: {"before": old_values[field], "after": merged[field]}
        for field in ("price", "stock", "currency")
        if old_values[field] != merged[field]
    }
    return merged, changes


def _print_row_result(
    *,
    label: str,
    row: dict,
    source_site: str,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> None:
    parts = [
        label,
        f"article={row.get('article')}",
        f"source={source_site}",
    ]
    if before is not None and after is not None:
        parts.append(f"price={before.get('price')}->{after.get('price')}")
        parts.append(f"stock={before.get('stock')}->{after.get('stock')}")
        parts.append(f"currency={before.get('currency')}->{after.get('currency')}")
    if reason:
        parts.append(f"reason={reason}")
    print(" | ".join(parts))


async def _parse_source_with_retry(
    source_url: str,
    *,
    timeout_seconds: float,
    retry_count: int,
) -> dict:
    last_error: str | None = None
    for attempt in range(1, retry_count + 1):
        try:
            result = await asyncio.wait_for(
                parse_fitting_source_metadata(source_url),
                timeout=timeout_seconds,
            )
            if result.get("success"):
                return result
            last_error = _normalize_text(result.get("error")) or "Parser returned success=false"
        except Exception as exc:
            last_error = _normalize_text(exc) or type(exc).__name__

        if attempt < retry_count:
            await asyncio.sleep(1)

    return {
        "success": False,
        "error": last_error or "Parser failed",
    }


async def _process_single_fitting(
    *,
    row: dict,
    apply_mode: bool,
    timeout_seconds: float,
    retry_count: int,
) -> str:
    source_url = _normalize_text(row.get("source_url"))
    source_site = _detect_source_site(source_url)

    if not source_url:
        _print_row_result(label="SKIPPED", row=row, source_site=source_site, reason="missing source_url")
        return "skipped"

    if source_site == "mt":
        _print_row_result(label="SKIPPED", row=row, source_site=source_site, reason="mt is not enabled yet")
        return "skipped"

    if source_site not in SUPPORTED_SOURCE_SITES:
        _print_row_result(label="SKIPPED", row=row, source_site=source_site, reason="unsupported source")
        return "skipped"

    fetched = await _parse_source_with_retry(
        source_url,
        timeout_seconds=timeout_seconds,
        retry_count=retry_count,
    )

    if not fetched.get("success"):
        _print_row_result(
            label="FAILED",
            row=row,
            source_site=source_site,
            reason=_normalize_text(fetched.get("error")) or "parser failure",
        )
        return "failed"

    merged, changes = _merge_dynamic_fields(row, fetched)
    if not changes:
        _print_row_result(label="UNCHANGED", row=row, source_site=source_site, before=row, after=row)
        return "unchanged"

    if not apply_mode:
        _print_row_result(label="WOULD UPDATE", row=row, source_site=source_site, before=row, after=merged)
        return "would_update"

    now = datetime.utcnow()
    updated_row = update_fitting_price_fields(
        item_id=row["id"],
        price=merged["price"],
        stock=merged["stock"],
        currency=merged["currency"],
        parsed_at=now,
        price_updated_at=now,
    )
    if not updated_row:
        _print_row_result(label="FAILED", row=row, source_site=source_site, reason="database row disappeared")
        return "failed"

    _print_row_result(label="UPDATED", row=row, source_site=source_site, before=row, after=updated_row)
    return "updated"


async def _run_batch(
    connection: sqlite3.Connection,
    *,
    article: str | None,
    limit: int | None,
    apply_mode: bool,
    timeout_seconds: float,
    retry_count: int,
    delay_seconds: float,
) -> int:
    candidates = _list_batch_candidates(connection, article=article, limit=limit)
    counters = {
        "mode": "APPLY" if apply_mode else "DRY-RUN",
        "scanned": len(candidates),
        "checked": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "failed": 0,
    }

    for index, row in enumerate(candidates):
        source_site = _detect_source_site(row.get("source_url"))
        if source_site == "mt" or source_site not in SUPPORTED_SOURCE_SITES or not _normalize_text(row.get("source_url")):
            counters["skipped"] += 1
            await _process_single_fitting(
                row=row,
                apply_mode=apply_mode,
                timeout_seconds=timeout_seconds,
                retry_count=retry_count,
            )
            continue

        counters["checked"] += 1
        result = await _process_single_fitting(
            row=row,
            apply_mode=apply_mode,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
        )
        if result == "updated":
            counters["updated"] += 1
        elif result == "unchanged":
            counters["unchanged"] += 1
        elif result == "skipped":
            counters["skipped"] += 1
        elif result == "failed":
            counters["failed"] += 1

        if index + 1 < len(candidates) and delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    print("SUMMARY:")
    for key in ("mode", "scanned", "checked", "updated", "unchanged", "skipped", "failed"):
        print(f"  {key}: {counters[key]}")

    return 1 if counters["failed"] > 0 else 0


async def _run_single(
    *,
    article: str,
    apply_mode: bool,
    timeout_seconds: float,
    retry_count: int,
) -> int:
    database_path = _resolve_database_path()
    with _open_readonly_connection(database_path) as connection:
        rows = _list_batch_candidates(connection, article=article, limit=None)

        if not rows:
            print(f"No fittings found for article={article}")
            print("SUMMARY:")
            print(f"  mode: {'APPLY' if apply_mode else 'DRY-RUN'}")
            print("  scanned: 0")
            print("  checked: 0")
            print("  updated: 0")
            print("  unchanged: 0")
            print("  skipped: 0")
            print("  failed: 0")
            return 0

        counters = {
            "mode": "APPLY" if apply_mode else "DRY-RUN",
            "scanned": len(rows),
            "checked": 0,
            "updated": 0,
            "unchanged": 0,
            "skipped": 0,
            "failed": 0,
        }

        for row in rows:
            source_site = _detect_source_site(row.get("source_url"))
            if source_site == "mt" or source_site not in SUPPORTED_SOURCE_SITES or not _normalize_text(row.get("source_url")):
                counters["skipped"] += 1
                if source_site == "mt":
                    skip_reason = "mt is not enabled yet"
                elif not _normalize_text(row.get("source_url")):
                    skip_reason = "missing source_url"
                else:
                    skip_reason = "unsupported source"
                _print_row_result(
                    label="SKIPPED",
                    row=row,
                    source_site=source_site,
                    reason=skip_reason,
                )
                continue
            counters["checked"] += 1

            result = await _process_single_fitting(
                row=row,
                apply_mode=apply_mode,
                timeout_seconds=timeout_seconds,
                retry_count=retry_count,
            )
            if result == "updated":
                counters["updated"] += 1
            elif result == "unchanged":
                counters["unchanged"] += 1
            elif result == "skipped":
                counters["skipped"] += 1
            elif result == "failed":
                counters["failed"] += 1

    print("SUMMARY:")
    for key in ("mode", "scanned", "checked", "updated", "unchanged", "skipped", "failed"):
        print(f"  {key}: {counters[key]}")

    return 1 if counters["failed"] > 0 else 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args(argv)
    database_path = _resolve_database_path()
    before_size = database_path.stat().st_size
    before_mtime = database_path.stat().st_mtime

    if args.batch:
        with _batch_process_lock(
            database_path,
            mode="APPLY" if args.apply else "DRY-RUN",
            batch_kind="all" if args.all else "limit",
        ):
            with _open_readonly_connection(database_path) as connection:
                result = asyncio.run(
                    _run_batch(
                        connection,
                        article=None,
                        limit=None if args.all else int(args.limit),
                        apply_mode=bool(args.apply),
                        timeout_seconds=float(args.timeout_seconds),
                        retry_count=int(args.retry_count),
                        delay_seconds=float(args.delay_seconds),
                    )
                )
        print(f"Database size before: {before_size}")
        print(f"Database mtime before: {before_mtime}")
        print("Database write performed: " + ("yes" if args.apply else "no"))
        print("Writer invoked: " + ("yes" if args.apply else "no"))
        print("External fetch performed: yes")
        return result

    result = asyncio.run(
        _run_single(
            article=(args.article or "").strip(),
            apply_mode=bool(args.apply),
            timeout_seconds=float(args.timeout_seconds),
            retry_count=int(args.retry_count),
        )
    )
    if args.apply:
        print("Mode: APPLY")
        print("Database write performed: yes")
        print("Writer invoked: yes")
    else:
        print("Mode: DRY-RUN")
        print("Database write performed: no")
        print("Writer invoked: no")
    print("External fetch performed: yes")
    print(f"Database size before: {before_size}")
    print(f"Database mtime before: {before_mtime}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
