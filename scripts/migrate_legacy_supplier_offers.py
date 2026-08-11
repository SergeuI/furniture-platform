"""Migrate legacy supplier data from fittings into fitting_supplier_offers.

This script is additive and idempotent:
- it never deletes or rewrites fittings rows
- it never changes fitting IDs
- it skips source=NULL rows automatically
- it collapses duplicate VIYAR rows onto the canonical fitting keeper
- it reuses the existing VIYAR supplier seed when present
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_DATABASE_NAME = "furniture_platform.db"
SUPPLIER_CODE = "viyar"
SUPPLIER_NAME = "VIYAR"
DEFAULT_PRIORITY = 100
CANONICAL_TARGET_BY_ARTICLE = {
    "190106": 45,
}
SOURCE_ROW_BY_ARTICLE = {
    "190106": 59,
}

REQUIRED_TABLES = ("suppliers", "fitting_supplier_offers", "fittings")
REQUIRED_FITTING_COLUMNS = (
    "id",
    "catalog_key",
    "article",
    "name",
    "source",
    "price",
    "currency",
    "unit",
    "stock",
    "source_url",
    "parsed_at",
    "price_updated_at",
    "source_payload_json",
    "is_active",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate legacy supplier data from fittings into fitting_supplier_offers.",
    )
    parser.add_argument(
        "--database",
        default=DEFAULT_DATABASE_NAME,
        help="Path to furniture_platform.db.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag the script only prints a dry-run plan.",
    )
    return parser.parse_args()


def _normalize_text(value: Any) -> str | None:
    text = "" if value is None else str(value).strip()
    return text or None


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def _index_exists(connection: sqlite3.Connection, index_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).fetchone()
    return row is not None


def _supplier_lookup(connection: sqlite3.Connection, supplier_code: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT id, code, name, is_active FROM suppliers WHERE lower(trim(code)) = lower(trim(?))",
        (supplier_code,),
    ).fetchone()
    return dict(row) if row is not None else None


def _ensure_supplier(connection: sqlite3.Connection) -> dict[str, Any]:
    supplier = _supplier_lookup(connection, SUPPLIER_CODE)
    if supplier is not None:
        return supplier

    connection.execute(
        """
        INSERT INTO suppliers (code, name, is_active)
        VALUES (?, ?, 1)
        """,
        (SUPPLIER_CODE, SUPPLIER_NAME),
    )
    supplier_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    return {
        "id": supplier_id,
        "code": SUPPLIER_CODE,
        "name": SUPPLIER_NAME,
        "is_active": 1,
    }


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _load_legacy_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            id,
            catalog_key,
            article,
            name,
            source,
            price,
            currency,
            unit,
            stock,
            source_url,
            parsed_at,
            price_updated_at,
            source_payload_json,
            is_active
        FROM fittings
        ORDER BY id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _parse_source_payload_json(value: Any) -> dict[str, Any] | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _payload_source_site(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return _normalize_text(payload.get("source_site"))


def _payload_article(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    parsed_item = payload.get("parsed_item")
    if not isinstance(parsed_item, dict):
        return None
    return _normalize_text(parsed_item.get("article"))


def _build_offer_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "fitting_id": int(row["canonical_fitting_id"]),
        "supplier_code": SUPPLIER_CODE,
        "supplier_id": int(row["supplier_id"]),
        "source_fitting_id": int(row["source_fitting_id"]),
        "article": row["offer_article"],
        "external_product_id": None,
        "source_url": row["source_url"],
        "price": row["price"],
        "currency": row["currency"] or "UAH",
        "unit": row.get("unit") or "шт",
        "stock": row["stock"],
        "is_active": bool(row["is_active"]),
        "priority": DEFAULT_PRIORITY,
        "parsed_at": row["parsed_at"],
        "price_updated_at": row["price_updated_at"],
        "source_payload_json": row["source_payload_json"],
    }


def _build_plan(connection: sqlite3.Connection) -> dict[str, Any]:
    if not all(_table_exists(connection, table_name) for table_name in REQUIRED_TABLES):
        return {
            "prerequisite_missing": True,
            "missing_prerequisites": [
                table_name
                for table_name in REQUIRED_TABLES
                if not _table_exists(connection, table_name)
            ],
            "missing_columns": [],
            "missing_indexes": [],
            "supplier": None,
            "offer_rows": [],
            "planned_offers": [],
            "skipped_rows": [],
            "catalog_key_groups": [],
        }

    missing_columns = [
        column_name
        for column_name in REQUIRED_FITTING_COLUMNS
        if not _column_exists(connection, "fittings", column_name)
    ]
    if missing_columns:
        return {
            "prerequisite_missing": True,
            "missing_prerequisites": ["fittings columns: " + ", ".join(missing_columns)],
            "missing_columns": missing_columns,
            "missing_indexes": [],
            "supplier": None,
            "offer_rows": [],
            "planned_offers": [],
            "skipped_rows": [],
            "catalog_key_groups": [],
        }

    missing_indexes = [
        index_name
        for index_name in (
            "ix_fitting_supplier_offers_fitting_id",
            "ix_fitting_supplier_offers_supplier_id",
            "ix_fitting_supplier_offers_priority",
        )
        if not _index_exists(connection, index_name)
    ]

    supplier = _supplier_lookup(connection, SUPPLIER_CODE)
    rows = _load_legacy_rows(connection)

    candidate_rows = []
    for row in rows:
        source = _normalize_text(row.get("source"))
        source_url = _normalize_text(row.get("source_url"))
        payload = _parse_source_payload_json(row.get("source_payload_json"))
        has_supplier_data = bool(source or source_url or payload)
        if not has_supplier_data:
            continue
        candidate_rows.append(
            {
                **row,
                "_payload": payload,
                "_source": source,
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        article = _normalize_text(row.get("article"))
        if not article:
            continue
        grouped[article].append(row)

    offer_rows: list[dict[str, Any]] = []
    planned_offers: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    catalog_key_groups: list[dict[str, Any]] = []

    for article in sorted(grouped.keys()):
        group_rows = sorted(grouped[article], key=lambda row: int(row["id"]))
        source_rows = [
            row
            for row in group_rows
            if _normalize_text(row.get("_source")) and _normalize_text(row.get("_source")).casefold() == SUPPLIER_CODE
        ]
        if not source_rows:
            for row in group_rows:
                plan_row = {
                    "source_fitting_id": int(row["id"]),
                    "canonical_fitting_id": None,
                    "catalog_key": row["catalog_key"],
                    "name": row["name"],
                    "article": article,
                    "source": row.get("_source"),
                    "price": row["price"],
                    "currency": row["currency"],
                    "unit": row["unit"],
                    "stock": row["stock"],
                    "source_url": row["source_url"],
                    "parsed_at": row["parsed_at"],
                    "price_updated_at": row["price_updated_at"],
                    "source_payload_json": row["source_payload_json"],
                    "payload": "present" if row.get("source_payload_json") else "null",
                    "payload_source_site": _payload_source_site(row["_payload"]),
                    "payload_article": _payload_article(row["_payload"]),
                    "status": "skipped_source_null",
                    "reason": "source is null",
                }
                offer_rows.append(plan_row)
                skipped_rows.append(plan_row)
            continue

        source_row_id = SOURCE_ROW_BY_ARTICLE.get(article)
        if source_row_id is not None:
            source_row = next((row for row in source_rows if int(row["id"]) == source_row_id), None)
        else:
            source_row = None
        if source_row is None:
            source_row = source_rows[0]

        canonical_fitting_id = CANONICAL_TARGET_BY_ARTICLE.get(article, int(source_row["id"]))
        canonical_source_ids = [int(row["id"]) for row in group_rows]
        catalog_key_groups.append(
            {
                "article": article,
                "canonical_fitting_id": canonical_fitting_id,
                "source_fitting_ids": canonical_source_ids,
            }
        )

        for row in group_rows:
            payload = row["_payload"]
            payload_site = _payload_source_site(payload)
            payload_article = _payload_article(payload)
            row_source = _normalize_text(row.get("_source"))
            status = "planned_offer" if int(row["id"]) == int(source_row["id"]) else (
                "skipped_source_null" if row_source is None else "skipped_duplicate"
            )
            reason = (
                "canonical keeper"
                if status == "planned_offer"
                else ("source is null" if row_source is None else f"duplicate of fitting_id={source_row['id']}")
            )
            plan_row = {
                "source_fitting_id": int(row["id"]),
                "canonical_fitting_id": canonical_fitting_id,
                "catalog_key": row["catalog_key"],
                "name": row["name"],
                "article": article,
                "source": row_source,
                "price": row["price"],
                "currency": row["currency"],
                "unit": row["unit"],
                "stock": row["stock"],
                "source_url": row["source_url"],
                "parsed_at": row["parsed_at"],
                "price_updated_at": row["price_updated_at"],
                "source_payload_json": row["source_payload_json"],
                "payload": "present" if row.get("source_payload_json") else "null",
                "payload_source_site": payload_site,
                "payload_article": payload_article,
                "status": status,
                "reason": reason,
            }
            offer_rows.append(plan_row)
            if status == "planned_offer":
                planned_offers.append(
                    {
                        **plan_row,
                        "offer_article": payload_article or article,
                        "supplier_id": supplier["id"] if supplier is not None else None,
                        "is_active": row["is_active"],
                        "external_product_id": None,
                    }
                )
            else:
                skipped_rows.append(plan_row)

    return {
        "prerequisite_missing": False,
        "missing_prerequisites": [],
        "missing_columns": missing_columns,
        "missing_indexes": missing_indexes,
        "supplier": supplier,
        "offer_rows": sorted(offer_rows, key=lambda row: int(row["source_fitting_id"])),
        "planned_offers": planned_offers,
        "skipped_rows": skipped_rows,
        "catalog_key_groups": catalog_key_groups,
    }


def _offer_exists(connection: sqlite3.Connection, fitting_id: int, supplier_id: int, external_product_id: str | None) -> bool:
    if external_product_id is None:
        row = connection.execute(
            """
            SELECT 1
            FROM fitting_supplier_offers
            WHERE fitting_id = ? AND supplier_id = ? AND external_product_id IS NULL
            """,
            (fitting_id, supplier_id),
        ).fetchone()
        return row is not None

    row = connection.execute(
        """
        SELECT 1
        FROM fitting_supplier_offers
        WHERE fitting_id = ? AND supplier_id = ? AND external_product_id = ?
        """,
        (fitting_id, supplier_id, external_product_id),
    ).fetchone()
    return row is not None


def _upsert_offer(connection: sqlite3.Connection, payload: dict[str, Any]) -> None:
    fitting_id = int(payload["fitting_id"])
    supplier_id = int(payload["supplier_id"])
    external_product_id = payload["external_product_id"]

    existing = None
    if external_product_id is None:
        existing = connection.execute(
            """
            SELECT id
            FROM fitting_supplier_offers
            WHERE fitting_id = ? AND supplier_id = ? AND external_product_id IS NULL
            """,
            (fitting_id, supplier_id),
        ).fetchone()
    else:
        existing = connection.execute(
            """
            SELECT id
            FROM fitting_supplier_offers
            WHERE fitting_id = ? AND supplier_id = ? AND external_product_id = ?
            """,
            (fitting_id, supplier_id, external_product_id),
        ).fetchone()

    values = {
        "fitting_id": fitting_id,
        "supplier_id": supplier_id,
        "article": payload["article"],
        "external_product_id": external_product_id,
        "source_url": payload["source_url"],
        "price": payload["price"],
        "currency": payload["currency"],
        "unit": payload["unit"],
        "stock": payload["stock"],
        "is_active": 1 if payload["is_active"] else 0,
        "priority": int(payload["priority"]),
        "parsed_at": payload["parsed_at"],
        "price_updated_at": payload["price_updated_at"],
        "source_payload_json": payload["source_payload_json"],
    }

    if existing is None:
        connection.execute(
            """
            INSERT INTO fitting_supplier_offers (
                fitting_id,
                supplier_id,
                article,
                external_product_id,
                source_url,
                price,
                currency,
                unit,
                stock,
                is_active,
                priority,
                parsed_at,
                price_updated_at,
                source_payload_json
            ) VALUES (
                :fitting_id,
                :supplier_id,
                :article,
                :external_product_id,
                :source_url,
                :price,
                :currency,
                :unit,
                :stock,
                :is_active,
                :priority,
                :parsed_at,
                :price_updated_at,
                :source_payload_json
            )
            """,
            values,
        )
    else:
        values["id"] = int(existing[0])
        connection.execute(
            """
            UPDATE fitting_supplier_offers
            SET
                article = :article,
                external_product_id = :external_product_id,
                source_url = :source_url,
                price = :price,
                currency = :currency,
                unit = :unit,
                stock = :stock,
                is_active = :is_active,
                priority = :priority,
                parsed_at = :parsed_at,
                price_updated_at = :price_updated_at,
                source_payload_json = :source_payload_json
            WHERE id = :id
            """,
            values,
        )


def _apply_plan(connection: sqlite3.Connection, plan: dict[str, Any]) -> None:
    if plan["prerequisite_missing"]:
        raise SystemExit(
            "Missing prerequisite tables or columns: "
            + ", ".join(plan["missing_prerequisites"]) or "unknown"
        )

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")
    try:
        supplier = _ensure_supplier(connection)
        for offer_row in plan["planned_offers"]:
            payload = _build_offer_payload({**offer_row, "supplier_id": supplier["id"]})
            _upsert_offer(connection, payload)
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def _counts_snapshot(connection: sqlite3.Connection) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    for table_name in (
        "fittings",
        "suppliers",
        "fitting_supplier_offers",
        "mounting_node_items",
        "fitting_hole_templates",
        "fitting_images",
    ):
        if _table_exists(connection, table_name):
            counts[table_name] = int(
                connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            )
        else:
            counts[table_name] = None
    return counts


def _offer_rows_after_apply(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            offer.id,
            offer.fitting_id,
            fitting.catalog_key,
            fitting.name AS fitting_name,
            offer.supplier_id,
            supplier.code AS supplier_code,
            offer.article,
            offer.external_product_id,
            offer.source_url,
            offer.price,
            offer.currency,
            offer.unit,
            offer.stock,
            offer.is_active,
            offer.priority,
            offer.parsed_at,
            offer.price_updated_at,
            CASE
                WHEN offer.source_payload_json IS NULL OR trim(offer.source_payload_json) = '' THEN 'null'
                ELSE 'present'
            END AS payload
        FROM fitting_supplier_offers offer
        JOIN fittings fitting ON fitting.id = offer.fitting_id
        JOIN suppliers supplier ON supplier.id = offer.supplier_id
        ORDER BY offer.fitting_id, offer.id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _print_plan(database_path: Path, plan: dict[str, Any], apply: bool, backup_path: Path | None) -> None:
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    if plan["prerequisite_missing"]:
        print("Prerequisites missing:", ", ".join(plan["missing_prerequisites"]) or "unknown")
        return

    print("Missing columns:", ", ".join(plan["missing_columns"]) or "none")
    print("Missing indexes:", ", ".join(plan["missing_indexes"]) or "none")
    print("Supplier seed reused:", "yes" if plan["supplier"] is not None else "no")
    print("Candidate supplier rows:", len(plan["offer_rows"]))
    print("Planned offers:", len(plan["planned_offers"]))
    print("Skipped rows:", len(plan["skipped_rows"]))
    print("Canonical remaps:")
    if plan["catalog_key_groups"]:
        for group in plan["catalog_key_groups"]:
            print(
                "  article=",
                group["article"],
                "canonical_fitting_id=",
                group["canonical_fitting_id"],
                "source_fitting_ids=",
                ",".join(str(item) for item in group["source_fitting_ids"]),
            )
    else:
        print("  none")

    print("Dry-run offer mapping:")
    for row in plan["offer_rows"]:
        print(
            "  row=",
            row["source_fitting_id"],
            "canonical=",
            row["canonical_fitting_id"] if row["canonical_fitting_id"] is not None else "skip",
            "status=",
            row["status"],
            "article=",
            row["article"],
            "name=",
            row["name"],
            "source=",
            row["source"],
            "price=",
            row["price"],
            "currency=",
            row["currency"],
            "stock=",
            row["stock"],
            "source_url=",
            row["source_url"],
            "parsed_at=",
            row["parsed_at"],
            "price_updated_at=",
            row["price_updated_at"],
            "payload=",
            row["payload"],
            "reason=",
            row["reason"],
        )


def _print_apply_result(connection: sqlite3.Connection) -> None:
    print("Post-apply integrity:", connection.execute("PRAGMA integrity_check").fetchone()[0])
    print("Post-apply counts:", json.dumps(_counts_snapshot(connection), ensure_ascii=False, sort_keys=True))
    print("Offers after apply:")
    for row in _offer_rows_after_apply(connection):
        print(
            "  offer_id=",
            row["id"],
            "fitting_id=",
            row["fitting_id"],
            "catalog_key=",
            row["catalog_key"],
            "name=",
            row["fitting_name"],
            "supplier_code=",
            row["supplier_code"],
            "article=",
            row["article"],
            "price=",
            row["price"],
            "currency=",
            row["currency"],
            "stock=",
            row["stock"],
            "is_active=",
            bool(row["is_active"]),
            "priority=",
            row["priority"],
            "payload=",
            row["payload"],
        )


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()

    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        before_counts = _counts_snapshot(connection)
        integrity_before = connection.execute("PRAGMA integrity_check").fetchone()[0]
        plan = _build_plan(connection)
        has_changes = not plan["prerequisite_missing"] and (
            bool(plan["planned_offers"]) or plan["supplier"] is None
        )
        backup_path = _create_backup(database_path) if args.apply and has_changes else None

        print("Integrity before:", integrity_before)
        print("Counts before:", json.dumps(before_counts, ensure_ascii=False, sort_keys=True))

        if args.apply and plan["prerequisite_missing"]:
            _print_plan(database_path, plan, args.apply, backup_path)
            raise SystemExit(1)

        if args.apply and has_changes:
            _apply_plan(connection, plan)

        _print_plan(database_path, plan, args.apply, backup_path)

        if args.apply and has_changes:
            _print_apply_result(connection)


if __name__ == "__main__":
    main()
