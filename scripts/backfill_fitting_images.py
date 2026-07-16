from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.fitting_source_parser import parse_fitting_source_metadata
from services.material_catalog_service import fetch_remote_image_payload


EXPECTED_GALLERY_SIZE = 5
EXPECTED_PRIMARY_SORT_ORDER = 0
EXPECTED_REQUIRED_COLUMNS = {
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


@dataclass(frozen=True)
class GalleryImage:
    sort_order: int
    is_primary: bool
    source_url: str
    image_bytes: bytes
    content_type: str
    image_sha256: str


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


def _require_schema(connection: sqlite3.Connection) -> None:
    missing = [
        table_name
        for table_name in ("fittings", "fitting_images")
        if not _table_exists(connection, table_name)
    ]
    if missing:
        raise SystemExit("Missing required tables: " + ", ".join(missing))

    fitting_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(fittings)").fetchall()
    }
    image_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(fitting_images)").fetchall()
    }

    if "image_cached_bytes" not in fitting_columns or "image_cached_content_type" not in fitting_columns:
        raise SystemExit("Table 'fittings' is missing cached image columns.")

    missing_image_columns = sorted(EXPECTED_REQUIRED_COLUMNS - image_columns)
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
            article,
            city,
            source,
            source_url,
            image_cached_bytes,
            image_cached_content_type
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
            image_sha256
        FROM fitting_images
        WHERE fitting_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (fitting_id,),
    ).fetchall()


def _normalize_image_url(value: object | None) -> str | None:
    url = _normalize_text(value)
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None

    query_items = [
        (key, item_value)
        for key, item_value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() != "size"
    ]
    return parsed._replace(query=urlencode(query_items, doseq=True), fragment="").geturl()


def _normalize_image_urls(values: object | None) -> list[str]:
    if not isinstance(values, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        url = _normalize_image_url(value)
        if not url or url in seen:
            continue
        seen.add(url)
        normalized.append(url)
    return normalized


def _detect_content_type(image_bytes: bytes) -> str | None:
    try:
        from PIL import Image
    except Exception:
        return None

    from io import BytesIO

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            image_format = (image.format or "").upper()
    except Exception:
        return None

    mime_map = {
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "PNG": "image/png",
    }
    return mime_map.get(image_format)


def _sha256_hex(image_bytes: bytes) -> str:
    return sha256(image_bytes).hexdigest()


def _build_gallery_images(
    *,
    fitting_row: sqlite3.Row,
    image_urls: list[str],
) -> list[GalleryImage]:
    if not image_urls:
        raise SystemExit("Parser did not return image_urls.")

    cached_bytes = fitting_row["image_cached_bytes"]
    cached_content_type = _normalize_text(fitting_row["image_cached_content_type"])

    if not cached_bytes:
        raise SystemExit("Main fitting image cache is empty.")
    if not cached_content_type:
        raise SystemExit("Main fitting image content type is missing.")

    detected_main_content_type = _detect_content_type(cached_bytes)
    if detected_main_content_type and detected_main_content_type != cached_content_type:
        raise SystemExit(
            "Main fitting image content type mismatch: "
            f"stored={cached_content_type}, detected={detected_main_content_type}"
        )

    gallery_images: list[GalleryImage] = []
    seen_hashes: set[str] = set()
    next_sort_order = 0

    main_source_url = image_urls[0]
    main_hash = _sha256_hex(cached_bytes)
    gallery_images.append(
        GalleryImage(
            sort_order=next_sort_order,
            is_primary=True,
            source_url=main_source_url,
            image_bytes=cached_bytes,
            content_type=cached_content_type,
            image_sha256=main_hash,
        )
    )
    seen_hashes.add(main_hash)
    next_sort_order += 1

    for source_url in image_urls[1:]:
        payload = fetch_remote_image_payload(source_url, city=_normalize_text(fitting_row["city"]))
        if not payload:
            raise SystemExit(f"Unable to validate gallery image: {source_url}")

        image_bytes = payload.get("bytes")
        content_type = _normalize_text(payload.get("content_type"))
        if not image_bytes or not content_type:
            raise SystemExit(f"Gallery image payload is empty: {source_url}")

        detected_content_type = _detect_content_type(image_bytes)
        if detected_content_type and detected_content_type != content_type:
            raise SystemExit(
                "Gallery image content type mismatch: "
                f"stored={content_type}, detected={detected_content_type}"
            )

        image_sha256 = _sha256_hex(image_bytes)
        if image_sha256 in seen_hashes:
            continue

        seen_hashes.add(image_sha256)
        gallery_images.append(
            GalleryImage(
                sort_order=next_sort_order,
                is_primary=False,
                source_url=source_url,
                image_bytes=image_bytes,
                content_type=content_type,
                image_sha256=image_sha256,
            )
        )
        next_sort_order += 1

    return gallery_images


def _gallery_matches_current(
    current_rows: list[sqlite3.Row],
    expected_images: list[GalleryImage],
) -> bool:
    if len(current_rows) != len(expected_images):
        return False

    for index, (current_row, expected_image) in enumerate(zip(current_rows, expected_images)):
        if int(current_row["sort_order"]) != index:
            return False
        if bool(current_row["is_primary"]) != expected_image.is_primary:
            return False
        if _normalize_text(current_row["source_url"]) != expected_image.source_url:
            return False
        if _normalize_text(current_row["image_cached_content_type"]) != expected_image.content_type:
            return False
        if _normalize_text(current_row["image_sha256"]) != expected_image.image_sha256:
            return False

    return True


def _print_gallery_state(rows: list[sqlite3.Row]) -> None:
    print("Current fitting_images rows:")
    if not rows:
        print("  - none")
        return
    for row in rows:
        print(
            "  - "
            f"id={row['id']}, "
            f"sort_order={row['sort_order']}, "
            f"is_primary={bool(row['is_primary'])}, "
            f"source_url={row['source_url']}, "
            f"content_type={row['image_cached_content_type']}, "
            f"sha256={row['image_sha256']}"
        )


def _print_preview(
    *,
    database_path: Path,
    fitting_row: sqlite3.Row,
    image_urls: list[str],
    current_rows: list[sqlite3.Row],
    expected_images: list[GalleryImage],
) -> None:
    print("Mode: DRY-RUN")
    print(f"Database: {database_path}")
    print("Integrity check: ok")
    print(f"Fitting id: {int(fitting_row['id'])}")
    print(f"Article: {fitting_row['article']}")
    print(f"Source: {fitting_row['source']}")
    print(f"Source URL: {fitting_row['source_url']}")
    print(f"Found image URLs: {len(image_urls)}")
    print("Image URLs:")
    for index, url in enumerate(image_urls):
        print(f"  {index}: {url}")
    _print_gallery_state(current_rows)
    print(f"Planned rows: {len(expected_images)}")
    print("Changes needed: " + ("no" if _gallery_matches_current(current_rows, expected_images) else "yes"))
    print("Use --apply to write this gallery.")


def _print_apply_header(*, database_path: Path, fitting_row: sqlite3.Row, image_urls: list[str]) -> None:
    print("Mode: APPLY")
    print(f"Database: {database_path}")
    print("Integrity check: ok")
    print(f"Fitting id: {int(fitting_row['id'])}")
    print(f"Article: {fitting_row['article']}")
    print(f"Source: {fitting_row['source']}")
    print(f"Source URL: {fitting_row['source_url']}")
    print(f"Found image URLs: {len(image_urls)}")


def _insert_gallery_rows(
    connection: sqlite3.Connection,
    *,
    fitting_id: int,
    expected_images: list[GalleryImage],
) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
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
                    image.image_sha256,
                )
                for image in expected_images
            ],
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _validate_apply_prerequisites(
    *,
    fitting_row: sqlite3.Row,
    image_urls: list[str],
    expected_images: list[GalleryImage],
    current_rows: list[sqlite3.Row],
) -> tuple[bool, str | None]:
    if _gallery_matches_current(current_rows, expected_images):
        return True, "Gallery already current"

    if current_rows:
        return False, "Existing fitting_images rows do not match the expected gallery"

    if not image_urls:
        return False, "Parser did not return image_urls"

    if not expected_images:
        return False, "No gallery images were prepared"

    if image_urls[0] != expected_images[0].source_url:
        return False, "Primary gallery image is not aligned with image_urls[0]"

    if len(expected_images) > len(image_urls):
        return False, "Prepared gallery contains more rows than source image_urls"

    if expected_images[0].sort_order != EXPECTED_PRIMARY_SORT_ORDER or not expected_images[0].is_primary:
        return False, "Primary gallery row is not configured correctly"

    if any(image.sort_order != index for index, image in enumerate(expected_images)):
        return False, "Gallery sort_order is not sequential"

    if sum(1 for image in expected_images if image.is_primary) != 1:
        return False, "Gallery must contain exactly one primary image"

    if _normalize_text(fitting_row["source"]) != "viyar":
        return False, "Gallery backfill is supported only for source=viyar"

    return True, None


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run or apply a safe gallery backfill for a single fitting.",
    )
    parser.add_argument("--database", required=True, help="Path to the SQLite database")
    parser.add_argument("--fitting-id", required=True, type=int, help="Fitting id to backfill")
    parser.add_argument("--apply", action="store_true", help="Write gallery rows to the database")
    args = parser.parse_args(argv)

    database_path = _resolve_database_path(args.database)
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    connection = _open_sqlite(database_path, readonly=not args.apply)
    try:
        _integrity_check(connection)
        _require_schema(connection)

        fitting_row = _load_fitting(connection, args.fitting_id)
        if not fitting_row:
            raise SystemExit(f"Fitting not found: {args.fitting_id}")

        article = _normalize_text(fitting_row["article"])
        if not article:
            raise SystemExit("Fitting article is missing")

        if _normalize_text(fitting_row["source"]) != "viyar":
            raise SystemExit("Only Viyar fittings are supported for gallery backfill")

        source_url = _normalize_text(fitting_row["source_url"])
        if not source_url:
            raise SystemExit("Fitting source_url is missing")

        parsed = awaitable_parse_fitting_source_metadata(source_url)
        if not parsed.get("success"):
            raise SystemExit(parsed.get("error") or "Parser failed")

        image_urls = _normalize_image_urls(parsed.get("image_urls"))
        current_rows = _load_gallery_rows(connection, args.fitting_id)
        expected_images = _build_gallery_images(
            fitting_row=fitting_row,
            image_urls=image_urls,
        )

        if not args.apply:
            _print_preview(
                database_path=database_path,
                fitting_row=fitting_row,
                image_urls=image_urls,
                current_rows=current_rows,
                expected_images=expected_images,
            )
            return 0

        _print_apply_header(
            database_path=database_path,
            fitting_row=fitting_row,
            image_urls=image_urls,
        )

        ok, message = _validate_apply_prerequisites(
            fitting_row=fitting_row,
            image_urls=image_urls,
            expected_images=expected_images,
            current_rows=current_rows,
        )
        if not ok:
            print("Database write performed: no")
            raise SystemExit(message)

        if message == "Gallery already current":
            print(message)
            print("Database write performed: no")
            return 0

        _insert_gallery_rows(
            connection,
            fitting_id=args.fitting_id,
            expected_images=expected_images,
        )
        print("Transaction committed: yes")
        print("Database write performed: yes")
        print(f"Inserted rows: {len(expected_images)}")
        print("Gallery already current: no")
        return 0
    finally:
        connection.close()


def awaitable_parse_fitting_source_metadata(source_url: str) -> dict[str, Any]:
    result = parse_fitting_source_metadata(source_url)
    if hasattr(result, "__await__"):
        import asyncio

        return asyncio.run(result)
    return result


if __name__ == "__main__":
    raise SystemExit(run())
