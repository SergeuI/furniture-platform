from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_DB_PATH = PROJECT_ROOT / "furniture_platform.db"
DEFAULT_JSON_PATH = PROJECT_ROOT / "reports" / "viyar_service_duplicates_audit.json"
DEFAULT_CSV_PATH = PROJECT_ROOT / "reports" / "viyar_service_duplicates_audit.csv"


CATEGORY_LABELS = {
    "drilling": "Свердління",
    "edgebanding": "Кромкування / Крайкування",
    "cutting": "Порізка",
    "milling": "Фрезерування",
    "other": "Інші",
}


@dataclass
class DuplicateRow:
    article: str
    service_catalog_item_id: str
    name: str
    folder_path: str
    category: str
    source_url: str
    base_price: float | None
    is_active: bool
    is_calculable: bool
    description_length: int
    full_description_length: int
    rules_parse_status: str
    rules_parse_status_group: str
    article_group_size: int
    article_group_rank: int
    duplicate_types: list[str]
    problem_reason: str
    duplicate_kind: str
    source_variant_count: int
    full_description_preview: str


def _normalize_text(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _extract_category(folder_path: str | None) -> str:
    normalized = _normalize_text(folder_path).lower()
    if "prisadka" in normalized:
        return "drilling"
    if "pokleyka_krivolineynaya" in normalized or "pokleyka" in normalized:
        return "edgebanding"
    if "porezka" in normalized:
        return "cutting"
    if "frezerovka" in normalized:
        return "milling"
    return "other"


def _format_price(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = _normalize_text(value)
    if not text:
        return None

    try:
        return float(Decimal(text.replace(" ", "").replace(",", ".")))
    except (InvalidOperation, ValueError):
        return None


def _price_key(value: float | None) -> str:
    if value is None:
        return "none"
    if value.is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _truncate(value: str | None, limit: int = 300) -> str:
    text = _normalize_text(value)
    return text[:limit]


def _load_active_service_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    return list(
        connection.execute(
            """
            SELECT
                id,
                article,
                name,
                folder_path,
                source_url,
                base_price,
                is_active,
                is_calculable,
                description,
                full_description,
                rules_parse_status
            FROM service_catalog_items
            WHERE source = 'viyar'
              AND item_type = 'service'
              AND is_active = 1
              AND article IS NOT NULL
              AND TRIM(article) <> ''
            ORDER BY article, folder_path, sort_order, name, id
            """
        )
    )


def _group_rows_by_article(rows: list[sqlite3.Row]) -> dict[str, list[sqlite3.Row]]:
    grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[_normalize_text(row["article"])].append(row)
    return dict(sorted(grouped.items(), key=lambda item: (len(item[0]), item[0])))


def _classify_group(rows: list[sqlite3.Row]) -> tuple[list[str], str]:
    normalized_names = {_normalize_text(row["name"]).lower() for row in rows}
    categories = {_extract_category(row["folder_path"]) for row in rows}
    prices = {_price_key(_format_price(row["base_price"])) for row in rows}
    statuses = {_normalize_text(row["rules_parse_status"]).lower() for row in rows}
    source_urls = {_normalize_text(row["source_url"]) for row in rows}
    descriptions = {_normalize_text(row["description"]) for row in rows}
    full_descriptions = {_normalize_text(row["full_description"]) for row in rows}

    duplicate_types: list[str] = []
    if len(normalized_names) == 1 and len(prices) == 1:
        duplicate_types.append("same_article_same_name_same_price")
    if len(normalized_names) > 1:
        duplicate_types.append("same_article_different_name")
    if len(categories) > 1:
        duplicate_types.append("same_article_different_category")
    if len(prices) > 1:
        duplicate_types.append("same_article_different_price")
    if len(source_urls) > 1:
        duplicate_types.append("same_article_different_source_url")

    stale_signals = 0
    if any(status in {"needs_review", "no_full_description", "failed"} for status in statuses):
        stale_signals += 1
    if len(descriptions) > 1 or len(full_descriptions) > 1:
        stale_signals += 1
    if len(source_urls) > 1:
        stale_signals += 1
    if len(normalized_names) > 1 or len(categories) > 1 or len(prices) > 1:
        stale_signals += 1

    if stale_signals >= 2:
        duplicate_types.append("службовий/старий дубль")

    if not duplicate_types:
        duplicate_types.append("same_article_variants")

    if len(normalized_names) == 1 and len(categories) == 1 and len(prices) == 1:
        duplicate_kind = "identical"
    elif len(normalized_names) > 1 and len(prices) > 1:
        duplicate_kind = "mixed_name_and_price"
    elif len(normalized_names) > 1:
        duplicate_kind = "name_variant"
    elif len(categories) > 1:
        duplicate_kind = "category_variant"
    elif len(prices) > 1:
        duplicate_kind = "price_variant"
    else:
        duplicate_kind = "old_or_service_variant"

    return duplicate_types, duplicate_kind


def _build_duplicate_rows(rows_by_article: dict[str, list[sqlite3.Row]]) -> tuple[list[DuplicateRow], list[dict[str, Any]]]:
    duplicate_rows: list[DuplicateRow] = []
    group_summaries: list[dict[str, Any]] = []

    for article, rows in rows_by_article.items():
        if len(rows) < 2:
            continue

        duplicate_types, duplicate_kind = _classify_group(rows)
        source_variant_count = len({_normalize_text(row["source_url"]) for row in rows})
        name_values = [_normalize_text(row["name"]) for row in rows]
        price_values = [_price_key(_format_price(row["base_price"])) for row in rows]
        category_values = [_extract_category(row["folder_path"]) for row in rows]
        status_values = [_normalize_text(row["rules_parse_status"]).lower() for row in rows]

        group_summaries.append(
            {
                "article": article,
                "duplicate_rows": len(rows),
                "duplicate_types": duplicate_types,
                "duplicate_kind": duplicate_kind,
                "categories": sorted(set(category_values)),
                "names": sorted(set(name_values)),
                "prices": sorted(set(price_values)),
                "rules_parse_statuses": sorted(set(status_values)),
                "source_variant_count": source_variant_count,
            }
        )

        for index, row in enumerate(rows, start=1):
            duplicate_rows.append(
                DuplicateRow(
                    article=article,
                    service_catalog_item_id=_normalize_text(row["id"]),
                    name=_normalize_text(row["name"]),
                    folder_path=_normalize_text(row["folder_path"]),
                    category=_extract_category(row["folder_path"]),
                    source_url=_normalize_text(row["source_url"]),
                    base_price=_format_price(row["base_price"]),
                    is_active=bool(row["is_active"]),
                    is_calculable=bool(row["is_calculable"]),
                    description_length=len(_normalize_text(row["description"])),
                    full_description_length=len(_normalize_text(row["full_description"])),
                    rules_parse_status=_normalize_text(row["rules_parse_status"]).lower(),
                    rules_parse_status_group=(
                        _normalize_text(row["rules_parse_status"]).lower() or "empty"
                    ),
                    article_group_size=len(rows),
                    article_group_rank=index,
                    duplicate_types=duplicate_types,
                    problem_reason="; ".join(duplicate_types),
                    duplicate_kind=duplicate_kind,
                    source_variant_count=source_variant_count,
                    full_description_preview=_truncate(row["full_description"]),
                )
            )

    duplicate_rows.sort(
        key=lambda item: (
            len(item.article),
            item.article,
            item.article_group_rank,
            item.service_catalog_item_id,
        )
    )
    group_summaries.sort(key=lambda item: (len(item["article"]), item["article"]))
    return duplicate_rows, group_summaries


def _write_csv(csv_path: Path, duplicate_rows: list[DuplicateRow]) -> None:
    fieldnames = list(asdict(duplicate_rows[0]).keys()) if duplicate_rows else [
        "article",
        "service_catalog_item_id",
        "name",
        "folder_path",
        "category",
        "source_url",
        "base_price",
        "is_active",
        "is_calculable",
        "description_length",
        "full_description_length",
        "rules_parse_status",
        "rules_parse_status_group",
        "article_group_size",
        "article_group_rank",
        "duplicate_types",
        "problem_reason",
        "duplicate_kind",
        "source_variant_count",
    ]

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in duplicate_rows:
            item = asdict(row)
            item["duplicate_types"] = " | ".join(item["duplicate_types"])
            writer.writerow(item)


def _build_report(rows: list[sqlite3.Row]) -> dict[str, Any]:
    rows_by_article = _group_rows_by_article(rows)
    duplicate_rows, group_summaries = _build_duplicate_rows(rows_by_article)

    duplicate_article_count = len(group_summaries)
    duplicate_row_count = len(duplicate_rows)
    duplicate_extra_rows = sum(group["duplicate_rows"] - 1 for group in group_summaries)

    type_counter = Counter()
    kind_counter = Counter()
    category_counter = Counter()
    status_counter = Counter()

    for group in group_summaries:
        kind_counter[group["duplicate_kind"]] += 1
        for duplicate_type in group["duplicate_types"]:
            type_counter[duplicate_type] += 1

    for row in duplicate_rows:
        category_counter[row.category] += 1
        status_counter[row.rules_parse_status_group] += 1

    top_groups = sorted(
        group_summaries,
        key=lambda item: (
            -item["duplicate_rows"],
            -len(item["duplicate_types"]),
            item["article"],
        ),
    )[:20]

    row_severity = {
        "mixed_name_and_price": 500,
        "name_variant": 400,
        "category_variant": 350,
        "price_variant": 300,
        "old_or_service_variant": 250,
        "identical": 100,
    }
    ranked_rows = sorted(
        duplicate_rows,
        key=lambda row: (
            -row_severity.get(row.duplicate_kind, 0),
            -row.article_group_size,
            row.article,
            row.article_group_rank,
            row.service_catalog_item_id,
        ),
    )

    top_rows = [
        {
            "article": row.article,
            "service_catalog_item_id": row.service_catalog_item_id,
            "name": row.name,
            "folder_path": row.folder_path,
            "source_url": row.source_url,
            "base_price": row.base_price,
            "is_active": row.is_active,
            "is_calculable": row.is_calculable,
            "description_length": row.description_length,
            "full_description_length": row.full_description_length,
            "rules_parse_status": row.rules_parse_status,
            "problem_reason": row.problem_reason,
            "preview": row.full_description_preview,
            "duplicate_kind": row.duplicate_kind,
        }
        for row in ranked_rows[:20]
    ]

    return {
        "summary": {
            "active_service_rows": len(rows),
            "unique_article_count": len(rows_by_article),
            "duplicate_article_count": duplicate_article_count,
            "duplicate_row_count": duplicate_row_count,
            "duplicate_extra_rows": duplicate_extra_rows,
            "duplicate_row_total": len(duplicate_rows),
            "duplicate_type_counts": dict(type_counter),
            "duplicate_kind_counts": dict(kind_counter),
            "duplicate_rows_by_category": dict(category_counter),
            "duplicate_rows_by_status": dict(status_counter),
            "can_leave_duplicates_safely": duplicate_article_count == 0,
            "should_disable_some_rows": duplicate_article_count > 0,
            "future_rule_binding_key": "service_catalog_item_id",
        },
        "group_summary": group_summaries,
        "top_groups": top_groups,
        "rows": [asdict(row) for row in duplicate_rows],
        "top_problematic_rows": top_rows,
    }


def _print_console_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("Viyar service duplicate audit")
    print(f"Active service rows: {summary['active_service_rows']}")
    print(f"Unique articles: {summary['unique_article_count']}")
    print(f"Articles with duplicates: {summary['duplicate_article_count']}")
    print(f"Duplicate rows (all): {summary['duplicate_row_count']}")
    print(f"Duplicate rows beyond first copies: {summary['duplicate_extra_rows']}")
    print()
    print("Duplicate type counts:")
    for key, value in sorted(summary["duplicate_type_counts"].items()):
        print(f"  {key}: {value}")
    print()
    print("Duplicate kind counts:")
    for key, value in sorted(summary["duplicate_kind_counts"].items()):
        print(f"  {key}: {value}")
    print()
    print("Top 20 duplicate articles:")
    for group in report["top_groups"]:
        print(
            f"- {group['article']} | rows={group['duplicate_rows']} | "
            f"kind={group['duplicate_kind']} | types={', '.join(group['duplicate_types'])} | "
            f"names={'; '.join(group['names'])} | prices={'; '.join(group['prices'])} | "
            f"categories={'; '.join(group['categories'])}"
        )
    print()
    print("Top 20 problematic rows:")
    for row in report["top_problematic_rows"]:
        print(
            f"- {row['article']} | {row['service_catalog_item_id']} | {row['name']} | "
            f"{row['duplicate_kind']} | {row['problem_reason']} | {row['preview'][:120]}"
        )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Audit duplicate Viyar service_catalog_items by article without changing the database."
    )
    parser.add_argument("--database", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON_PATH))
    parser.add_argument("--output-csv", default=str(DEFAULT_CSV_PATH))
    args = parser.parse_args()

    database_path = Path(args.database).resolve()
    if not database_path.is_file():
        raise SystemExit(f"Database was not found: {database_path}")

    connection = sqlite3.connect(str(database_path))
    try:
        rows = _load_active_service_rows(connection)
    finally:
        connection.close()

    report = _build_report(rows)

    output_json = Path(args.output_json).resolve()
    output_csv = Path(args.output_csv).resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(output_csv, [DuplicateRow(**row) for row in report["rows"]])

    _print_console_report(report)
    print(f"Saved JSON report to: {output_json}")
    print(f"Saved CSV report to: {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
