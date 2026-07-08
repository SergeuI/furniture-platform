from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.viyar_service_catalog_service import (
    _fetch_viyar_service_full_description,
    _is_viyar_stale_full_description_text,
    _is_viyar_valid_full_description_text,
)


DEFAULT_ARTICLES = ["144691", "98165", "98178", "128750", "00011", "19002", "98031"]


def _backup_database(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _load_service_row(connection: sqlite3.Connection, article: str) -> dict[str, Any] | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT id, article, name, source_url, description, full_description, rules_parse_status, rules_parsed_at
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
    return (value or "").strip()[:limit]


def _detect_problem(full_description: str | None) -> str | None:
    text = (full_description or "").strip()
    if not text:
        return "empty"
    if _is_viyar_stale_full_description_text(text):
        return "stale_service_text"
    if not _is_viyar_valid_full_description_text(text):
        return "invalid_format"
    return None


def _reparse_service(row: dict[str, Any]) -> dict[str, Any]:
    try:
        fetch_result = _fetch_viyar_service_full_description(
            row.get("source_url") or "",
            use_remote=True,
            diagnostic=True,
        )
    except Exception as exc:  # pragma: no cover - safety for blocked network environments
        return {
            "selected_selector": None,
            "new_status": "failed",
            "new_full_description": None,
            "new_full_description_preview": "",
            "diagnostics": {},
            "fetch_error": str(exc),
        }

    diagnostics = fetch_result.get("diagnostics") or {}
    new_full_description = (fetch_result.get("full_description") or "").strip()
    selected_selector = diagnostics.get("selected_selector")
    selected_ok = bool(selected_selector and str(selected_selector).startswith("section#description"))
    parse_status = str(fetch_result.get("rules_parse_status") or "").strip().lower()

    if new_full_description and selected_ok and _is_viyar_valid_full_description_text(new_full_description):
        return {
            "selected_selector": selected_selector,
            "new_status": "parsed",
            "new_full_description": new_full_description,
            "new_full_description_preview": _truncate(new_full_description),
            "diagnostics": diagnostics,
        }

    if parse_status == "failed":
        return {
            "selected_selector": selected_selector,
            "new_status": "failed",
            "new_full_description": None,
            "new_full_description_preview": "",
            "diagnostics": diagnostics,
        }

    if selected_ok:
        return {
            "selected_selector": selected_selector,
            "new_status": "no_full_description",
            "new_full_description": None,
            "new_full_description_preview": "",
            "diagnostics": diagnostics,
        }

    return {
        "selected_selector": selected_selector,
        "new_status": "needs_review",
        "new_full_description": None,
        "new_full_description_preview": "",
        "diagnostics": diagnostics,
        "fetch_error": None,
    }


def _build_report(row: dict[str, Any], result: dict[str, Any] | None = None) -> dict[str, Any]:
    old_full = row.get("full_description") or ""
    detected_problem = _detect_problem(old_full)
    report = {
        "article": row.get("article"),
        "old_status": row.get("rules_parse_status"),
        "old_full_description_preview": _truncate(old_full),
        "detected_problem": detected_problem,
        "new_status": None,
        "new_full_description_preview": None,
        "selected_selector": None,
        "fetch_error": None,
    }
    if result is not None:
        report["new_status"] = result.get("new_status")
        report["new_full_description_preview"] = result.get("new_full_description_preview")
        report["selected_selector"] = result.get("selected_selector")
        report["fetch_error"] = result.get("fetch_error")
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Dry-run or apply a safe Viyar full_description backfill for stale database rows."
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
        "--apply",
        action="store_true",
        help="Write changes to the database. Default is dry-run.",
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
    connection.row_factory = sqlite3.Row

    try:
        rows = []
        for article in args.articles:
            row = _load_service_row(connection, article)
            if row is None:
                rows.append({"article": article, "found_in_db": False})
                continue

            detected_problem = _detect_problem(row.get("full_description"))
            report = _build_report(row)
            report["found_in_db"] = True

            if detected_problem is None:
                report["new_status"] = row.get("rules_parse_status")
                report["new_full_description_preview"] = _truncate(row.get("full_description"))
                report["selected_selector"] = "existing-full_description-kept"
                rows.append(report)
                continue

            reparsed = _reparse_service(row)
            report.update(
                {
                    "new_status": reparsed.get("new_status"),
                    "new_full_description_preview": reparsed.get("new_full_description_preview"),
                    "selected_selector": reparsed.get("selected_selector"),
                }
            )
            rows.append(report)

            if args.apply:
                if reparsed.get("new_status") == "parsed":
                    connection.execute(
                        """
                        UPDATE service_catalog_items
                        SET full_description = ?,
                            rules_parse_status = ?,
                            rules_parsed_at = ?,
                            rules_source_url = ?
                        WHERE id = ?
                        """,
                        (
                            reparsed.get("new_full_description"),
                            reparsed.get("new_status"),
                            datetime.utcnow().isoformat(timespec="seconds"),
                            row.get("source_url"),
                            row.get("id"),
                        ),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE service_catalog_items
                        SET full_description = NULL,
                            rules_parse_status = ?,
                            rules_parsed_at = NULL,
                            rules_source_url = ?
                        WHERE id = ?
                        """,
                        (
                            reparsed.get("new_status"),
                            row.get("source_url"),
                            row.get("id"),
                        ),
                    )

        if args.apply:
            connection.commit()
        else:
            connection.rollback()
            print("DRY RUN - no changes saved")

        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return 0

        for item in rows:
            print(json.dumps(item, ensure_ascii=False, indent=2))
            print()

        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
