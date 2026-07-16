from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.fitting_image_gallery_service import (
    PreparedFittingGalleryImage,
    normalize_fitting_gallery_image_urls,
    prepare_fitting_gallery_images,
)
from services.fitting_source_parser import parse_fitting_source_metadata
from services.material_catalog_service import fetch_remote_image_payload


REQUIRED_TABLES = ("fittings", "fitting_images")
FITTINGS_REQUIRED_COLUMNS = {
    "id",
    "city",
    "code",
    "article",
    "name",
    "price",
    "stock",
    "fitting_type",
    "fitting_group",
    "image_url",
    "image_cached_bytes",
    "image_cached_content_type",
    "source_url",
    "source",
    "brand",
    "description",
    "unit",
    "currency",
    "parsed_at",
    "price_updated_at",
    "source_payload_json",
    "owner_user_id",
    "is_system",
    "is_active",
    "sort_order",
    "updated_at",
}
FITTING_IMAGES_REQUIRED_COLUMNS = {
    "id",
    "fitting_id",
    "sort_order",
    "is_primary",
    "source_url",
    "image_cached_bytes",
    "image_cached_content_type",
    "image_sha256",
    "created_at",
    "updated_at",
}


def _normalize_text(value: object | None) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def _resolve_database_path(database_arg: str) -> Path:
    candidate = Path(database_arg).expanduser()
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    return candidate


def _open_sqlite(database_path: Path, *, readonly: bool) -> sqlite3.Connection:
    mode = "ro" if readonly else "rw"
    uri = f"file:{database_path.as_posix()}?mode={mode}"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _require_schema(connection: sqlite3.Connection) -> None:
    missing_tables = [table_name for table_name in REQUIRED_TABLES if not _table_exists(connection, table_name)]
    if missing_tables:
        raise SystemExit("Missing required tables: " + ", ".join(missing_tables))

    fitting_columns = _table_columns(connection, "fittings")
    image_columns = _table_columns(connection, "fitting_images")

    missing_fitting_columns = sorted(FITTINGS_REQUIRED_COLUMNS - fitting_columns)
    if missing_fitting_columns:
        raise SystemExit(
            "Table 'fittings' is missing required columns: "
            + ", ".join(missing_fitting_columns)
        )

    missing_image_columns = sorted(FITTING_IMAGES_REQUIRED_COLUMNS - image_columns)
    if missing_image_columns:
        raise SystemExit(
            "Table 'fitting_images' is missing required columns: "
            + ", ".join(missing_image_columns)
        )


def _integrity_check(connection: sqlite3.Connection) -> None:
    row = connection.execute("PRAGMA integrity_check").fetchone()
    if not row or str(row[0]).lower() != "ok":
        raise SystemExit(f"Integrity check failed: {row[0] if row else 'unknown'}")


def _load_fitting(connection: sqlite3.Connection, fitting_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            id,
            city,
            code,
            article,
            name,
            price,
            stock,
            fitting_type,
            fitting_group,
            image_url,
            image_cached_bytes,
            image_cached_content_type,
            source_url,
            source,
            brand,
            description,
            unit,
            currency,
            parsed_at,
            price_updated_at,
            source_payload_json,
            owner_user_id,
            is_system,
            is_active,
            sort_order,
            updated_at
        FROM fittings
        WHERE id = ?
        """,
        (fitting_id,),
    ).fetchone()


def _load_gallery_rows(connection: sqlite3.Connection, fitting_id: int) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            id,
            fitting_id,
            sort_order,
            is_primary,
            source_url,
            image_cached_content_type,
            image_sha256,
            image_cached_bytes
        FROM fitting_images
        WHERE fitting_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (fitting_id,),
    ).fetchall()


def _safe_parse_source_payload_json(value: object | None) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value

    text = _normalize_text(value)
    if not text:
        return {}

    try:
        parsed = json.loads(text)
    except Exception:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _is_blank_like(value: object | None) -> bool:
    text = _normalize_text(value)
    if not text:
        return True

    lowered = text.lower()
    return lowered in {"none", "null", "n/a", "na", "unknown", "undefined", "технічне значення"}


def _count_characteristics(value: object | None) -> int:
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, (list, tuple)):
        return len(value)
    return 0


def _source_site_from_url(source_url: str | None) -> str:
    parsed = urlsplit(_normalize_text(source_url) or "")
    host = (parsed.hostname or "").lower()
    if "viyar" in host:
        return "viyar"
    return ""


def _awaitable_parse_fitting_source_metadata(source_url: str) -> dict[str, Any]:
    result = parse_fitting_source_metadata(source_url)
    if hasattr(result, "__await__"):
        return asyncio.run(result)
    return result


def _build_source_payload(
    *,
    source_site: str,
    source_url: str,
    selected_city: str | None,
    parsed_item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_site": source_site,
        "source_url": source_url,
        "selected_city": selected_city,
        "parsed_item": parsed_item,
    }


def _prepare_gallery(
    *,
    fitting_row: sqlite3.Row,
    image_urls: list[str],
) -> list[PreparedFittingGalleryImage]:
    current_bytes = fitting_row["image_cached_bytes"]
    current_content_type = _normalize_text(fitting_row["image_cached_content_type"])
    city = _normalize_text(fitting_row["city"])

    kwargs: dict[str, object] = {}
    if current_bytes and current_content_type:
        kwargs["existing_primary_bytes"] = bytes(current_bytes)
        kwargs["existing_primary_content_type"] = current_content_type

    return list(
        prepare_fitting_gallery_images(
            image_urls,
            fetcher=lambda source_url: fetch_remote_image_payload(source_url, city=city),
            **kwargs,
        )
    )


def _same_json_payload(current_value: object | None, new_payload: dict[str, Any]) -> bool:
    current_payload = _safe_parse_source_payload_json(current_value)
    return current_payload == new_payload


def _build_update_plan(
    *,
    fitting_row: sqlite3.Row,
    parsed: dict[str, Any],
    prepared_images: list[PreparedFittingGalleryImage],
    source_payload: dict[str, Any],
) -> dict[str, Any]:
    updates: dict[str, Any] = {}

    final_source_url = _normalize_text(parsed.get("final_url")) or _normalize_text(fitting_row["source_url"])
    source_site = _normalize_text(parsed.get("source_site")) or _source_site_from_url(final_source_url) or "viyar"

    if not _same_json_payload(fitting_row["source_payload_json"], source_payload):
        updates["source_payload_json"] = json.dumps(source_payload, ensure_ascii=False)

    if source_site and _normalize_text(fitting_row["source"]) != source_site:
        updates["source"] = source_site

    if final_source_url and _normalize_text(fitting_row["source_url"]) != final_source_url:
        updates["source_url"] = final_source_url

    primary_image = prepared_images[0]
    if _normalize_text(fitting_row["image_url"]) != primary_image.source_url:
        updates["image_url"] = primary_image.source_url

    current_bytes = fitting_row["image_cached_bytes"]
    if bytes(current_bytes or b"") != primary_image.image_bytes:
        updates["image_cached_bytes"] = primary_image.image_bytes

    if _normalize_text(fitting_row["image_cached_content_type"]) != primary_image.content_type:
        updates["image_cached_content_type"] = primary_image.content_type

    parsed_description = _normalize_text(parsed.get("description"))
    if _is_blank_like(fitting_row["description"]) and parsed_description:
        updates["description"] = parsed_description

    parsed_brand = _normalize_text(parsed.get("brand"))
    if _is_blank_like(fitting_row["brand"]) and parsed_brand:
        updates["brand"] = parsed_brand

    parsed_availability = _normalize_text(parsed.get("availability"))
    if _is_blank_like(fitting_row["stock"]) and parsed_availability:
        updates["stock"] = parsed_availability

    return updates


def _print_gallery_rows(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("Current fitting_images: none")
        return

    print("Current fitting_images:")
    for row in rows:
        blob_size = len(row["image_cached_bytes"] or b"")
        print(
            "  - "
            f"id={row['id']}, "
            f"sort_order={row['sort_order']}, "
            f"is_primary={bool(row['is_primary'])}, "
            f"source_url={row['source_url']}, "
            f"content_type={row['image_cached_content_type']}, "
            f"blob_size={blob_size}, "
            f"sha256={row['image_sha256']}"
        )


def _print_prepared_images(prepared_images: list[PreparedFittingGalleryImage]) -> None:
    print("Prepared gallery:")
    for image in prepared_images:
        print(
            "  - "
            f"sort_order={image.sort_order}, "
            f"is_primary={image.is_primary}, "
            f"source_url={image.source_url}, "
            f"content_type={image.content_type}, "
            f"blob_size={len(image.image_bytes)}, "
            f"sha256={image.sha256}"
        )


def _print_update_plan(updates: dict[str, Any]) -> None:
    if not updates:
        print("Planned field updates: none")
        return

    print("Planned field updates:")
    for field_name, new_value in updates.items():
        if field_name == "source_payload_json":
            payload = _safe_parse_source_payload_json(new_value)
            parsed_item = payload.get("parsed_item") if isinstance(payload, dict) else {}
            image_urls = parsed_item.get("image_urls") if isinstance(parsed_item, dict) else []
            characteristics = parsed_item.get("characteristics") if isinstance(parsed_item, dict) else {}
            print(
                "  - "
                f"{field_name}: refresh to rich payload "
                f"(image_urls={len(image_urls or []) if isinstance(image_urls, list) else 'n/a'}, "
                f"characteristics={_count_characteristics(characteristics)})"
            )
            continue

        if isinstance(new_value, bytes):
            print(f"  - {field_name}: blob bytes ({len(new_value)} bytes)")
        else:
            print(f"  - {field_name}: {_normalize_text(new_value) or ''}")


def _extract_state_summary(
    *,
    fitting_row: sqlite3.Row,
    parsed: dict[str, Any],
    prepared_images: list[PreparedFittingGalleryImage],
    current_gallery_count: int,
) -> None:
    parsed_item = parsed.get("parsed_item") if isinstance(parsed, dict) else {}
    if not isinstance(parsed_item, dict) or not parsed_item:
        parsed_item = parsed if isinstance(parsed, dict) else {}
    image_urls = parsed_item.get("image_urls") if isinstance(parsed_item, dict) else []
    characteristics = parsed_item.get("characteristics") if isinstance(parsed_item, dict) else {}
    print(f"Parser success: {bool(parsed.get('success'))}")
    print(f"Parser source_site: {_normalize_text(parsed.get('source_site')) or 'unknown'}")
    print(f"Parser name: {_normalize_text(parsed.get('name')) or ''}")
    print(f"Parser article: {_normalize_text(parsed.get('article')) or ''}")
    print(f"Parser price: {parsed.get('price')}")
    print(f"Parser brand: {_normalize_text(parsed.get('brand')) or ''}")
    print(f"Parser availability: {_normalize_text(parsed.get('availability')) or ''}")
    print(f"Parser image_url: {_normalize_text(parsed.get('image_url')) or ''}")
    print(f"Parser image_urls count: {len(image_urls) if isinstance(image_urls, list) else 0}")
    print(f"Parser characteristics count: {_count_characteristics(characteristics)}")
    print(f"Prepared images count: {len(prepared_images)}")
    print(f"Current fitting_images count: {current_gallery_count}")


def _validate_parser_payload(parsed: dict[str, Any]) -> tuple[str, list[str], int]:
    if not parsed.get("success"):
        raise SystemExit(_normalize_text(parsed.get("error")) or "Parser failed")

    parsed_item = parsed.get("parsed_item")
    parsed_item = parsed_item if isinstance(parsed_item, dict) else parsed

    image_urls = parsed_item.get("image_urls") if isinstance(parsed_item, dict) else []
    if not image_urls:
        raise SystemExit("Rich parser did not return image_urls.")

    characteristics = parsed_item.get("characteristics") if isinstance(parsed_item, dict) else {}
    characteristics_count = _count_characteristics(characteristics)
    if characteristics_count <= 0:
        raise SystemExit("Rich parser did not return characteristics.")

    source_site = _normalize_text(parsed.get("source_site")) or _normalize_text(parsed_item.get("source_site")) or ""
    if source_site != "viyar":
        raise SystemExit("Only Viyar fittings are supported.")

    normalized_urls = normalize_fitting_gallery_image_urls(image_urls)
    return source_site, normalized_urls, characteristics_count


def _insert_fitting_images(
    connection: sqlite3.Connection,
    *,
    fitting_id: int,
    prepared_images: list[PreparedFittingGalleryImage],
) -> None:
    connection.executemany(
        """
        INSERT INTO fitting_images (
            fitting_id,
            sort_order,
            is_primary,
            source_url,
            image_cached_bytes,
            image_cached_content_type,
            image_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                fitting_id,
                image.sort_order,
                int(image.is_primary),
                image.source_url,
                image.image_bytes,
                image.content_type,
                image.sha256,
            )
            for image in prepared_images
        ],
    )


def _apply_updates(
    connection: sqlite3.Connection,
    *,
    fitting_id: int,
    updates: dict[str, Any],
) -> None:
    if not updates:
        return

    columns = list(updates.keys())
    set_clause = ", ".join(f"{column} = ?" for column in columns)
    values = [updates[column] for column in columns]
    values.append(fitting_id)
    connection.execute(
        f"UPDATE fittings SET {set_clause} WHERE id = ?",
        values,
    )


def _protected_snapshot(fitting_row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": fitting_row["id"],
        "article": fitting_row["article"],
        "city": fitting_row["city"],
        "name": fitting_row["name"],
        "price": fitting_row["price"],
        "description": fitting_row["description"],
        "fitting_type": fitting_row["fitting_type"],
        "fitting_group": fitting_row["fitting_group"],
        "unit": fitting_row["unit"],
        "currency": fitting_row["currency"],
        "is_system": bool(fitting_row["is_system"]),
        "is_active": bool(fitting_row["is_active"]),
        "sort_order": fitting_row["sort_order"],
        "created_at": fitting_row["parsed_at"],
    }


def _verify_protected_fields(
    before: dict[str, Any],
    after: sqlite3.Row,
) -> None:
    checks = {
        "id": after["id"],
        "article": after["article"],
        "city": after["city"],
        "name": after["name"],
        "price": after["price"],
        "description": after["description"],
        "fitting_type": after["fitting_type"],
        "fitting_group": after["fitting_group"],
        "unit": after["unit"],
        "currency": after["currency"],
        "is_system": bool(after["is_system"]),
        "is_active": bool(after["is_active"]),
        "sort_order": after["sort_order"],
        "created_at": after["parsed_at"],
    }

    for field_name, original_value in before.items():
        if checks[field_name] != original_value:
            raise SystemExit(f"Protected field changed unexpectedly: {field_name}")


def _verify_post_apply(
    connection: sqlite3.Connection,
    *,
    fitting_id: int,
    before_snapshot: dict[str, Any],
    expected_images: list[PreparedFittingGalleryImage],
    expected_source_payload: dict[str, Any],
) -> None:
    _integrity_check(connection)

    after_row = _load_fitting(connection, fitting_id)
    if not after_row:
        raise SystemExit("Fitting disappeared after apply.")

    _verify_protected_fields(before_snapshot, after_row)

    current_gallery_rows = _load_gallery_rows(connection, fitting_id)
    if len(current_gallery_rows) != len(expected_images):
        raise SystemExit("Gallery row count after apply does not match prepared images.")

    for index, (gallery_row, prepared_image) in enumerate(zip(current_gallery_rows, expected_images)):
        if int(gallery_row["sort_order"]) != index:
            raise SystemExit("Gallery sort_order is not sequential after apply.")
        if bool(gallery_row["is_primary"]) != prepared_image.is_primary:
            raise SystemExit("Gallery primary flag mismatch after apply.")
        if _normalize_text(gallery_row["source_url"]) != prepared_image.source_url:
            raise SystemExit("Gallery source_url mismatch after apply.")
        if _normalize_text(gallery_row["image_cached_content_type"]) != prepared_image.content_type:
            raise SystemExit("Gallery content_type mismatch after apply.")
        if _normalize_text(gallery_row["image_sha256"]) != prepared_image.sha256:
            raise SystemExit("Gallery sha256 mismatch after apply.")

    if not current_gallery_rows:
        raise SystemExit("Gallery rows were not created.")

    if not bool(current_gallery_rows[0]["is_primary"]) or int(current_gallery_rows[0]["sort_order"]) != 0:
        raise SystemExit("Primary gallery row is not sort_order=0 after apply.")

    if _safe_parse_source_payload_json(after_row["source_payload_json"]) != expected_source_payload:
        raise SystemExit("source_payload_json after apply does not match expected rich payload.")


def _print_dry_run(
    *,
    database_path: Path,
    fitting_row: sqlite3.Row,
    parsed: dict[str, Any],
    image_urls: list[str],
    current_gallery_rows: list[sqlite3.Row],
    prepared_images: list[PreparedFittingGalleryImage],
    updates: dict[str, Any],
) -> None:
    print("Mode: DRY-RUN")
    print(f"Database: {database_path}")
    print(f"Integrity check: ok")
    print(f"Fitting id: {int(fitting_row['id'])}")
    print(f"Article: {fitting_row['article']}")
    print(f"Source: {fitting_row['source']}")
    print(f"Source URL: {fitting_row['source_url']}")
    print(f"Current main blob size: {len(fitting_row['image_cached_bytes'] or b'')}")
    print(f"Current main blob sha256: {hashlib.sha256(bytes(fitting_row['image_cached_bytes'] or b'' )).hexdigest() if fitting_row['image_cached_bytes'] else 'empty'}")
    print(f"Parser image_urls count: {len(image_urls)}")
    print(f"Prepared images count: {len(prepared_images)}")
    print(f"Current fitting_images count: {len(current_gallery_rows)}")
    _extract_state_summary(
        fitting_row=fitting_row,
        parsed=parsed,
        prepared_images=prepared_images,
        current_gallery_count=len(current_gallery_rows),
    )
    _print_gallery_rows(current_gallery_rows)
    _print_prepared_images(prepared_images)
    _print_update_plan(updates)
    if current_gallery_rows:
        print("Apply status: blocked because fitting_images already exist.")
    else:
        print("Apply status: allowed if the current row remains unchanged and --apply is used.")
    print("Database write performed: no")


def _print_apply_header(
    *,
    database_path: Path,
    fitting_row: sqlite3.Row,
    image_urls: list[str],
    prepared_images: list[PreparedFittingGalleryImage],
    current_gallery_rows: list[sqlite3.Row],
) -> None:
    print("Mode: APPLY")
    print(f"Database: {database_path}")
    print("Integrity check: ok")
    print(f"Fitting id: {int(fitting_row['id'])}")
    print(f"Article: {fitting_row['article']}")
    print(f"Source: {fitting_row['source']}")
    print(f"Source URL: {fitting_row['source_url']}")
    print(f"Parser image_urls count: {len(image_urls)}")
    print(f"Prepared images count: {len(prepared_images)}")
    print(f"Current fitting_images count: {len(current_gallery_rows)}")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Repair rich Viyar data for a single fitting without touching unrelated rows.",
    )
    parser.add_argument("--database", required=True, help="Path to the SQLite database")
    parser.add_argument("--fitting-id", required=True, type=int, help="Fitting id to repair")
    parser.add_argument("--apply", action="store_true", help="Write changes to the database")
    args = parser.parse_args(argv)

    database_path = _resolve_database_path(args.database)
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    readonly_connection = _open_sqlite(database_path, readonly=True)
    try:
        _integrity_check(readonly_connection)
        _require_schema(readonly_connection)

        fitting_row = _load_fitting(readonly_connection, args.fitting_id)
        if not fitting_row:
            raise SystemExit(f"Fitting not found: {args.fitting_id}")

        source_url = _normalize_text(fitting_row["source_url"])
        if not source_url:
            raise SystemExit("Fitting source_url is missing.")

        current_source_site = _normalize_text(fitting_row["source"]) or _source_site_from_url(source_url)
        if current_source_site != "viyar":
            raise SystemExit("Only Viyar fittings are supported.")

        parsed = _awaitable_parse_fitting_source_metadata(source_url)
        source_site, image_urls, characteristics_count = _validate_parser_payload(parsed)
        parsed_item = parsed.get("parsed_item")
        parsed_item = parsed_item if isinstance(parsed_item, dict) else parsed

        current_gallery_rows = _load_gallery_rows(readonly_connection, args.fitting_id)
        prepared_images = _prepare_gallery(fitting_row=fitting_row, image_urls=image_urls)
        source_payload = _build_source_payload(
            source_site=source_site,
            source_url=_normalize_text(parsed.get("final_url")) or source_url,
            selected_city=_normalize_text(fitting_row["city"]),
            parsed_item=parsed_item,
        )
        updates = _build_update_plan(
            fitting_row=fitting_row,
            parsed=parsed,
            prepared_images=prepared_images,
            source_payload=source_payload,
        )

        if not args.apply:
            _print_dry_run(
                database_path=database_path,
                fitting_row=fitting_row,
                parsed=parsed,
                image_urls=image_urls,
                current_gallery_rows=current_gallery_rows,
                prepared_images=prepared_images,
                updates=updates,
            )
            return 0
    finally:
        readonly_connection.close()

    write_connection = _open_sqlite(database_path, readonly=False)
    try:
        write_connection.execute("PRAGMA foreign_keys = ON")
        _integrity_check(write_connection)
        _require_schema(write_connection)

        fitting_row = _load_fitting(write_connection, args.fitting_id)
        if not fitting_row:
            raise SystemExit(f"Fitting not found: {args.fitting_id}")

        current_source_site = _normalize_text(fitting_row["source"]) or _source_site_from_url(source_url)
        if current_source_site != "viyar":
            raise SystemExit("Only Viyar fittings are supported.")

        source_url = _normalize_text(fitting_row["source_url"])
        if not source_url:
            raise SystemExit("Fitting source_url is missing.")

        current_gallery_rows = _load_gallery_rows(write_connection, args.fitting_id)
        if current_gallery_rows:
            _print_apply_header(
                database_path=database_path,
                fitting_row=fitting_row,
                image_urls=image_urls,
                prepared_images=prepared_images,
                current_gallery_rows=current_gallery_rows,
            )
            print("Database write performed: no")
            raise SystemExit("Existing fitting_images rows found. Refusing to rebuild or replace gallery.")

        before_snapshot = _protected_snapshot(fitting_row)

        _print_apply_header(
            database_path=database_path,
            fitting_row=fitting_row,
            image_urls=image_urls,
            prepared_images=prepared_images,
            current_gallery_rows=current_gallery_rows,
        )
        _extract_state_summary(
            fitting_row=fitting_row,
            parsed=parsed,
            prepared_images=prepared_images,
            current_gallery_count=len(current_gallery_rows),
        )
        _print_update_plan(updates)

        if not image_urls:
            raise SystemExit("Rich parser did not return image_urls.")
        if characteristics_count <= 0:
            raise SystemExit("Rich parser did not return characteristics.")
        if not prepared_images:
            raise SystemExit("No gallery images were prepared.")

        write_connection.execute("BEGIN IMMEDIATE")
        try:
            _apply_updates(write_connection, fitting_id=args.fitting_id, updates=updates)
            _insert_fitting_images(
                write_connection,
                fitting_id=args.fitting_id,
                prepared_images=prepared_images,
            )
            write_connection.commit()
        except Exception:
            write_connection.rollback()
            raise

        _verify_post_apply(
            write_connection,
            fitting_id=args.fitting_id,
            before_snapshot=before_snapshot,
            expected_images=prepared_images,
            expected_source_payload=source_payload,
        )

        print("Transaction committed: yes")
        print("Database write performed: yes")
        print(f"Inserted gallery rows: {len(prepared_images)}")
        print(f"Integrity check after apply: ok")
        return 0
    finally:
        write_connection.close()


if __name__ == "__main__":
    raise SystemExit(run())
