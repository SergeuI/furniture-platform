from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_DATABASE_NAME = "furniture_platform.db"
CANDIDATE_KEEPER_MAP: dict[int, int] = {
    15: 7,
    23: 7,
    31: 7,
    39: 7,
    46: 45,
    49: 48,
    59: 45,
}
REFERENCE_TABLE_ORDER = (
    "fitting_hole_templates",
    "fitting_images",
    "fitting_supplier_offers",
    "mounting_node_items",
)


@dataclass(frozen=True)
class FittingRow:
    id: int
    article: str | None
    name: str | None
    source: str | None
    source_url: str | None
    source_payload_json: str | None
    catalog_key: str | None


@dataclass(frozen=True)
class GalleryRow:
    sort_order: int
    is_primary: int
    source_url: str | None
    image_sha256: str
    image_cached_content_type: str | None


@dataclass(frozen=True)
class CleanupCandidatePlan:
    fitting_id: int
    keeper_id: int
    article: str | None
    name: str | None
    status: str
    reason: str
    dependency_counts: dict[str, int]
    candidate_images: list[GalleryRow]
    keeper_images: list[GalleryRow]
    gallery_status: str
    offer_status: str

    @property
    def can_delete(self) -> bool:
        return self.status == "SAFE_DELETE"


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _integrity_check(connection: sqlite3.Connection) -> str:
    row = connection.execute("PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else "unknown"


def _foreign_key_check(connection: sqlite3.Connection) -> list[tuple[Any, ...]]:
    rows = connection.execute("PRAGMA foreign_key_check").fetchall()
    return [tuple(row) for row in rows]


def _normalize_text(value: Any) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def _counts_snapshot(connection: sqlite3.Connection) -> dict[str, int]:
    tables = (
        "fittings",
        "suppliers",
        "fitting_supplier_offers",
        "mounting_node_items",
        "fitting_hole_templates",
        "fitting_images",
    )
    counts: dict[str, int] = {}
    for table_name in tables:
        if _table_exists(connection, table_name):
            counts[table_name] = int(
                connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            )
        else:
            counts[table_name] = 0
    return counts


def _load_fitting(connection: sqlite3.Connection, fitting_id: int) -> FittingRow | None:
    row = connection.execute(
        """
        SELECT id, article, name, source, source_url, source_payload_json, catalog_key
        FROM fittings
        WHERE id = ?
        """,
        (fitting_id,),
    ).fetchone()
    if row is None:
        return None
    return FittingRow(
        id=int(row["id"]),
        article=row["article"],
        name=row["name"],
        source=row["source"],
        source_url=row["source_url"],
        source_payload_json=row["source_payload_json"],
        catalog_key=row["catalog_key"],
    )


def _discover_fitting_reference_tables(connection: sqlite3.Connection) -> list[tuple[str, str, str]]:
    references: list[tuple[str, str, str]] = []
    tables = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    for table_row in tables:
        table_name = str(table_row[0])
        for fk_row in connection.execute(f"PRAGMA foreign_key_list({table_name})").fetchall():
            if str(fk_row[2]) == "fittings" and str(fk_row[4]) == "id":
                references.append((table_name, str(fk_row[3]), str(fk_row[6])))
    references.sort(key=lambda item: REFERENCE_TABLE_ORDER.index(item[0]) if item[0] in REFERENCE_TABLE_ORDER else len(REFERENCE_TABLE_ORDER))
    return references


def _load_dependency_counts(
    connection: sqlite3.Connection,
    fitting_id: int,
    references: list[tuple[str, str, str]],
) -> dict[str, int]:
    dependency_counts: dict[str, int] = {}
    for table_name, column_name, _on_delete in references:
        dependency_counts[table_name] = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = ?",
                (fitting_id,),
            ).fetchone()[0]
        )
    return dependency_counts


def _load_gallery(connection: sqlite3.Connection, fitting_id: int) -> list[GalleryRow]:
    if not _table_exists(connection, "fitting_images"):
        return []
    rows = connection.execute(
        """
        SELECT sort_order, is_primary, source_url, image_sha256, image_cached_content_type
        FROM fitting_images
        WHERE fitting_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (fitting_id,),
    ).fetchall()
    return [
        GalleryRow(
            sort_order=int(row["sort_order"]),
            is_primary=int(row["is_primary"]),
            source_url=row["source_url"],
            image_sha256=str(row["image_sha256"]),
            image_cached_content_type=row["image_cached_content_type"],
        )
        for row in rows
    ]


def _gallery_signature(rows: list[GalleryRow]) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            row.sort_order,
            row.is_primary,
            _normalize_text(row.source_url),
            row.image_sha256,
            _normalize_text(row.image_cached_content_type),
        )
        for row in rows
    )


def _compare_galleries(candidate_rows: list[GalleryRow], keeper_rows: list[GalleryRow]) -> tuple[str, str]:
    if not candidate_rows:
        return "EMPTY", "candidate has no images"
    if not keeper_rows:
        return "BLOCKED", "keeper has no images"
    if _gallery_signature(candidate_rows) == _gallery_signature(keeper_rows):
        return "IDENTICAL", "gallery identical"
    return "BLOCKED", "gallery mismatch"


def _keeper_offer_status(
    connection: sqlite3.Connection,
    candidate: FittingRow,
    keeper_id: int,
) -> str:
    if not _table_exists(connection, "fitting_supplier_offers") or not _table_exists(connection, "suppliers"):
        return "not_needed"

    rows = connection.execute(
        """
        SELECT offer.article, offer.source_url, supplier.code AS supplier_code
        FROM fitting_supplier_offers AS offer
        JOIN suppliers AS supplier ON supplier.id = offer.supplier_id
        WHERE offer.fitting_id = ?
        """,
        (keeper_id,),
    ).fetchall()

    if not rows:
        return "not_needed"

    candidate_article = _normalize_text(candidate.article)
    candidate_source_url = _normalize_text(candidate.source_url)
    for row in rows:
        if _normalize_text(row["supplier_code"]) != "viyar":
            continue
        if candidate_article is not None and _normalize_text(row["article"]) != candidate_article:
            continue
        if candidate_source_url is not None and _normalize_text(row["source_url"]) != candidate_source_url:
            continue
        return "verified"

    return "blocked"


def _build_candidate_plan(
    connection: sqlite3.Connection,
    candidate_id: int,
    keeper_id: int,
    references: list[tuple[str, str, str]],
) -> CleanupCandidatePlan:
    candidate = _load_fitting(connection, candidate_id)
    keeper = _load_fitting(connection, keeper_id)

    if candidate is None:
        return CleanupCandidatePlan(
            fitting_id=candidate_id,
            keeper_id=keeper_id,
            article=None,
            name=None,
            status="BLOCKED",
            reason="candidate fitting is missing",
            dependency_counts={table_name: 0 for table_name, _column_name, _on_delete in references},
            candidate_images=[],
            keeper_images=[],
            gallery_status="BLOCKED",
            offer_status="not_needed",
        )

    if keeper is None:
        return CleanupCandidatePlan(
            fitting_id=candidate_id,
            keeper_id=keeper_id,
            article=candidate.article,
            name=candidate.name,
            status="BLOCKED",
            reason=f"keeper fitting_id={keeper_id} is missing",
            dependency_counts={table_name: 0 for table_name, _column_name, _on_delete in references},
            candidate_images=[],
            keeper_images=[],
            gallery_status="BLOCKED",
            offer_status="not_needed",
        )

    dependency_counts = _load_dependency_counts(connection, candidate_id, references)
    candidate_images = _load_gallery(connection, candidate_id)
    keeper_images = _load_gallery(connection, keeper_id)
    gallery_status, gallery_reason = _compare_galleries(candidate_images, keeper_images)
    offer_status = _keeper_offer_status(connection, candidate, keeper_id)

    blocking_counts = {
        table_name: count
        for table_name, count in dependency_counts.items()
        if table_name != "fitting_images" and count > 0
    }
    if blocking_counts:
        reason = "live dependencies: " + ", ".join(
            f"{table_name}={count}"
            for table_name, count in blocking_counts.items()
        )
        return CleanupCandidatePlan(
            fitting_id=candidate_id,
            keeper_id=keeper_id,
            article=candidate.article,
            name=candidate.name,
            status="BLOCKED",
            reason=reason,
            dependency_counts=dependency_counts,
            candidate_images=candidate_images,
            keeper_images=keeper_images,
            gallery_status=gallery_status,
            offer_status=offer_status,
        )

    if gallery_status == "BLOCKED":
        return CleanupCandidatePlan(
            fitting_id=candidate_id,
            keeper_id=keeper_id,
            article=candidate.article,
            name=candidate.name,
            status="BLOCKED",
            reason=gallery_reason,
            dependency_counts=dependency_counts,
            candidate_images=candidate_images,
            keeper_images=keeper_images,
            gallery_status=gallery_status,
            offer_status=offer_status,
        )

    reason_parts = ["no live dependencies", gallery_reason]
    if offer_status == "verified":
        reason_parts.append("keeper VIYAR offer verified")

    return CleanupCandidatePlan(
        fitting_id=candidate_id,
        keeper_id=keeper_id,
        article=candidate.article,
        name=candidate.name,
        status="SAFE_DELETE",
        reason="; ".join(reason_parts),
        dependency_counts=dependency_counts,
        candidate_images=candidate_images,
        keeper_images=keeper_images,
        gallery_status=gallery_status,
        offer_status=offer_status,
    )


def _build_plan(connection: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(connection, "fittings"):
        return {
            "prerequisite_missing": True,
            "missing_prerequisites": ["fittings"],
            "counts_before": {},
            "counts_after": {},
            "candidate_plans": [],
            "safe_delete_ids": [],
            "blocked_ids": [],
        }

    references = _discover_fitting_reference_tables(connection)
    counts_before = _counts_snapshot(connection)
    candidate_plans = [
        _build_candidate_plan(connection, candidate_id, keeper_id, references)
        for candidate_id, keeper_id in CANDIDATE_KEEPER_MAP.items()
    ]
    safe_delete_ids = [plan.fitting_id for plan in candidate_plans if plan.can_delete]
    blocked_ids = [plan.fitting_id for plan in candidate_plans if not plan.can_delete]
    counts_after = dict(counts_before)
    counts_after["fittings"] -= len(safe_delete_ids)
    counts_after["fitting_images"] -= sum(len(plan.candidate_images) for plan in candidate_plans if plan.can_delete)

    return {
        "prerequisite_missing": False,
        "missing_prerequisites": [],
        "counts_before": counts_before,
        "counts_after": counts_after,
        "candidate_plans": candidate_plans,
        "safe_delete_ids": safe_delete_ids,
        "blocked_ids": blocked_ids,
    }


def _apply_plan(connection: sqlite3.Connection, plan: dict[str, Any]) -> int:
    safe_delete_ids = list(plan["safe_delete_ids"])
    if not safe_delete_ids:
        return 0

    connection.executemany(
        "DELETE FROM fittings WHERE id = ?",
        [(fitting_id,) for fitting_id in safe_delete_ids],
    )
    return len(safe_delete_ids)


def _print_plan(
    database_path: Path,
    plan: dict[str, Any],
    *,
    dry_run: bool,
    backup_path: Path | None = None,
) -> None:
    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    print(f"Database: {database_path}")
    if backup_path is not None:
        print(f"Backup: {backup_path}")
        print(f"Backup size: {backup_path.stat().st_size}")
    if plan["prerequisite_missing"]:
        print("Prerequisites missing:", ", ".join(plan["missing_prerequisites"]) or "unknown")
        return

    print("Integrity before:", plan["integrity_before"])
    print("Foreign key issues before:", len(plan["fk_issues_before"]))
    print("Counts before:", json.dumps(plan["counts_before"], ensure_ascii=False, sort_keys=True))
    print("Candidate audit:")
    for candidate_plan in plan["candidate_plans"]:
        dependency_text = ", ".join(
            f"{table_name}={count}"
            for table_name, count in candidate_plan.dependency_counts.items()
        ) or "none"
        print(
            f"  - fitting={candidate_plan.fitting_id} keeper={candidate_plan.keeper_id} "
            f"status={candidate_plan.status} deps={dependency_text} "
            f"gallery={candidate_plan.gallery_status.lower()} offer={candidate_plan.offer_status} "
            f"reason={candidate_plan.reason}"
        )
    print("Dry-run delete plan:")
    if plan["safe_delete_ids"]:
        for candidate_plan in plan["candidate_plans"]:
            if candidate_plan.can_delete:
                print(
                    f"  SAFE_DELETE fitting={candidate_plan.fitting_id} "
                    f"keeper={candidate_plan.keeper_id}"
                )
    else:
        print("  none")
    if plan["blocked_ids"]:
        for candidate_plan in plan["candidate_plans"]:
            if not candidate_plan.can_delete:
                print(
                    f"  BLOCKED fitting={candidate_plan.fitting_id} "
                    f"keeper={candidate_plan.keeper_id}"
                )
    else:
        print("  BLOCKED none")
    print(f"Safe deletes: {len(plan['safe_delete_ids'])}")
    print(f"Blocked rows: {len(plan['blocked_ids'])}")
    print("Expected counts after apply:", json.dumps(plan["counts_after"], ensure_ascii=False, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely delete confirmed duplicate fittings after dependency and gallery checks.",
    )
    parser.add_argument("--database", default=DEFAULT_DATABASE_NAME)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    database_path = Path(args.database).resolve()
    if not database_path.is_file():
        raise SystemExit(f"Database was not found: {database_path}")

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        integrity_before = _integrity_check(connection)
        fk_issues_before = _foreign_key_check(connection)
        if integrity_before.lower() != "ok":
            raise SystemExit(f"Integrity check failed before cleanup: {integrity_before}")
        if fk_issues_before:
            raise SystemExit(f"Foreign key check failed before cleanup: {fk_issues_before}")

        plan = _build_plan(connection)
        plan["integrity_before"] = integrity_before
        plan["fk_issues_before"] = fk_issues_before

        if not args.apply:
            _print_plan(database_path, plan, dry_run=True)
            if plan["prerequisite_missing"]:
                raise SystemExit(1)
            return 0

        if not plan["safe_delete_ids"]:
            _print_plan(database_path, plan, dry_run=False)
            print("No SAFE_DELETE rows were found; no write performed.")
            if plan["prerequisite_missing"]:
                raise SystemExit(1)
            return 0

        backup_path = _create_backup(database_path)
        connection.execute("BEGIN IMMEDIATE")
        deleted_count = _apply_plan(connection, plan)
        connection.commit()

        integrity_after = _integrity_check(connection)
        fk_issues_after = _foreign_key_check(connection)
        if integrity_after.lower() != "ok":
            raise SystemExit(f"Integrity check failed after cleanup: {integrity_after}")
        if fk_issues_after:
            raise SystemExit(f"Foreign key check failed after cleanup: {fk_issues_after}")

        _print_plan(database_path, plan, dry_run=False, backup_path=backup_path)
        print(f"Deleted fittings: {deleted_count}")
        print("Post-apply integrity:", integrity_after)
        print("Post-apply counts:", json.dumps(_counts_snapshot(connection), ensure_ascii=False, sort_keys=True))
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
