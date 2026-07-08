from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_DB_PATH = PROJECT_ROOT / "furniture_platform.db"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "reports" / "viyar_description_audit.json"

CATEGORY_LABELS = {
    "drilling": "Свердління",
    "edgebanding": "Кромкування / Крайкування",
    "cutting": "Порізка",
    "milling": "Фрезерування",
    "other": "Інші",
}

SUSPICIOUS_MARKERS = (
    "код:",
    "ціна viyarpro",
    "строки",
    "увага! колір товару",
    "грн/шт",
    "є/шт",
    "основні характеристики продукту",
    "тип товару",
    "тип послуги",
    "виробник",
    "країна виробник",
)


@dataclass
class AuditRecord:
    article: str | None
    name: str
    category: str
    folder_path: str
    source_url: str
    description_length: int
    full_description_length: int
    rules_parse_status: str
    has_full_description: bool
    has_short_description: bool
    has_description_marker: bool
    has_limitations_marker: bool
    has_equipment_marker: bool
    classification: str
    problem_reason: str
    full_description_preview: str


def _normalize_text(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _truncate(value: str, limit: int = 300) -> str:
    text = _normalize_text(value)
    return text[:limit]


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


def _is_description_valid(full_description: str) -> bool:
    text = _normalize_text(full_description)
    if not text:
        return False

    lowered = text.lower()
    if "опис:" not in lowered:
        return False

    if len(text) < 50:
        return False

    return True


def _has_suspicious_noise(
    full_description: str,
    has_description_marker: bool,
) -> tuple[bool, list[str]]:
    text = _normalize_text(full_description).lower()
    marker_pool = SUSPICIOUS_MARKERS
    if has_description_marker:
        marker_pool = SUSPICIOUS_MARKERS[:6]
    matches = [marker for marker in marker_pool if marker in text]
    return bool(matches), matches


def _classify_record(row: sqlite3.Row) -> AuditRecord:
    article = _normalize_text(row["article"])
    name = _normalize_text(row["name"])
    folder_path = _normalize_text(row["folder_path"])
    source_url = _normalize_text(row["source_url"])
    description = _normalize_text(row["description"])
    full_description = _normalize_text(row["full_description"])
    parse_status = _normalize_text(row["rules_parse_status"]).lower()

    has_short_description = bool(description)
    has_full_description = bool(full_description)
    has_description_marker = "опис:" in full_description.lower()
    has_limitations_marker = "обмеження:" in full_description.lower()
    has_equipment_marker = "обладнання:" in full_description.lower()
    category = _extract_category(folder_path)

    suspicious, suspicious_matches = _has_suspicious_noise(
        full_description,
        has_description_marker,
    )
    valid_full_description = _is_description_valid(full_description)

    if parse_status == "failed":
        classification = "failed"
        reasons = ["rules_parse_status=failed"]
    elif has_full_description and valid_full_description and not suspicious:
        classification = "valid_full_description"
        reasons = ["valid description block"]
    elif has_full_description and suspicious:
        classification = "suspicious_full_description"
        reasons = [f"suspicious markers: {', '.join(suspicious_matches)}"]
    elif has_full_description:
        classification = "needs_review"
        reasons = []
        if parse_status == "needs_review":
            reasons.append("rules_parse_status=needs_review")
        if not has_description_marker:
            reasons.append("missing 'Опис:' marker")
        if has_limitations_marker:
            reasons.append("contains 'Обмеження:'")
        if has_equipment_marker:
            reasons.append("contains 'Обладнання:'")
        if not reasons:
            reasons.append("full_description requires manual review")
    elif has_short_description and parse_status == "needs_review":
        classification = "needs_review"
        reasons = ["rules_parse_status=needs_review", "full_description is missing"]
    elif has_short_description:
        classification = "short_description_only"
        reasons = ["short description only"]
    else:
        classification = "no_description"
        reasons = ["missing both short and full description"]

    return AuditRecord(
        article=article or None,
        name=name,
        category=category,
        folder_path=folder_path,
        source_url=source_url,
        description_length=len(description),
        full_description_length=len(full_description),
        rules_parse_status=parse_status,
        has_full_description=has_full_description,
        has_short_description=has_short_description,
        has_description_marker=has_description_marker,
        has_limitations_marker=has_limitations_marker,
        has_equipment_marker=has_equipment_marker,
        classification=classification,
        problem_reason="; ".join(reasons),
        full_description_preview=_truncate(full_description),
    )


def _load_rows(connection: sqlite3.Connection, include_inactive: bool) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    query = """
        SELECT
            article,
            name,
            folder_path,
            source_url,
            description,
            full_description,
            rules_parse_status
        FROM service_catalog_items
        WHERE source = 'viyar'
          AND item_type = 'service'
    """
    if not include_inactive:
        query += "\n          AND is_active = 1"
    query += "\n        ORDER BY folder_path, sort_order, name"
    return list(connection.execute(query))


def _build_report(records: list[AuditRecord]) -> dict[str, Any]:
    counters = Counter(record.classification for record in records)
    total = len(records)
    with_source_url = sum(1 for record in records if record.source_url)
    with_short_description = sum(1 for record in records if record.has_short_description)
    with_full_description = sum(1 for record in records if record.has_full_description)
    with_description_marker = sum(1 for record in records if record.has_description_marker)
    with_limitations_marker = sum(1 for record in records if record.has_limitations_marker)
    with_equipment_marker = sum(1 for record in records if record.has_equipment_marker)

    category_buckets: dict[str, dict[str, Any]] = {
        key: {
            "label": label,
            "total": 0,
            "valid_full_description": 0,
            "short_description_only": 0,
            "needs_review": 0,
            "suspicious_full_description": 0,
            "no_description": 0,
            "failed": 0,
        }
        for key, label in CATEGORY_LABELS.items()
    }

    for record in records:
        bucket = category_buckets[record.category]
        bucket["total"] += 1
        bucket[record.classification] += 1

    problematic = [
        record
        for record in records
        if record.classification != "valid_full_description"
    ]

    severity = {
        "failed": 500,
        "suspicious_full_description": 400,
        "needs_review": 300,
        "no_description": 200,
        "short_description_only": 100,
        "valid_full_description": 0,
    }
    problematic.sort(
        key=lambda record: (
            -severity.get(record.classification, 0),
            -record.full_description_length,
            record.article or "",
        )
    )

    top_problems = []
    seen_problem_keys: set[str] = set()
    for record in problematic[:20]:
        problem_key = record.article or f"{record.name}|{record.folder_path}|{record.source_url}"
        if problem_key in seen_problem_keys:
            continue
        seen_problem_keys.add(problem_key)
        top_problems.append(
            {
                "article": record.article,
                "name": record.name,
                "status": record.classification,
                "problem_reason": record.problem_reason,
                "preview": record.full_description_preview,
                "source_url": record.source_url,
                "folder_path": record.folder_path,
            }
        )

    return {
        "summary": {
            "total_active_services": total,
            "with_source_url": with_source_url,
            "with_short_description": with_short_description,
            "with_full_description": with_full_description,
            "with_description_marker": with_description_marker,
            "with_limitations_marker": with_limitations_marker,
            "with_equipment_marker": with_equipment_marker,
            "valid_full_description": counters["valid_full_description"],
            "short_description_only": counters["short_description_only"],
            "needs_review": counters["needs_review"],
            "suspicious_full_description": counters["suspicious_full_description"],
            "no_description": counters["no_description"],
            "failed": counters["failed"],
            "duplicate_article_records": sum(
                count - 1 for count in Counter(record.article for record in records if record.article).values() if count > 1
            ),
        },
        "categories": category_buckets,
        "top_problems": top_problems,
        "records": [asdict(record) for record in records],
    }


def _print_console_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    categories = report["categories"]
    top_problems = report["top_problems"]

    print("Viyar description audit")
    print(f"Total active services: {summary['total_active_services']}")
    print(f"With source_url: {summary['with_source_url']}")
    print(f"With short description: {summary['with_short_description']}")
    print(f"With full_description: {summary['with_full_description']}")
    print(f"With 'Опис:' marker: {summary['with_description_marker']}")
    print(f"With 'Обмеження:' marker: {summary['with_limitations_marker']}")
    print(f"With 'Обладнання:' marker: {summary['with_equipment_marker']}")
    print(f"Valid full descriptions: {summary['valid_full_description']}")
    print(f"Short description only: {summary['short_description_only']}")
    print(f"Needs review: {summary['needs_review']}")
    print(f"Suspicious full descriptions: {summary['suspicious_full_description']}")
    print(f"No description: {summary['no_description']}")
    print(f"Failed: {summary['failed']}")
    print(f"Duplicate article rows: {summary['duplicate_article_records']}")
    print()

    print("By category:")
    for key in ("drilling", "edgebanding", "cutting", "milling", "other"):
        bucket = categories[key]
        print(
            f"  {bucket['label']}: total={bucket['total']}, "
            f"valid={bucket['valid_full_description']}, "
            f"short={bucket['short_description_only']}, "
            f"needs_review={bucket['needs_review']}, "
            f"suspicious={bucket['suspicious_full_description']}, "
            f"no_description={bucket['no_description']}, "
            f"failed={bucket['failed']}"
        )
    print()

    print("Top 20 problematic records:")
    for index, item in enumerate(top_problems, start=1):
        preview = item["preview"].replace("\n", " | ")
        print(
            f"{index}. {item['article']} | {item['name']} | {item['status']} | "
            f"{item['problem_reason']} | {preview}"
        )
    print()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Audit quality of Viyar service full descriptions without changing the database."
    )
    parser.add_argument(
        "--database",
        default=str(DEFAULT_DB_PATH),
        help="SQLite database path.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path for the JSON audit report.",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Include inactive Viyar services in the audit.",
    )
    args = parser.parse_args()

    database_path = Path(args.database).resolve()
    if not database_path.is_file():
        raise SystemExit(f"Database was not found: {database_path}")

    connection = sqlite3.connect(str(database_path))
    try:
        rows = _load_rows(connection, include_inactive=args.include_inactive)
    finally:
        connection.close()

    records = [_classify_record(row) for row in rows]
    report = _build_report(records)

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _print_console_report(report)
    print(f"Saved report to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
