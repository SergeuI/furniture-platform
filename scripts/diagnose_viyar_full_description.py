from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.viyar_service_catalog_service import _fetch_viyar_service_full_description


DEFAULT_ARTICLES = ["19002", "98031", "144691", "98165", "54109"]


def _load_service_row(connection: sqlite3.Connection, article: str) -> dict[str, Any] | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT article, name, source_url, description, full_description, rules_parse_status
        FROM service_catalog_items
        WHERE source = 'viyar' AND article = ?
        LIMIT 1
        """,
        (article,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def _truncate(value: str | None, limit: int = 300) -> str:
    text = (value or "").strip()
    return text[:limit]


def _diagnose_article(connection: sqlite3.Connection, article: str) -> dict[str, Any]:
    row = _load_service_row(connection, article)
    if row is None:
        return {
            "article": article,
            "found_in_db": False,
        }

    fetch_result = _fetch_viyar_service_full_description(
        row.get("source_url") or "",
        use_remote=True,
        diagnostic=True,
    )
    diagnostics = fetch_result.get("diagnostics") or {}

    return {
        "article": row.get("article"),
        "name": row.get("name"),
        "source_url": row.get("source_url"),
        "rules_parse_status": row.get("rules_parse_status"),
        "description": row.get("description"),
        "current_full_description_preview": _truncate(row.get("full_description")),
        "fetch_rules_parse_status": fetch_result.get("rules_parse_status"),
        "fetch_selected_selector": diagnostics.get("selected_selector"),
        "fetch_selected_text_length": diagnostics.get("selected_text_length"),
        "fetch_selected_text_preview": _truncate(diagnostics.get("selected_text")),
        "fetch_has_description_section": diagnostics.get("has_description_section"),
        "fetch_has_characteristics_section": diagnostics.get("has_characteristics_section"),
        "fetch_candidate_blocks": diagnostics.get("candidate_blocks", []),
        "fetch_rejected_blocks": diagnostics.get("rejected_blocks", []),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Diagnose Viyar full_description parsing without writing to the database."
    )
    parser.add_argument(
        "articles",
        nargs="*",
        default=DEFAULT_ARTICLES,
        help="Viyar article numbers to inspect.",
    )
    parser.add_argument(
        "--database",
        default="furniture_platform.db",
        help="SQLite database path.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of a readable report.",
    )
    args = parser.parse_args()

    database_path = Path(args.database).resolve()
    if not database_path.is_file():
        raise SystemExit(f"Database was not found: {database_path}")

    connection = sqlite3.connect(str(database_path))
    try:
        report = [_diagnose_article(connection, article) for article in args.articles]
    finally:
        connection.close()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    for item in report:
        print(json.dumps(item, ensure_ascii=False, indent=2))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
