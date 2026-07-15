import argparse
import hashlib
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.material_catalog_service import (
    fetch_remote_image_payload,
)


def _backup_database(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _count(connection: sqlite3.Connection, query: str, parameters=()) -> int:
    return int(connection.execute(query, parameters).fetchone()[0])


def _normalize_viyar_image_url(url: str | None) -> str | None:
    if not url:
        return None

    parsed = urlsplit(url)
    if (parsed.hostname or "").lower() != "www.viyar.ua":
        return url

    netloc = "viyar.ua"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    if parsed.username:
        auth = parsed.username
        if parsed.password is not None:
            auth = f"{auth}:{parsed.password}"
        netloc = f"{auth}@{netloc}"

    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def _resolve_database_path(explicit_database: str | None) -> Path:
    if explicit_database:
        return Path(explicit_database).expanduser().resolve()

    env_database = os.environ.get("FURNITURE_PLATFORM_DB_PATH")
    if env_database:
        return Path(env_database).expanduser().resolve()

    return (PROJECT_ROOT / "furniture_platform.db").resolve()


def _fetch_material_by_article(
    connection: sqlite3.Connection,
    article: str,
) -> sqlite3.Row:
    rows = connection.execute(
        """
        SELECT id, article, name, image, source_url, image_cached_bytes,
               image_cached_content_type, image_cached_hash
        FROM materials
        WHERE article = ?
        ORDER BY id
        """,
        (article,),
    ).fetchall()

    if len(rows) != 1:
        raise ValueError(
            f"Expected exactly one materials row for article {article}, found {len(rows)}"
        )

    return rows[0]


def _load_local_jpeg_payload(image_path: Path) -> dict:
    if not image_path.is_file():
        raise ValueError(f"Image file was not found: {image_path}")

    image_bytes = image_path.read_bytes()
    if not image_bytes:
        raise ValueError(f"Image file is empty: {image_path}")

    try:
        from PIL import Image
    except Exception:
        raise ValueError("Pillow is required to validate --image-file JPEG payloads")
    else:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                if (image.format or "").upper() != "JPEG":
                    raise ValueError(f"Image file is not a JPEG: {image_path}")
        except Exception as exc:
            raise ValueError(f"Image file is not a valid JPEG: {image_path} ({exc})") from exc

    return {
        "bytes": image_bytes,
        "content_type": "image/jpeg",
        "sha256": hashlib.sha256(image_bytes).hexdigest(),
    }


def _build_point_image_payload(
    row: sqlite3.Row,
    image_file: str | None,
    city: str | None,
) -> dict:
    if image_file:
        image_path = Path(image_file).expanduser()
        payload = _load_local_jpeg_payload(image_path)
        return {
            "source": "file",
            "image_file": str(image_path.resolve()),
            "bytes": payload["bytes"],
            "content_type": payload["content_type"],
            "sha256": payload["sha256"],
        }

    image_url = row["image"]
    payload = fetch_remote_image_payload(image_url, city=city)
    if not payload:
        raise ValueError(
            f"Remote image could not be loaded for article {row['article']}"
        )

    return {
        "source": "remote",
        "image_file": None,
        "bytes": payload["bytes"],
        "content_type": payload["content_type"],
        "sha256": hashlib.sha256(payload["bytes"]).hexdigest(),
    }


def _point_image_change_fields(
    row: sqlite3.Row,
    payload: dict,
) -> list[str]:
    current_bytes = row["image_cached_bytes"]
    current_content_type = row["image_cached_content_type"]
    current_hash = row["image_cached_hash"]

    changed_fields: list[str] = []

    if current_bytes != payload["bytes"]:
        changed_fields.append("image_cached_bytes")
    if current_content_type != payload["content_type"]:
        changed_fields.append("image_cached_content_type")
    if current_hash != payload["sha256"]:
        changed_fields.append("image_cached_hash")

    return changed_fields


def _print_point_image_preview(
    database_path: Path,
    row: sqlite3.Row,
    payload: dict,
    changed_fields: list[str],
    can_write: bool,
) -> None:
    current_bytes = row["image_cached_bytes"] or b""
    current_size = len(current_bytes)
    new_size = len(payload["bytes"])
    existing_image = row["image_cached_bytes"] is not None and len(row["image_cached_bytes"]) > 0

    print(f"Database path: {database_path}")
    print(f"Article: {row['article']}")
    print(f"Name: {row['name']}")
    print(f"Image source: {payload['source']}")
    if payload["image_file"]:
        print(f"Image file: {payload['image_file']}")
    print(f"Current BLOB size: {current_size}")
    print(f"New BLOB size: {new_size}")
    print(f"Content type: {payload['content_type']}")
    print(f"SHA-256: {payload['sha256']}")
    print(f"Fields to change: {', '.join(changed_fields) if changed_fields else 'none'}")
    print(f"Existing image already present: {'yes' if existing_image else 'no'}")
    if existing_image and not can_write:
        print("Replacement blocked: existing image is protected without --replace-existing-image")
    print("Database write performed: no")


def _apply_point_image_update(
    connection: sqlite3.Connection,
    article: str,
    payload: dict,
) -> None:
    connection.execute(
        """
        UPDATE materials
        SET image_cached_bytes = ?, image_cached_content_type = ?, image_cached_hash = ?
        WHERE article = ?
        """,
        (payload["bytes"], payload["content_type"], payload["sha256"], article),
    )


def _verify_point_image_update(
    connection: sqlite3.Connection,
    article: str,
    payload: dict,
) -> None:
    row = connection.execute(
        """
        SELECT image_cached_bytes, image_cached_content_type, image_cached_hash
        FROM materials
        WHERE article = ?
        """,
        (article,),
    ).fetchone()

    if row is None:
        raise ValueError(f"Material disappeared after update for article {article}")

    if len(row["image_cached_bytes"] or b"") != len(payload["bytes"]):
        raise ValueError(f"Post-update BLOB size mismatch for article {article}")

    if row["image_cached_content_type"] != payload["content_type"]:
        raise ValueError(f"Post-update content type mismatch for article {article}")

    if row["image_cached_hash"] != payload["sha256"]:
        raise ValueError(f"Post-update SHA-256 mismatch for article {article}")


def _run_point_image_mode(
    connection: sqlite3.Connection,
    database_path: Path,
    article: str,
    image_file: str | None,
    city: str | None,
    apply_changes: bool,
    replace_existing_image: bool,
) -> int:
    row = _fetch_material_by_article(connection, article)
    existing_image = row["image_cached_bytes"] is not None and len(row["image_cached_bytes"]) > 0
    if existing_image and not replace_existing_image and not image_file:
        payload = {
            "source": "existing",
            "image_file": None,
            "bytes": row["image_cached_bytes"] or b"",
            "content_type": row["image_cached_content_type"] or "",
            "sha256": row["image_cached_hash"] or hashlib.sha256(row["image_cached_bytes"] or b"").hexdigest(),
        }
        changed_fields: list[str] = []
    else:
        payload = _build_point_image_payload(row, image_file, city)
        changed_fields = _point_image_change_fields(row, payload)
    can_write = apply_changes and (not existing_image or replace_existing_image)

    _print_point_image_preview(database_path, row, payload, changed_fields, can_write)

    if not apply_changes:
        return 0

    if existing_image and not replace_existing_image:
        return 0

    if not changed_fields:
        return 0

    backup_path = _backup_database(database_path)
    print(f"Backup: {backup_path}")
    connection.execute("BEGIN")
    _apply_point_image_update(connection, article, payload)
    _verify_point_image_update(connection, article, payload)
    connection.commit()
    print("Database write performed: yes")
    return 0


def _restore_catalog_visibility(connection: sqlite3.Connection) -> dict:
    service_filter = """
        source = 'viyar'
        AND is_active = 0
        AND (
            item_type = 'folder'
            OR NULLIF(TRIM(COALESCE(article, '')), '') IS NOT NULL
            OR base_price IS NOT NULL
            OR NULLIF(TRIM(COALESCE(source_url, '')), '') IS NOT NULL
        )
    """
    material_filter = """
        owner_user_id IS NULL
        AND is_default = 0
        AND NULLIF(TRIM(COALESCE(source_url, '')), '') IS NOT NULL
    """

    result = {
        "viyar_items_reactivated": _count(
            connection,
            f"SELECT COUNT(*) FROM service_catalog_items WHERE {service_filter}",
        ),
        "shared_materials_promoted": _count(
            connection,
            f"SELECT COUNT(*) FROM materials WHERE {material_filter}",
        ),
    }

    connection.execute(
        f"UPDATE service_catalog_items SET is_active = 1 WHERE {service_filter}"
    )
    connection.execute(
        f"UPDATE materials SET is_default = 1 WHERE {material_filter}"
    )
    return result


def _reuse_cached_images(connection: sqlite3.Connection) -> dict:
    result = {"materials": 0, "edges": 0, "fittings": 0}
    definitions = (
        ("materials", "image", "materials"),
        ("material_edge_options", "image", "edges"),
        ("fittings", "image_url", "fittings"),
    )

    for table_name, image_column, result_key in definitions:
        rows = connection.execute(
            f"""
            SELECT target.id, source.image_cached_bytes, source.image_cached_content_type
            FROM {table_name} AS target
            JOIN {table_name} AS source
              ON source.{image_column} = target.{image_column}
             AND source.id != target.id
             AND source.image_cached_bytes IS NOT NULL
            WHERE target.image_cached_bytes IS NULL
              AND NULLIF(TRIM(COALESCE(target.{image_column}, '')), '') IS NOT NULL
            GROUP BY target.id
            """
        ).fetchall()
        for item_id, image_bytes, content_type in rows:
            connection.execute(
                f"""
                UPDATE {table_name}
                SET image_cached_bytes = ?, image_cached_content_type = ?
                WHERE id = ?
                """,
                (image_bytes, content_type, item_id),
            )
        result[result_key] = len(rows)

    return result


def _fetch_missing_image_targets(
    connection: sqlite3.Connection,
    table_name: str,
    id_column: str,
    preview_columns: tuple[str, ...],
    where_clause: str,
) -> list[dict]:
    columns = ", ".join((id_column, *preview_columns))
    rows = connection.execute(
        f"""
        SELECT {columns}
        FROM {table_name}
        WHERE {where_clause}
        ORDER BY {id_column}
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _print_image_preview(label: str, rows: list[dict]) -> None:
    print(f"{label}: {len(rows)}")
    for row in rows:
        identifier = row.get("article") if row.get("article") is not None else row.get("id")
        image_value = row.get("image") or row.get("image_url")
        print(
            f"  - {identifier}: "
            f"source_url={row.get('source_url') or ''}, "
            f"image={image_value or ''}"
        )


def _images_only_preview(connection: sqlite3.Connection) -> dict[str, list[dict]]:
    materials = _fetch_missing_image_targets(
        connection,
        "materials",
        "article",
        ("article", "name", "source", "source_url", "image", "image_source_url", "image_cached_hash"),
        "image_cached_bytes IS NULL",
    )
    edges = _fetch_missing_image_targets(
        connection,
        "material_edge_options",
        "id",
        ("id", "material_article", "edge_key", "article", "name", "source_url", "image", "image_source_url", "image_cached_hash"),
        "image_cached_bytes IS NULL",
    )
    fittings = _fetch_missing_image_targets(
        connection,
        "fittings",
        "id",
        ("id", "image_url", "city", "image_cached_bytes"),
        "image_cached_bytes IS NULL",
    )
    return {
        "materials": materials,
        "edges": edges,
        "fittings": fittings,
    }


def _warm_material_images_images_only(
    connection: sqlite3.Connection,
    city: str | None,
) -> dict:
    preview = _images_only_preview(connection)
    result = {
        "materials": 0,
        "edges": 0,
        "fittings": 0,
        "failed": 0,
        "skipped": 0,
        "preview": preview,
    }

    for row in preview["materials"]:
        article = row["article"]
        image = row.get("image")
        if not image:
            result["skipped"] += 1
            continue
        normalized_image = _normalize_viyar_image_url(image)
        if normalized_image != image:
            print("Normalized image host: www.viyar.ua -> viyar.ua")
        payload = fetch_remote_image_payload(normalized_image, city=city)
        if not payload:
            result["failed"] += 1
            continue
        connection.execute(
            """
            UPDATE materials
            SET image_cached_bytes = ?, image_cached_content_type = ?
            WHERE article = ?
            """,
            (payload["bytes"], payload["content_type"], article),
        )
        result["materials"] += 1

    for row in preview["edges"]:
        item_id = row["id"]
        image = row.get("image")
        if not image:
            result["skipped"] += 1
            continue
        normalized_image = _normalize_viyar_image_url(image)
        if normalized_image != image:
            print("Normalized image host: www.viyar.ua -> viyar.ua")
        payload = fetch_remote_image_payload(normalized_image, city=city)
        if not payload:
            result["failed"] += 1
            continue
        connection.execute(
            """
            UPDATE material_edge_options
            SET image_cached_bytes = ?, image_cached_content_type = ?
            WHERE id = ?
            """,
            (payload["bytes"], payload["content_type"], item_id),
        )
        result["edges"] += 1

    for row in preview["fittings"]:
        item_id = row["id"]
        image_url = row.get("image_url")
        item_city = row.get("city")
        if not image_url:
            result["skipped"] += 1
            continue
        normalized_image_url = _normalize_viyar_image_url(image_url)
        if normalized_image_url != image_url:
            print("Normalized image host: www.viyar.ua -> viyar.ua")
        payload = fetch_remote_image_payload(normalized_image_url, city=item_city or city)
        if not payload:
            result["failed"] += 1
            continue
        connection.execute(
            """
            UPDATE fittings
            SET image_cached_bytes = ?, image_cached_content_type = ?
            WHERE id = ?
            """,
            (payload["bytes"], payload["content_type"], item_id),
        )
        result["fittings"] += 1

    return result


def _warm_material_images(
    connection: sqlite3.Connection,
    city: str | None,
) -> dict:
    reused = _reuse_cached_images(connection)
    result = {
        "materials": 0,
        "edges": 0,
        "fittings": 0,
        "failed": 0,
        "reused": reused,
    }

    materials = connection.execute(
        """
        SELECT article, image, source_url
        FROM materials
        WHERE image_cached_bytes IS NULL
          AND NULLIF(TRIM(COALESCE(article, '')), '') IS NOT NULL
          AND (
              NULLIF(TRIM(COALESCE(source_url, '')), '') IS NOT NULL
              OR image LIKE 'http%'
          )
        """
    ).fetchall()
    for article, image, source_url in materials:
        payload = fetch_remote_image_payload(image, city=city)
        if not payload:
            result["failed"] += 1
            continue
        connection.execute(
            """
            UPDATE materials
            SET image_cached_bytes = ?, image_cached_content_type = ?
            WHERE article = ?
            """,
            (payload["bytes"], payload["content_type"], article),
        )
        result["materials"] += 1

    edges = connection.execute(
        """
        SELECT id, article, image, source_url
        FROM material_edge_options
        WHERE image_cached_bytes IS NULL
          AND NULLIF(TRIM(COALESCE(article, '')), '') IS NOT NULL
          AND (
              NULLIF(TRIM(COALESCE(source_url, '')), '') IS NOT NULL
              OR image LIKE 'http%'
          )
        """
    ).fetchall()
    for item_id, article, image, source_url in edges:
        payload = fetch_remote_image_payload(image, city=city)
        if not payload:
            result["failed"] += 1
            continue
        connection.execute(
            """
            UPDATE material_edge_options
            SET image_cached_bytes = ?, image_cached_content_type = ?
            WHERE id = ?
            """,
            (payload["bytes"], payload["content_type"], item_id),
        )
        result["edges"] += 1

    fittings = connection.execute(
        """
        SELECT id, image_url, city
        FROM fittings
        WHERE image_cached_bytes IS NULL
          AND NULLIF(TRIM(COALESCE(image_url, '')), '') IS NOT NULL
        """
    ).fetchall()
    for item_id, image_url, item_city in fittings:
        payload = fetch_remote_image_payload(image_url, city=item_city or city)
        if not payload:
            result["failed"] += 1
            continue
        connection.execute(
            """
            UPDATE fittings
            SET image_cached_bytes = ?, image_cached_content_type = ?
            WHERE id = ?
            """,
            (payload["bytes"], payload["content_type"], item_id),
        )
        result["fittings"] += 1

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair persisted catalog visibility and optionally cache images in SQLite."
    )
    parser.add_argument("--database", default=None)
    parser.add_argument("--city", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--warm-images", action="store_true")
    parser.add_argument("--images-only", action="store_true")
    parser.add_argument("--article", default=None)
    parser.add_argument("--image-file", default=None)
    parser.add_argument("--replace-existing-image", action="store_true")
    args = parser.parse_args()

    if args.article and not args.images_only:
        parser.error("--article can only be used together with --images-only")
    if args.image_file and not (args.images_only and args.article):
        parser.error("--image-file can only be used together with --images-only and --article")
    if args.replace_existing_image and not (args.images_only and args.article and args.image_file):
        parser.error(
            "--replace-existing-image can only be used together with --images-only, --article and --image-file"
        )

    database_path = _resolve_database_path(args.database)
    if not database_path.is_file():
        raise SystemExit(f"Database was not found: {database_path}")

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        exit_code = 0
        image_result = None
        reused_images = None
        visibility = None

        if args.images_only and args.article:
            try:
                exit_code = _run_point_image_mode(
                    connection,
                    database_path,
                    args.article,
                    args.image_file,
                    args.city,
                    args.apply,
                    args.replace_existing_image,
                )
            except Exception as exc:
                try:
                    connection.rollback()
                except Exception:
                    pass
                print(f"Error: {exc}", file=sys.stderr)
                print("Database write performed: no")
                exit_code = 1
        elif args.images_only:
            preview = _images_only_preview(connection)

            if not args.apply:
                print("DRY RUN - no database changes were saved")
                _print_image_preview("Materials without BLOB", preview["materials"])
                _print_image_preview("Material edge options without BLOB", preview["edges"])
                if args.warm_images:
                    _print_image_preview("Fittings without BLOB", preview["fittings"])
            else:
                backup_path = _backup_database(database_path)
                connection.execute("BEGIN")
                if args.warm_images:
                    image_result = _warm_material_images_images_only(connection, args.city)
                connection.commit()
                print(f"Backup: {backup_path}")

            print(f"Materials without BLOB: {len(preview['materials'])}")
            print(f"Material edge options without BLOB: {len(preview['edges'])}")
            if args.warm_images:
                print(f"Fittings without BLOB: {len(preview['fittings'])}")

            if image_result is not None:
                print(
                    "Image cache: "
                    f"materials={image_result['materials']}, "
                    f"edges={image_result['edges']}, "
                    f"fittings={image_result['fittings']}, "
                    f"failed={image_result['failed']}, "
                    f"skipped={image_result['skipped']}"
                )
                print(
                    "Image cache reused: "
                    f"materials={image_result.get('reused', {}).get('materials', 0) if image_result.get('reused') else 0}, "
                    f"edges={image_result.get('reused', {}).get('edges', 0) if image_result.get('reused') else 0}, "
                    f"fittings={image_result.get('reused', {}).get('fittings', 0) if image_result.get('reused') else 0}"
                )
                if args.apply and image_result["failed"] > 0:
                    print(f"Image backfill completed with errors: failed={image_result['failed']}")
                    exit_code = 1
        else:
            connection.execute("BEGIN")
            visibility = _restore_catalog_visibility(connection)
            reused_images = None

            if not args.apply:
                connection.rollback()
                print("DRY RUN - no database changes were saved")
            else:
                connection.rollback()
                backup_path = _backup_database(database_path)
                connection.execute("BEGIN")
                visibility = _restore_catalog_visibility(connection)
                reused_images = _reuse_cached_images(connection)
                if args.warm_images:
                    image_result = _warm_material_images(connection, args.city)
                connection.commit()
                print(f"Backup: {backup_path}")

            print(f"Viyar items to reactivate: {visibility['viyar_items_reactivated']}")
            print(f"Shared parsed materials to expose: {visibility['shared_materials_promoted']}")
            if reused_images is not None:
                print(
                    "Image cache reused before download: "
                    f"materials={reused_images['materials']}, "
                    f"edges={reused_images['edges']}, "
                    f"fittings={reused_images['fittings']}"
                )
            if image_result is not None:
                print(
                    "Image cache: "
                    f"materials={image_result['materials']}, "
                    f"edges={image_result['edges']}, "
                    f"fittings={image_result['fittings']}, "
                    f"failed={image_result['failed']}"
                )
                print(
                    "Image cache reused: "
                    f"materials={image_result['reused']['materials']}, "
                    f"edges={image_result['reused']['edges']}, "
                    f"fittings={image_result['reused']['fittings']}"
                )
    finally:
        connection.close()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
