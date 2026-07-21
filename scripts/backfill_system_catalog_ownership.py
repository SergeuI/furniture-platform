from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SelectionRow:
    kind: str
    row_id: int
    article: str | None
    owner_marker: str
    system_marker: str
    planned_change: str
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class BackfillPlan:
    rows: list[SelectionRow]

    @property
    def valid_rows(self) -> list[SelectionRow]:
        return [row for row in self.rows if row.status == "valid"]

    @property
    def invalid_rows(self) -> list[SelectionRow]:
        return [row for row in self.rows if row.status == "invalid"]

    @property
    def already_system_rows(self) -> list[SelectionRow]:
        return [row for row in self.rows if row.status == "already_system"]

    @property
    def can_apply(self) -> bool:
        return not self.invalid_rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill ownership markers for system catalog rows.",
    )
    parser.add_argument(
        "--database",
        default="furniture_platform.db",
        help="Path to the SQLite database.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the selected ownership backfill.",
    )
    parser.add_argument(
        "--material-id",
        action="append",
        type=int,
        default=[],
        help="Material row id to backfill. Repeatable.",
    )
    parser.add_argument(
        "--fitting-id",
        action="append",
        type=int,
        default=[],
        help="Fitting row id to backfill. Repeatable.",
    )
    args = parser.parse_args(argv)
    if not args.material_id and not args.fitting_id:
        parser.error("at least one --material-id or --fitting-id is required")
    return args


def _resolve_database_path(database_arg: str) -> Path:
    candidate = Path(database_arg).expanduser()
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    return candidate


def _open_sqlite(database_path: Path, *, readonly: bool) -> sqlite3.Connection:
    mode = "ro" if readonly else "rw"
    connection = sqlite3.connect(
        f"file:{database_path.as_posix()}?mode={mode}",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _require_schema(connection: sqlite3.Connection) -> None:
    required_tables = ("materials", "fittings", "users", "audit_logs")
    missing_tables = [
        table_name
        for table_name in required_tables
        if not _table_exists(connection, table_name)
    ]
    if missing_tables:
        raise SystemExit("Missing required tables: " + ", ".join(missing_tables))

    required_columns = {
        "materials": {"id", "article", "owner_user_id", "is_default"},
        "fittings": {"id", "article", "owner_user_id", "is_system"},
        "users": {"id", "role"},
        "audit_logs": {"id", "actor_user_id", "actor_email", "action", "entity_type", "entity_id", "details", "created_at"},
    }

    for table_name, expected_columns in required_columns.items():
        actual_columns = {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        missing_columns = sorted(expected_columns - actual_columns)
        if missing_columns:
            raise SystemExit(
                f"Table '{table_name}' is missing required columns: "
                + ", ".join(missing_columns)
            )


def _integrity_check(connection: sqlite3.Connection) -> None:
    row = connection.execute("PRAGMA integrity_check").fetchone()
    if not row or str(row[0]).lower() != "ok":
        raise SystemExit(f"Integrity check failed: {row[0] if row else 'unknown'}")


def _normalize_text(value: object | None) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def _load_owner_role(connection: sqlite3.Connection, owner_user_id: str | None) -> str | None:
    normalized_owner = _normalize_text(owner_user_id)
    if not normalized_owner:
        return None

    row = connection.execute(
        "SELECT role FROM users WHERE id = ?",
        (normalized_owner,),
    ).fetchone()
    return _normalize_text(row["role"]) if row else None


def _load_material_row(connection: sqlite3.Connection, material_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            m.id,
            m.article,
            m.name,
            m.image,
            m.source_url,
            m.owner_user_id,
            m.is_default,
            u.role AS owner_role
        FROM materials m
        LEFT JOIN users u ON u.id = m.owner_user_id
        WHERE m.id = ?
        """,
        (material_id,),
    ).fetchone()


def _load_fitting_row(connection: sqlite3.Connection, fitting_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            f.id,
            f.article,
            f.name,
            f.price,
            f.image_url,
            f.source_url,
            f.owner_user_id,
            f.is_system,
            u.role AS owner_role
        FROM fittings f
        LEFT JOIN users u ON u.id = f.owner_user_id
        WHERE f.id = ?
        """,
        (fitting_id,),
    ).fetchone()


def _build_material_row(connection: sqlite3.Connection, material_id: int) -> SelectionRow:
    row = _load_material_row(connection, material_id)
    if not row:
        return SelectionRow(
            kind="material",
            row_id=material_id,
            article=None,
            owner_marker="owner_user_id=NULL",
            system_marker="is_default=unknown",
            planned_change="blocked",
            status="invalid",
            reason="row not found",
        )

    article = _normalize_text(row["article"])
    owner_user_id = _normalize_text(row["owner_user_id"])
    owner_role = _normalize_text(row["owner_role"])
    is_default = bool(row["is_default"])

    if is_default:
        return SelectionRow(
            kind="material",
            row_id=int(row["id"]),
            article=article,
            owner_marker=f"owner_user_id={owner_user_id or 'NULL'}",
            system_marker="is_default=true",
            planned_change="no change",
            status="already_system",
            reason="already system/default",
        )

    if not owner_user_id:
        return SelectionRow(
            kind="material",
            row_id=int(row["id"]),
            article=article,
            owner_marker="owner_user_id=NULL",
            system_marker="is_default=false",
            planned_change="blocked",
            status="invalid",
            reason="owner_user_id is empty",
        )

    if owner_role != "admin":
        return SelectionRow(
            kind="material",
            row_id=int(row["id"]),
            article=article,
            owner_marker=f"owner_user_id={owner_user_id}",
            system_marker="is_default=false",
            planned_change="blocked",
            status="invalid",
            reason=f"owner role is {owner_role or 'missing'}",
        )

    return SelectionRow(
        kind="material",
        row_id=int(row["id"]),
        article=article,
        owner_marker=f"owner_user_id={owner_user_id}",
        system_marker="is_default=false",
        planned_change="set is_default=true; owner_user_id=NULL",
        status="valid",
    )


def _build_fitting_row(connection: sqlite3.Connection, fitting_id: int) -> SelectionRow:
    row = _load_fitting_row(connection, fitting_id)
    if not row:
        return SelectionRow(
            kind="fitting",
            row_id=fitting_id,
            article=None,
            owner_marker="owner_user_id=NULL",
            system_marker="is_system=unknown",
            planned_change="blocked",
            status="invalid",
            reason="row not found",
        )

    article = _normalize_text(row["article"])
    owner_user_id = _normalize_text(row["owner_user_id"])
    owner_role = _normalize_text(row["owner_role"])
    is_system = bool(row["is_system"])

    if is_system:
        return SelectionRow(
            kind="fitting",
            row_id=int(row["id"]),
            article=article,
            owner_marker=f"owner_user_id={owner_user_id or 'NULL'}",
            system_marker="is_system=true",
            planned_change="no change",
            status="already_system",
            reason="already system",
        )

    if not owner_user_id:
        return SelectionRow(
            kind="fitting",
            row_id=int(row["id"]),
            article=article,
            owner_marker="owner_user_id=NULL",
            system_marker="is_system=false",
            planned_change="blocked",
            status="invalid",
            reason="owner_user_id is empty",
        )

    if owner_role != "admin":
        return SelectionRow(
            kind="fitting",
            row_id=int(row["id"]),
            article=article,
            owner_marker=f"owner_user_id={owner_user_id}",
            system_marker="is_system=false",
            planned_change="blocked",
            status="invalid",
            reason=f"owner role is {owner_role or 'missing'}",
        )

    return SelectionRow(
        kind="fitting",
        row_id=int(row["id"]),
        article=article,
        owner_marker=f"owner_user_id={owner_user_id}",
        system_marker="is_system=false",
        planned_change="set is_system=true; owner_user_id=NULL",
        status="valid",
    )


def build_plan(
    connection: sqlite3.Connection,
    *,
    material_ids: list[int],
    fitting_ids: list[int],
) -> BackfillPlan:
    rows: list[SelectionRow] = []
    for material_id in material_ids:
        rows.append(_build_material_row(connection, material_id))
    for fitting_id in fitting_ids:
        rows.append(_build_fitting_row(connection, fitting_id))
    return BackfillPlan(rows=rows)


def _print_plan(plan: BackfillPlan) -> None:
    print("type | id | article | current owner marker | current system marker | planned change | status")
    for row in plan.rows:
        status = row.status
        if row.reason:
            status = f"{status} ({row.reason})"
        print(
            f"{row.kind} | {row.row_id} | {row.article or '-'} | "
            f"{row.owner_marker} | {row.system_marker} | {row.planned_change} | {status}"
        )
    print(f"selected materials: {sum(1 for row in plan.rows if row.kind == 'material')}")
    print(f"selected fittings: {sum(1 for row in plan.rows if row.kind == 'fitting')}")
    print(f"valid candidates: {len(plan.valid_rows)}")
    print(f"invalid selections: {len(plan.invalid_rows)}")
    print(f"already system: {len(plan.already_system_rows)}")
    print(f"can_apply={str(plan.can_apply).lower()}")


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _apply_plan(
    connection: sqlite3.Connection,
    plan: BackfillPlan,
) -> tuple[list[int], list[int]]:
    material_ids = [row.row_id for row in plan.valid_rows if row.kind == "material"]
    fitting_ids = [row.row_id for row in plan.valid_rows if row.kind == "fitting"]

    if not material_ids and not fitting_ids:
        return [], []

    connection.execute("BEGIN IMMEDIATE")
    try:
        for material_id in material_ids:
            connection.execute(
                """
                UPDATE materials
                SET is_default = 1, owner_user_id = NULL
                WHERE id = ?
                """,
                (material_id,),
            )

        for fitting_id in fitting_ids:
            connection.execute(
                """
                UPDATE fittings
                SET is_system = 1, owner_user_id = NULL
                WHERE id = ?
                """,
                (fitting_id,),
            )

        details = {
            "material_ids": material_ids,
            "fitting_ids": fitting_ids,
            "material_count": len(material_ids),
            "fitting_count": len(fitting_ids),
            "source": "cli",
        }
        connection.execute(
            """
            INSERT INTO audit_logs (
                id,
                actor_user_id,
                actor_email,
                action,
                entity_type,
                entity_id,
                details,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"catalog-system-ownership-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                "system",
                "system",
                "catalog.system_ownership.backfilled",
                "catalog",
                "system_catalog_ownership",
                json.dumps(details, ensure_ascii=False),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return material_ids, fitting_ids


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    database_path = _resolve_database_path(args.database)
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    with _open_sqlite(database_path, readonly=not args.apply) as connection:
        _require_schema(connection)
        _integrity_check(connection)
        plan = build_plan(
            connection,
            material_ids=list(args.material_id),
            fitting_ids=list(args.fitting_id),
        )

        print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
        print(f"Database: {database_path}")
        _print_plan(plan)

        if plan.invalid_rows:
            raise SystemExit(1)

        if not args.apply:
            return 0

        if not plan.valid_rows:
            print("No changes required.")
            return 0

    backup_path = _create_backup(database_path)
    print(f"Backup: {backup_path}")

    with _open_sqlite(database_path, readonly=False) as connection:
        _require_schema(connection)
        _integrity_check(connection)
        applied_material_ids, applied_fitting_ids = _apply_plan(connection, plan)

    print(f"Applied materials: {len(applied_material_ids)}")
    print(f"Applied fittings: {len(applied_fitting_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
