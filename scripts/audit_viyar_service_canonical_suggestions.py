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
DEFAULT_JSON_PATH = PROJECT_ROOT / "reports" / "viyar_service_canonical_suggestions.json"
DEFAULT_CSV_PATH = PROJECT_ROOT / "reports" / "viyar_service_canonical_suggestions.csv"


@dataclass
class CanonicalMemberRow:
    article: str
    canonical_service_catalog_item_id: str
    duplicate_service_catalog_item_id: str
    row_role: str
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
    reason: str
    duplicate_kind: str
    duplicate_group_size: int
    group_risk: str


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


def _load_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
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


def _group_rows(rows: list[sqlite3.Row]) -> dict[str, list[sqlite3.Row]]:
    grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[_normalize_text(row["article"])].append(row)
    return grouped


def _is_group_identical(rows: list[sqlite3.Row]) -> bool:
    names = {_normalize_text(row["name"]).lower() for row in rows}
    categories = {_extract_category(row["folder_path"]) for row in rows}
    prices = {_price_key(_format_price(row["base_price"])) for row in rows}
    descriptions = {_normalize_text(row["description"]) for row in rows}
    full_descriptions = {_normalize_text(row["full_description"]) for row in rows}
    statuses = {_normalize_text(row["rules_parse_status"]).lower() for row in rows}
    source_urls = {_normalize_text(row["source_url"]) for row in rows}
    return (
        len(names) == 1
        and len(categories) == 1
        and len(prices) == 1
        and len(descriptions) <= 1
        and len(full_descriptions) <= 1
        and len(statuses) <= 1
        and len(source_urls) <= 1
    )


def _score_row(row: sqlite3.Row) -> tuple[int, int, int, str]:
    has_full_description = bool(_normalize_text(row["full_description"]))
    is_parsed = _normalize_text(row["rules_parse_status"]).lower() == "parsed"
    is_active = bool(row["is_active"])

    # Larger score is better.
    return (
        1 if is_active else 0,
        1 if has_full_description else 0,
        1 if is_parsed else 0,
        row["id"],
    )


def _pick_canonical(rows: list[sqlite3.Row]) -> tuple[sqlite3.Row, str]:
    ranked = sorted(
        rows,
        key=lambda row: (
            -int(bool(row["is_active"])),
            -int(bool(_normalize_text(row["full_description"]))),
            -int(_normalize_text(row["rules_parse_status"]).lower() == "parsed"),
            _normalize_text(row["id"]),
        ),
    )
    canonical = ranked[0]
    reason_parts = ["active"]
    if _normalize_text(canonical["full_description"]):
        reason_parts.append("has full_description")
    if _normalize_text(canonical["rules_parse_status"]).lower() == "parsed":
        reason_parts.append("rules_parse_status=parsed")
    reason_parts.append("smallest id among highest-ranked rows")
    return canonical, "; ".join(reason_parts)


def _duplicate_kind(rows: list[sqlite3.Row]) -> str:
    names = {_normalize_text(row["name"]).lower() for row in rows}
    categories = {_extract_category(row["folder_path"]) for row in rows}
    prices = {_price_key(_format_price(row["base_price"])) for row in rows}

    if len(names) == 1 and len(categories) == 1 and len(prices) == 1:
        return "identical"
    if len(names) > 1 and len(prices) > 1:
        return "mixed_name_and_price"
    if len(names) > 1:
        return "name_variant"
    if len(categories) > 1:
        return "category_variant"
    if len(prices) > 1:
        return "price_variant"
    return "mixed_variant"


def _group_risk(rows: list[sqlite3.Row], duplicate_kind: str) -> str:
    statuses = {_normalize_text(row["rules_parse_status"]).lower() for row in rows}
    descriptions = {_normalize_text(row["description"]) for row in rows}
    full_descriptions = {_normalize_text(row["full_description"]) for row in rows}
    source_urls = {_normalize_text(row["source_url"]) for row in rows}
    names = {_normalize_text(row["name"]).lower() for row in rows}
    categories = {_extract_category(row["folder_path"]) for row in rows}
    prices = {_price_key(_format_price(row["base_price"])) for row in rows}

    if duplicate_kind != "identical":
        return "high"
    if (
        len(statuses) > 1
        or len(descriptions) > 1
        or len(full_descriptions) > 1
        or len(source_urls) > 1
    ):
        return "medium"
    if len(names) > 1 or len(categories) > 1 or len(prices) > 1:
        return "medium"
    return "low"


def _build_members(rows: list[sqlite3.Row], canonical: sqlite3.Row, canonical_reason: str, duplicate_kind: str, group_risk: str) -> list[CanonicalMemberRow]:
    members: list[CanonicalMemberRow] = []
    canonical_id = _normalize_text(canonical["id"])

    for row in rows:
        row_id = _normalize_text(row["id"])
        row_role = "canonical" if row_id == canonical_id else "duplicate"
        row_reason = canonical_reason if row_role == "canonical" else f"duplicate of {canonical_id}"
        members.append(
            CanonicalMemberRow(
                article=_normalize_text(row["article"]),
                canonical_service_catalog_item_id=canonical_id,
                duplicate_service_catalog_item_id=row_id,
                row_role=row_role,
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
                reason=row_reason,
                duplicate_kind=duplicate_kind,
                duplicate_group_size=len(rows),
                group_risk=group_risk,
            )
        )

    return members


def _build_report(rows: list[sqlite3.Row]) -> dict[str, Any]:
    grouped = _group_rows(rows)
    duplicate_groups = {
        article: group
        for article, group in grouped.items()
        if len(group) > 1
    }

    group_records: list[dict[str, Any]] = []
    member_rows: list[CanonicalMemberRow] = []

    duplicate_kind_counter = Counter()
    risk_counter = Counter()
    canonical_count = 0
    duplicate_row_count = 0

    for article, group_rows in sorted(duplicate_groups.items(), key=lambda item: (len(item[0]), item[0])):
        canonical_row, canonical_reason = _pick_canonical(group_rows)
        duplicate_kind = _duplicate_kind(group_rows)
        group_risk = _group_risk(group_rows, duplicate_kind)
        members = _build_members(group_rows, canonical_row, canonical_reason, duplicate_kind, group_risk)

        duplicate_kind_counter[duplicate_kind] += 1
        risk_counter[group_risk] += 1
        canonical_count += 1
        duplicate_row_count += len(group_rows) - 1
        member_rows.extend(members)

        group_records.append(
            {
                "article": article,
                "duplicate_group_size": len(group_rows),
                "canonical_service_catalog_item_id": _normalize_text(canonical_row["id"]),
                "canonical_name": _normalize_text(canonical_row["name"]),
                "canonical_folder_path": _normalize_text(canonical_row["folder_path"]),
                "canonical_base_price": _format_price(canonical_row["base_price"]),
                "canonical_rules_parse_status": _normalize_text(canonical_row["rules_parse_status"]).lower(),
                "canonical_full_description_length": len(_normalize_text(canonical_row["full_description"])),
                "canonical_reason": canonical_reason,
                "duplicate_kind": duplicate_kind,
                "group_risk": group_risk,
                "rows": [asdict(member) for member in members],
            }
        )

    rows_for_csv = sorted(
        member_rows,
        key=lambda row: (
            len(row.article),
            row.article,
            row.row_role != "canonical",
            row.duplicate_service_catalog_item_id,
        ),
    )

    risky_groups = [group for group in group_records if group["group_risk"] != "low"]
    can_safely_disable_duplicates = len(risky_groups) == 0

    summary = {
        "active_service_rows": len(rows),
        "unique_article_count": len(grouped),
        "duplicate_article_count": len(duplicate_groups),
        "canonical_row_count": canonical_count,
        "duplicate_row_count": duplicate_row_count,
        "risky_group_count": len(risky_groups),
        "risk_counts": dict(risk_counter),
        "duplicate_kind_counts": dict(duplicate_kind_counter),
        "can_safely_disable_duplicates": can_safely_disable_duplicates,
        "future_rule_binding_key": "service_catalog_item_id",
        "future_rule_binding_reason": "article is duplicated; use concrete service_catalog_item_id for stable rules",
    }

    top_groups = sorted(
        group_records,
        key=lambda item: (
            -item["duplicate_group_size"],
            0 if item["duplicate_kind"] == "identical" else 1,
            item["article"],
        ),
    )[:20]

    top_rows = sorted(
        rows_for_csv,
        key=lambda row: (
            0 if row.row_role == "canonical" else 1,
            -row.duplicate_group_size,
            row.article,
            row.duplicate_service_catalog_item_id,
        ),
    )[:20]

    return {
        "summary": summary,
        "groups": group_records,
        "top_groups": top_groups,
        "rows": [asdict(row) for row in rows_for_csv],
        "top_rows": [asdict(row) for row in top_rows],
    }


def _write_csv(csv_path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        csv_path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            item = dict(row)
            writer.writerow(item)


def _print_console_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("Viyar canonical suggestion audit")
    print(f"Active service rows: {summary['active_service_rows']}")
    print(f"Unique articles: {summary['unique_article_count']}")
    print(f"Articles with duplicates: {summary['duplicate_article_count']}")
    print(f"Canonical rows: {summary['canonical_row_count']}")
    print(f"Duplicate rows: {summary['duplicate_row_count']}")
    print(f"Risky groups: {summary['risky_group_count']}")
    print(f"Safe to disable duplicates later: {summary['can_safely_disable_duplicates']}")
    print(f"Future rule binding key: {summary['future_rule_binding_key']}")
    print()
    print("Duplicate kind counts:")
    for key, value in sorted(summary["duplicate_kind_counts"].items()):
        print(f"  {key}: {value}")
    print()
    print("Risk counts:")
    for key, value in sorted(summary["risk_counts"].items()):
        print(f"  {key}: {value}")
    print()
    print("Top 20 duplicate groups:")
    for group in report["top_groups"]:
        print(
            f"- {group['article']} | rows={group['duplicate_group_size']} | "
            f"canonical={group['canonical_service_catalog_item_id']} | "
            f"risk={group['group_risk']} | kind={group['duplicate_kind']} | "
            f"reason={group['canonical_reason']}"
        )
    print()
    print("Top 20 rows:")
    for row in report["top_rows"]:
        print(
            f"- {row['article']} | {row['row_role']} | {row['duplicate_service_catalog_item_id']} | "
            f"{row['name']} | {row['duplicate_kind']} | {row['reason']}"
        )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Build canonical row suggestions for duplicated Viyar service rows without changing the database."
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
        rows = _load_rows(connection)
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
    _write_csv(output_csv, report["rows"])

    _print_console_report(report)
    print(f"Saved JSON report to: {output_json}")
    print(f"Saved CSV report to: {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
