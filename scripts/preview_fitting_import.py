from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.fitting_source_parser import parse_fitting_source_metadata
from services.material_catalog_service import fetch_remote_image_payload


DEFAULT_DATABASE_NAME = "furniture_platform.db"
READ_ONLY_QUERY = "file:{path}?mode=ro"
READ_WRITE_QUERY = "file:{path}?mode=rw"
PARSER_VERSION = "fitting_source_parser@1"
REQUIRED_FITTINGS_COLUMNS = {
    "id",
    "article",
    "name",
    "description",
    "brand",
    "city",
    "price",
    "currency",
    "unit",
    "source",
    "source_url",
    "image_url",
    "image_cached_bytes",
    "image_cached_content_type",
    "source_payload_json",
    "parsed_at",
    "price_updated_at",
}
FITTINGS_INSERT_COLUMNS = [
    "article",
    "name",
    "description",
    "brand",
    "city",
    "price",
    "currency",
    "unit",
    "source",
    "source_url",
    "image_url",
    "image_cached_bytes",
    "image_cached_content_type",
    "source_payload_json",
    "parsed_at",
    "price_updated_at",
]


def _normalize_text(value: object | None) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def _resolve_database_path(database_arg: str | None) -> Path:
    if database_arg:
        candidate = Path(database_arg).expanduser()
        if not candidate.is_absolute():
            candidate = (PROJECT_ROOT / candidate).resolve()
        return candidate

    env_database = _normalize_text(os.getenv("FURNITURE_PLATFORM_DB_PATH"))
    if env_database:
        candidate = Path(env_database).expanduser()
        if not candidate.is_absolute():
            candidate = (PROJECT_ROOT / candidate).resolve()
        return candidate

    return (PROJECT_ROOT / DEFAULT_DATABASE_NAME).resolve()


def _open_read_only_sqlite(database_path: Path) -> sqlite3.Connection:
    uri = READ_ONLY_QUERY.format(path=database_path.as_posix())
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _open_read_write_sqlite(database_path: Path) -> sqlite3.Connection:
    uri = READ_WRITE_QUERY.format(path=database_path.as_posix())
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _normalize_unit_for_preview(unit: str | None) -> tuple[str | None, str | None]:
    raw_unit = _normalize_text(unit)
    if not raw_unit:
        return None, None

    normalized_unit = raw_unit
    if "/" in raw_unit:
        normalized_unit = _normalize_text(raw_unit.split("/", 1)[-1]) or raw_unit

    return normalized_unit, raw_unit


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _query_duplicates(connection: sqlite3.Connection, article: str, city: str) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT id, article, city, name, source_url
        FROM fittings
        WHERE article = ? AND city = ?
        ORDER BY id
        """,
        (article, city),
    ).fetchall()
    return [dict(row) for row in rows]


def _inspect_fittings_schema(connection: sqlite3.Connection) -> tuple[list[str], list[str]]:
    rows = connection.execute("PRAGMA table_info(fittings)").fetchall()
    columns = {row["name"]: row for row in rows}
    missing_required = [
        column_name
        for column_name in REQUIRED_FITTINGS_COLUMNS
        if column_name not in columns
    ]

    missing_insert_defaults = [
        row["name"]
        for row in rows
        if row["notnull"]
        and row["dflt_value"] is None
        and row["name"] not in FITTINGS_INSERT_COLUMNS
        and row["name"] != "id"
    ]

    return missing_required, missing_insert_defaults


def _validate_parsed_item(*, expected_article: str, parsed: dict) -> tuple[bool, str | None]:
    if not parsed.get("success"):
        return False, parsed.get("error") or "Parser failed"

    parsed_article = _normalize_text(parsed.get("article"))
    if not parsed_article:
        return False, "Parsed article is missing"

    if parsed_article != expected_article:
        return False, f"Parsed article mismatch: expected {expected_article}, got {parsed_article}"

    if not _normalize_text(parsed.get("name")):
        return False, "Parsed name is missing"

    if parsed.get("price") is None:
        return False, "Parsed price is missing"

    if not _normalize_text(parsed.get("image_url")):
        return False, "Parsed image_url is missing"

    return True, None


def _validate_confirm_article(*, expected_article: str, parsed_article: str, confirm_article: str | None) -> tuple[bool, str | None]:
    normalized_confirm = _normalize_text(confirm_article)
    if not normalized_confirm:
        return False, "Missing --confirm-article for apply"
    if normalized_confirm != expected_article:
        return False, f"--confirm-article mismatch: expected {expected_article}, got {normalized_confirm}"
    if normalized_confirm != parsed_article:
        return False, f"--confirm-article does not match parsed article: expected {parsed_article}, got {normalized_confirm}"
    return True, None


def _validate_image_payload(image_url: str | None, city: str) -> tuple[dict | None, str | None]:
    image_payload = fetch_remote_image_payload(image_url, city=city)
    if not image_payload:
        return None, "Image payload could not be fetched or validated"

    image_bytes = image_payload["bytes"]
    content_type = _normalize_text(image_payload.get("content_type"))
    if not image_bytes or not content_type:
        return None, "Image payload is empty"

    return {
        "bytes_length": len(image_bytes),
        "content_type": content_type,
        "sha256": sha256(image_bytes).hexdigest(),
        "real_format": content_type.split("/")[-1].upper(),
        "resolved_url": _normalize_text(image_payload.get("resolved_url")),
    }, None


def _build_source_payload_json(
    *,
    source_url: str,
    parsed: dict,
    image_info: dict | None,
    city: str,
    timestamp_iso: str,
) -> dict[str, object]:
    raw_unit = parsed.get("unit")
    normalized_unit, raw_unit_value = _normalize_unit_for_preview(raw_unit)

    return {
        "source_site": parsed.get("source_site"),
        "source_url": source_url,
        "parser_version": PARSER_VERSION,
        "http": {
            "requested_url": parsed.get("requested_url"),
            "final_url": parsed.get("final_url"),
            "status": parsed.get("http_status"),
            "redirect": bool(parsed.get("redirect")),
            "transport": parsed.get("transport"),
        },
        "parsed_item": {
            "article": parsed.get("article"),
            "name": parsed.get("name"),
            "description": parsed.get("description"),
            "brand": parsed.get("brand"),
            "price": parsed.get("price"),
            "currency": parsed.get("currency"),
            "raw_unit": raw_unit_value,
            "normalized_unit": normalized_unit,
            "availability": parsed.get("availability"),
            "image_url": parsed.get("image_url"),
            "characteristics": parsed.get("characteristics") or {},
        },
        "image": {
            "content_type": (image_info or {}).get("content_type"),
            "bytes_length": (image_info or {}).get("bytes_length"),
            "sha256": (image_info or {}).get("sha256"),
            "real_format": (image_info or {}).get("real_format"),
        },
        "preview": {
            "city": city,
            "parsed_at": timestamp_iso,
            "price_updated_at": timestamp_iso,
            "code": None,
            "fitting_type": None,
            "fitting_group": None,
        },
    }


def _build_preview_payload(
    *,
    source_url: str,
    city: str,
    parsed: dict,
    image_info: dict | None,
) -> dict[str, object]:
    raw_unit = parsed.get("unit")
    normalized_unit, raw_unit_value = _normalize_unit_for_preview(raw_unit)
    now_iso = _utc_now_iso()

    return {
        "source_site": parsed.get("source_site"),
        "source_url": source_url,
        "parser_version": PARSER_VERSION,
        "http": {
            "requested_url": parsed.get("requested_url"),
            "final_url": parsed.get("final_url"),
            "status": parsed.get("http_status"),
            "redirect": bool(parsed.get("redirect")),
            "transport": parsed.get("transport"),
        },
        "parsed_item": {
            "article": parsed.get("article"),
            "name": parsed.get("name"),
            "description": parsed.get("description"),
            "brand": parsed.get("brand"),
            "price": parsed.get("price"),
            "currency": parsed.get("currency"),
            "raw_unit": raw_unit_value,
            "normalized_unit": normalized_unit,
            "availability": parsed.get("availability"),
            "image_url": parsed.get("image_url"),
            "characteristics": parsed.get("characteristics") or {},
        },
        "image": {
            "content_type": (image_info or {}).get("content_type"),
            "bytes_length": (image_info or {}).get("bytes_length"),
            "sha256": (image_info or {}).get("sha256"),
            "real_format": (image_info or {}).get("real_format"),
        },
        "preview": {
            "city": city,
            "parsed_at": now_iso,
            "price_updated_at": now_iso,
            "code": None,
            "fitting_type": None,
            "fitting_group": None,
        },
    }


def _print_duplicate_report(duplicates: list[dict[str, object]]) -> None:
    print("Duplicate found: yes" if duplicates else "Duplicate found: no")
    print(f"Duplicate rows: {len(duplicates)}")
    for row in duplicates:
        print(
            " - "
            f"id={row.get('id')}, "
            f"article={row.get('article')}, "
            f"city={row.get('city')}, "
            f"name={row.get('name')}, "
            f"source_url={row.get('source_url')}"
        )


def _print_preview_summary(
    *,
    database_path: Path,
    article: str,
    city: str,
    source_url: str,
    parsed: dict,
    duplicates: list[dict[str, object]],
    image_info: dict | None,
    source_payload_json: dict[str, object],
) -> None:
    fields_to_write = [
        "article",
        "name",
        "description",
        "brand",
        "city",
        "price",
        "currency",
        "unit",
        "source",
        "source_url",
        "image_url",
        "image_cached_bytes",
        "image_cached_content_type",
        "source_payload_json",
        "parsed_at",
        "price_updated_at",
    ]

    print("Mode: DRY RUN")
    print(f"Database path: {database_path}")
    print("Database opened read-only: yes")
    print(f"Article: {article}")
    print(f"City: {city}")
    print(f"Source URL: {source_url}")
    print(f"Parsed successfully: yes")
    print(f"Article matches request: yes")
    print(f"Duplicate found: {'yes' if duplicates else 'no'}")
    print(f"Image validated: {'yes' if image_info else 'no'}")
    print(f"Fields that would be written: {', '.join(fields_to_write)}")
    print("Database write performed: no")
    print("Source payload preview:")
    print(json.dumps(source_payload_json, ensure_ascii=False, indent=2))
    print("Normalized preview:")
    print(
        json.dumps(
            {
                "article": parsed.get("article"),
                "name": parsed.get("name"),
                "description": parsed.get("description"),
                "brand": parsed.get("brand"),
                "city": city,
                "price": parsed.get("price"),
                "currency": parsed.get("currency"),
                "unit": _normalize_unit_for_preview(parsed.get("unit"))[0],
                "source": parsed.get("source_site"),
                "source_url": source_url,
                "image_url": parsed.get("image_url"),
                "image_cached_bytes": (image_info or {}).get("bytes_length"),
                "image_cached_content_type": (image_info or {}).get("content_type"),
                "image_real_format": (image_info or {}).get("real_format"),
                "source_payload_json": source_payload_json,
                "parsed_at": source_payload_json.get("preview", {}).get("parsed_at"),
                "price_updated_at": source_payload_json.get("preview", {}).get("price_updated_at"),
                "code": None,
                "fitting_type": None,
                "fitting_group": None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _build_insert_values(
    *,
    city: str,
    parsed: dict,
    source_url: str,
    image_info: dict,
    source_payload_json_text: str,
    timestamp_iso: str,
) -> dict[str, object | None]:
    normalized_unit, _raw_unit = _normalize_unit_for_preview(parsed.get("unit"))

    return {
        "article": parsed.get("article"),
        "name": parsed.get("name"),
        "description": parsed.get("description"),
        "brand": parsed.get("brand"),
        "city": city,
        "price": parsed.get("price"),
        "currency": parsed.get("currency"),
        "unit": normalized_unit,
        "source": parsed.get("source_site"),
        "source_url": source_url,
        "image_url": parsed.get("image_url"),
        "image_cached_bytes": image_info["bytes"],
        "image_cached_content_type": image_info["content_type"],
        "source_payload_json": source_payload_json_text,
        "parsed_at": timestamp_iso,
        "price_updated_at": timestamp_iso,
    }


def _validate_inserted_row(
    *,
    row: sqlite3.Row | None,
    expected: dict[str, object | None],
    image_info: dict,
    source_payload_json_text: str,
) -> tuple[bool, str | None]:
    if row is None:
        return False, "Inserted row could not be read back"

    checks = {
        "article": expected["article"],
        "city": expected["city"],
        "name": expected["name"],
        "price": expected["price"],
        "source": expected["source"],
        "source_url": expected["source_url"],
        "image_cached_content_type": expected["image_cached_content_type"],
    }

    for field_name, expected_value in checks.items():
        if _normalize_text(row[field_name]) != _normalize_text(expected_value):
            return False, f"Inserted row field mismatch: {field_name}"

    image_bytes = row["image_cached_bytes"]
    if not image_bytes:
        return False, "Inserted row image_cached_bytes is empty"
    if len(image_bytes) != int(image_info["bytes_length"]):
        return False, "Inserted row image_cached_bytes length mismatch"

    stored_payload_text = row["source_payload_json"]
    try:
        stored_payload = json.loads(stored_payload_text)
    except Exception:
        return False, "Inserted row source_payload_json is not valid JSON"

    expected_payload = json.loads(source_payload_json_text)
    if stored_payload.get("parsed_item", {}).get("article") != expected_payload.get("parsed_item", {}).get("article"):
        return False, "Inserted row source_payload_json article mismatch"
    if stored_payload.get("image", {}).get("sha256") != expected_payload.get("image", {}).get("sha256"):
        return False, "Inserted row source_payload_json image sha256 mismatch"

    return True, None


def _verify_committed_row_read_only(
    *,
    database_path: Path,
    inserted_id: int,
    expected: dict[str, object | None],
    image_info: dict,
    source_payload_json_text: str,
) -> bool:
    connection = _open_read_only_sqlite(database_path)
    try:
        row = connection.execute(
            """
            SELECT id, article, city, name, price, source, source_url,
                   image_cached_bytes, image_cached_content_type, source_payload_json
            FROM fittings
            WHERE id = ?
            """,
            (inserted_id,),
        ).fetchone()
        ok, _error_message = _validate_inserted_row(
            row=row,
            expected=expected,
            image_info=image_info,
            source_payload_json_text=source_payload_json_text,
        )
        return ok
    finally:
        connection.close()


def _print_apply_success(*, inserted_id: int, article: str, city: str, image_info: dict) -> None:
    print("Mode: APPLY")
    print("Database opened read-write: yes")
    print("Transaction started: yes")
    print(f"Inserted fitting id: {inserted_id}")
    print(f"Article: {article}")
    print(f"City: {city}")
    print(f"Image BLOB bytes: {image_info['bytes_length']}")
    print("Post-commit read-only verification: passed")
    print("Database write performed: yes")


def _print_apply_rollback() -> None:
    print("Transaction rolled back: yes")
    print("Database write performed: no")


def _apply_insert(
    *,
    database_path: Path,
    article: str,
    city: str,
    source_url: str,
    parsed: dict,
    image_info: dict,
    source_payload_json_text: str,
) -> tuple[int, int]:
    timestamp_iso = _utc_now_iso()
    connection = _open_read_write_sqlite(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")

        missing_required, missing_insert_defaults = _inspect_fittings_schema(connection)
        if missing_required or missing_insert_defaults:
            print("Database write performed: no")
            if missing_required:
                print(f"Error: missing required fittings columns: {', '.join(sorted(missing_required))}", file=sys.stderr)
            if missing_insert_defaults:
                print(
                    "Error: fittings schema has unexpected NOT NULL columns without defaults: "
                    f"{', '.join(sorted(missing_insert_defaults))}",
                    file=sys.stderr,
                )
            return 1, 0

        connection.execute("BEGIN IMMEDIATE")
        print("Mode: APPLY")
        print("Database opened read-write: yes")
        print("Transaction started: yes")

        duplicates = _query_duplicates(connection, article, city)
        if duplicates:
            connection.rollback()
            _print_duplicate_report(duplicates)
            _print_apply_rollback()
            return 2, 0

        insert_values = _build_insert_values(
            city=city,
            parsed=parsed,
            source_url=source_url,
            image_info=image_info,
            source_payload_json_text=source_payload_json_text,
            timestamp_iso=timestamp_iso,
        )
        columns_sql = ", ".join(FITTINGS_INSERT_COLUMNS)
        placeholders_sql = ", ".join("?" for _ in FITTINGS_INSERT_COLUMNS)
        cursor = connection.execute(
            f"INSERT INTO fittings ({columns_sql}) VALUES ({placeholders_sql})",
            [insert_values[column] for column in FITTINGS_INSERT_COLUMNS],
        )
        inserted_id = int(cursor.lastrowid)

        row = connection.execute(
            """
            SELECT id, article, city, name, price, source, source_url,
                   image_cached_bytes, image_cached_content_type, source_payload_json
            FROM fittings
            WHERE id = ?
            """,
            (inserted_id,),
        ).fetchone()
        ok, error_message = _validate_inserted_row(
            row=row,
            expected=insert_values,
            image_info=image_info,
            source_payload_json_text=source_payload_json_text,
        )
        if not ok:
            connection.rollback()
            _print_apply_rollback()
            print(f"Error: {error_message}", file=sys.stderr)
            return 1, 0

        connection.commit()
    except Exception as error:
        try:
            connection.rollback()
        except Exception:
            pass
        _print_apply_rollback()
        print(f"Error: {error}", file=sys.stderr)
        return 1, 0
    finally:
        connection.close()

    if not _verify_committed_row_read_only(
        database_path=database_path,
        inserted_id=inserted_id,
        expected=insert_values,
        image_info=image_info,
        source_payload_json_text=source_payload_json_text,
    ):
        print("Error: Post-commit read-only verification failed", file=sys.stderr)
        return 1, inserted_id

    _print_apply_success(inserted_id=inserted_id, article=article, city=city, image_info=image_info)
    return 0, inserted_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview-only CLI for a point fitting import.",
    )
    parser.add_argument("--article", required=True, help="Expected fitting article")
    parser.add_argument("--source-url", required=True, help="Source product URL")
    parser.add_argument("--city", required=True, help="City code for preview and image validation")
    parser.add_argument("--database", help="SQLite database path")
    parser.add_argument("--apply", action="store_true", help="Write the validated fitting into the local database")
    parser.add_argument("--confirm-article", help="Exact confirmation article required for apply")
    return parser.parse_args()


async def _run_preview(args: argparse.Namespace) -> int:
    article = _normalize_text(args.article)
    source_url = _normalize_text(args.source_url)
    city = _normalize_text(args.city)
    database_path = _resolve_database_path(args.database)

    if not article:
        print("Error: --article is required", file=sys.stderr)
        return 1
    if not source_url:
        print("Error: --source-url is required", file=sys.stderr)
        return 1
    if not city:
        print("Error: --city is required", file=sys.stderr)
        return 1
    if not database_path.exists():
        print(f"Error: database not found: {database_path}", file=sys.stderr)
        return 1

    parsed = await parse_fitting_source_metadata(source_url)
    ok, error_message = _validate_parsed_item(expected_article=article, parsed=parsed)
    if not ok:
        print(f"Error: {error_message}", file=sys.stderr)
        return 1

    image_info, image_error = _validate_image_payload(parsed.get("image_url"), city)
    if image_error:
        print(f"Error: {image_error}", file=sys.stderr)
        return 1

    timestamp_iso = _utc_now_iso()
    source_payload_json = _build_source_payload_json(
        source_url=source_url,
        parsed=parsed,
        image_info=image_info,
        city=city,
        timestamp_iso=timestamp_iso,
    )

    connection = _open_read_only_sqlite(database_path)
    try:
        duplicates = _query_duplicates(connection, article, city)
    finally:
        connection.close()

    if args.apply:
        ok, error_message = _validate_confirm_article(
            expected_article=article,
            parsed_article=_normalize_text(parsed.get("article")) or "",
            confirm_article=args.confirm_article,
        )
        if not ok:
            print(f"Error: {error_message}", file=sys.stderr)
            return 1

        exit_code, _inserted_id = _apply_insert(
            database_path=database_path,
            article=article,
            city=city,
            source_url=source_url,
            parsed=parsed,
            image_info=image_info,
            source_payload_json_text=json.dumps(source_payload_json, ensure_ascii=False),
        )
        return exit_code

    _print_duplicate_report(duplicates)
    _print_preview_summary(
        database_path=database_path,
        article=article,
        city=city,
        source_url=source_url,
        parsed=parsed,
        duplicates=duplicates,
        image_info=image_info,
        source_payload_json=source_payload_json,
    )

    if duplicates:
        print("Database write performed: no")
        return 2

    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(_run_preview(args))


if __name__ == "__main__":
    raise SystemExit(main())
