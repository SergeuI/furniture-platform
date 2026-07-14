"""Safe price-only refresh for a single material row.

This CLI reads the current material and price row from the main SQLite database
in read-only mode, fetches the latest Viyar price from a direct product URL, and
optionally writes only the price row when --apply is provided.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.repositories.inventory_repository import upsert_material_price
from services.material_catalog_service import fetch_material_price_by_url
from services.legacy_db_config import DEFAULT_DB_PATH


ALLOWED_CITY = "kyiv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and optionally store a single material price from Viyar.",
    )
    parser.add_argument(
        "--article",
        required=True,
        help="Material article to refresh.",
    )
    parser.add_argument(
        "--city",
        required=True,
        help="City code. For this first version only kyiv is supported.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the refreshed price row back to the database.",
    )
    return parser.parse_args()


def _resolve_database_path() -> Path:
    database_path = Path(DEFAULT_DB_PATH).resolve()
    print(f"Resolved database path: {database_path}")
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")
    return database_path


def _open_readonly_connection(database_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)


def _normalize_city(city: str) -> str:
    normalized = (city or "").strip().lower()
    if normalized != ALLOWED_CITY:
        raise SystemExit(
            "Controlled error: this first version supports only city=kyiv. "
            "Prices for other cities have not been checked yet."
        )
    return normalized


def _is_viyar_url(source_url: str | None) -> bool:
    if not source_url:
        return False
    parsed = urlparse(source_url)
    host = (parsed.netloc or "").lower()
    return host.endswith("viyar.ua")


def _read_material_snapshot(
    connection: sqlite3.Connection,
    *,
    article: str,
    city: str,
) -> dict:
    connection.row_factory = sqlite3.Row
    cur = connection.cursor()

    material_row = cur.execute(
        """
        SELECT
            article,
            name,
            source,
            source_url,
            length(image_cached_bytes) AS image_cached_bytes_len
        FROM materials
        WHERE article = ?
        """,
        (article,),
    ).fetchone()
    if not material_row:
        raise SystemExit(f"Controlled error: material was not found for article={article}")

    price_row = cur.execute(
        """
        SELECT
            price,
            currency,
            availability,
            old_price,
            is_promo,
            discount_percent,
            promo_label,
            promo_valid_until,
            source_checked_at,
            updated_at
        FROM material_prices
        WHERE article = ? AND city = ?
        """,
        (article, city),
    ).fetchone()

    source_url = material_row["source_url"]
    if not source_url:
        raise SystemExit(
            f"Controlled error: source_url is missing for article={article}. "
            "No external fetch will be performed."
        )
    if not _is_viyar_url(source_url):
        raise SystemExit(
            f"Controlled error: source_url does not belong to viyar.ua for article={article}."
        )

    return {
        "material": {
            "article": material_row["article"],
            "name": material_row["name"],
            "source": material_row["source"],
            "source_url": material_row["source_url"],
            "image_cached_bytes_len": material_row["image_cached_bytes_len"],
        },
        "price": None if price_row is None else {
            "price": price_row["price"],
            "currency": price_row["currency"],
            "availability": price_row["availability"],
            "old_price": price_row["old_price"],
            "is_promo": bool(price_row["is_promo"]) if price_row["is_promo"] is not None else False,
            "discount_percent": price_row["discount_percent"],
            "promo_label": price_row["promo_label"],
            "promo_valid_until": price_row["promo_valid_until"],
            "source_checked_at": price_row["source_checked_at"],
            "updated_at": price_row["updated_at"],
        },
    }


def _convert_promo_valid_until(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise SystemExit(f"Controlled error: invalid promo_valid_until value: {value!r}") from exc


def _print_before(snapshot: dict) -> None:
    print("BEFORE:")
    print(f"  article: {snapshot['material']['article']}")
    print(f"  name: {snapshot['material']['name']}")
    print(f"  source: {snapshot['material']['source']}")
    print(f"  source_url: {snapshot['material']['source_url']}")
    print(f"  image_cached_bytes_len: {snapshot['material']['image_cached_bytes_len']}")
    print("  material_prices:")
    print(f"    price: {snapshot['price']['price'] if snapshot['price'] else None}")
    print(f"    currency: {snapshot['price']['currency'] if snapshot['price'] else None}")
    print(f"    availability: {snapshot['price']['availability'] if snapshot['price'] else None}")
    print(f"    old_price: {snapshot['price']['old_price'] if snapshot['price'] else None}")
    print(f"    is_promo: {snapshot['price']['is_promo'] if snapshot['price'] else False}")
    print(f"    discount_percent: {snapshot['price']['discount_percent'] if snapshot['price'] else None}")
    print(f"    promo_label: {snapshot['price']['promo_label'] if snapshot['price'] else None}")
    print(f"    promo_valid_until: {snapshot['price']['promo_valid_until'] if snapshot['price'] else None}")
    print(f"    source_checked_at: {snapshot['price']['source_checked_at'] if snapshot['price'] else None}")
    print(f"    updated_at: {snapshot['price']['updated_at'] if snapshot['price'] else None}")


def _print_fetched(fetched: dict) -> None:
    print("FETCHED:")
    print(f"  price: {fetched['price']}")
    print(f"  old_price: {fetched['old_price']}")
    print(f"  currency: {fetched['currency']}")
    print(f"  availability: {fetched['availability']}")
    print(f"  unit: {fetched['unit']}")
    print(f"  is_promo: {fetched['is_promo']}")
    print(f"  discount_percent: {fetched['discount_percent']}")
    print(f"  promo_label: {fetched['promo_label']}")
    print(f"  promo_valid_until: {fetched['promo_valid_until']}")
    print(f"  final_url: {fetched['final_url']}")


def _print_would_write(
    *,
    article: str,
    city: str,
    fetched: dict,
    source_checked_at: datetime,
) -> None:
    promo_valid_until = _convert_promo_valid_until(fetched.get("promo_valid_until"))
    print("WOULD WRITE:")
    print(f"  article: {article}")
    print(f"  city: {city}")
    print(f"  price: {fetched.get('price')}")
    print(f"  currency: {fetched.get('currency')}")
    print(f"  availability: {fetched.get('availability')}")
    print(f"  old_price: {fetched.get('old_price')}")
    print(f"  is_promo: {fetched.get('is_promo')}")
    print(f"  discount_percent: {fetched.get('discount_percent')}")
    print(f"  promo_label: {fetched.get('promo_label')}")
    print(f"  promo_valid_until: {promo_valid_until}")
    print(f"  source_checked_at: {source_checked_at}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    article = (args.article or "").strip()
    city = _normalize_city(args.city)

    database_path = _resolve_database_path()
    before_size = database_path.stat().st_size
    before_mtime = database_path.stat().st_mtime

    with _open_readonly_connection(database_path) as connection:
        snapshot = _read_material_snapshot(connection, article=article, city=city)

    _print_before(snapshot)

    fetched = fetch_material_price_by_url(snapshot["material"]["source_url"])
    _print_fetched(fetched)

    source_checked_at = datetime.utcnow()

    if not args.apply:
        _print_would_write(
            article=article,
            city=city,
            fetched=fetched,
            source_checked_at=source_checked_at,
        )
        print("Mode: DRY-RUN")
        print("Database write performed: no")
        print("Writer invoked: no")
        print("External fetch performed: yes")
        return 0

    try:
        promo_valid_until = _convert_promo_valid_until(fetched.get("promo_valid_until"))
    except SystemExit:
        raise

    upsert_material_price(
        article=article,
        city=city,
        price=fetched.get("price"),
        currency=fetched.get("currency"),
        availability=fetched.get("availability"),
        old_price=fetched.get("old_price"),
        is_promo=fetched.get("is_promo"),
        discount_percent=fetched.get("discount_percent"),
        promo_label=fetched.get("promo_label"),
        promo_valid_until=promo_valid_until,
        source_checked_at=source_checked_at,
    )

    print("Mode: APPLY")
    print("Database write performed: yes")
    print("Writer invoked: yes")
    print(f"Database size before: {before_size}")
    print(f"Database mtime before: {before_mtime}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
