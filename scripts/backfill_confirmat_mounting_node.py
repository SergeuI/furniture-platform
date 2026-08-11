from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.models.user import UserModel  # noqa: F401
from services.mounting_node_service import MountingNodeService
from scripts import upgrade_mounting_nodes_schema as mounting_nodes_schema


DEFAULT_NODE_CODE = "mn_confirmat_7x50"
DEFAULT_NODE_NAME = "Конфірмат 7×50"
DEFAULT_NODE_DESCRIPTION = "Монтажний вузол для конфірмата 7×50"
DEFAULT_FITTING_ID = 1
DEFAULT_TEMPLATE_ID = 7428
EXPECTED_FITTING_ARTICLE = "190106"
EXPECTED_FITTING_CODE = "confirmat_7x50"
EXPECTED_MOUNTING_VARIANT_KEY = "face_to_edge"
EXPECTED_ROLE = "Основний кріпильний елемент"
_BACKFILL_CURRENT_COUNTS: dict[str, int] | None = None


@dataclass(frozen=True)
class BackfillTarget:
    node_code: str
    node_name: str
    description: str
    fitting_id: int
    template_id: int


@dataclass(frozen=True)
class BackfillPlan:
    target: BackfillTarget
    status: str
    reason: str | None
    fitting: dict[str, Any] | None
    template: dict[str, Any] | None
    points: list[dict[str, Any]]
    existing_node: dict[str, Any] | None
    expected_counts: dict[str, int]
    current_counts: dict[str, int]

    @property
    def can_apply(self) -> bool:
        return self.status == "valid"

    @property
    def is_already_applied(self) -> bool:
        return self.status == "already_applied"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill the first mounting node for confirmat 7x50.",
    )
    parser.add_argument(
        "--db-path",
        "--database",
        dest="db_path",
        default="furniture_platform.db",
        help="Path to the SQLite database.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the plan without writing anything.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Apply the backfill after backup and validation.",
    )
    parser.add_argument(
        "--node-code",
        default=DEFAULT_NODE_CODE,
        help="Target mounting node code.",
    )
    parser.add_argument(
        "--template-id",
        type=int,
        default=DEFAULT_TEMPLATE_ID,
        help="Target fitting-hole template id.",
    )
    parser.add_argument(
        "--fitting-id",
        type=int,
        default=DEFAULT_FITTING_ID,
        help="Target fitting id.",
    )
    args = parser.parse_args(argv)
    if not args.dry_run and not args.apply:
        args.dry_run = True
    return args


def _resolve_database_path(database_arg: str | None) -> Path:
    candidate = Path(database_arg or "furniture_platform.db").expanduser()
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
    required_tables = (
        "fittings",
        "fitting_hole_templates",
        "fitting_hole_points",
        "mounting_nodes",
        "mounting_node_items",
        "mounting_node_templates",
    )
    missing_tables = [
        table_name
        for table_name in required_tables
        if not _table_exists(connection, table_name)
    ]
    if missing_tables:
        raise SystemExit("Missing required tables: " + ", ".join(missing_tables))


def _integrity_check(connection: sqlite3.Connection) -> None:
    row = connection.execute("PRAGMA integrity_check").fetchone()
    if not row or str(row[0]).lower() != "ok":
        raise SystemExit(f"Integrity check failed: {row[0] if row else 'unknown'}")


def _foreign_key_check(connection: sqlite3.Connection) -> list[tuple[Any, ...]]:
    rows = connection.execute("PRAGMA foreign_key_check").fetchall()
    return [tuple(row) for row in rows]


def _normalize_text(value: object | None) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def _load_row(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[Any, ...],
) -> dict[str, Any] | None:
    row = connection.execute(query, parameters).fetchone()
    return dict(row) if row else None


def _load_fitting(connection: sqlite3.Connection, fitting_id: int) -> dict[str, Any] | None:
    return _load_row(
        connection,
        """
        SELECT id, article, code, name, fitting_type, fitting_group, is_system, is_active
        FROM fittings
        WHERE id = ?
        """,
        (fitting_id,),
    )


def _load_template(connection: sqlite3.Connection, template_id: int) -> dict[str, Any] | None:
    return _load_row(
        connection,
        """
        SELECT id, fitting_id, name, mounting_variant_key, is_default, is_active
        FROM fitting_hole_templates
        WHERE id = ?
        """,
        (template_id,),
    )


def _load_points(connection: sqlite3.Connection, template_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, template_id, label, x_mm, y_mm, z_mm, diameter_mm, depth_mm,
               target_panel, target_surface, target_side, quantity, mirrored, order_index
        FROM fitting_hole_points
        WHERE template_id = ?
        ORDER BY order_index ASC, id ASC
        """,
        (template_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _load_existing_node(connection: sqlite3.Connection, node_code: str) -> dict[str, Any] | None:
    node = _load_row(
        connection,
        """
        SELECT id, code, name, description, is_active, owner_user_id,
               created_by_user_id, updated_by_user_id
        FROM mounting_nodes
        WHERE code = ?
        """,
        (node_code,),
    )
    if node is None:
        return None

    items = [
        dict(row)
        for row in connection.execute(
            """
            SELECT id, node_id, fitting_id, role, quantity, is_required, affects_processing, order_index
            FROM mounting_node_items
            WHERE node_id = ?
            ORDER BY order_index ASC, id ASC
            """,
            (node["id"],),
        ).fetchall()
    ]
    templates = [
        dict(row)
        for row in connection.execute(
            """
            SELECT id, node_id, template_id, is_default, order_index
            FROM mounting_node_templates
            WHERE node_id = ?
            ORDER BY order_index ASC, id ASC
            """,
            (node["id"],),
        ).fetchall()
    ]
    node["items"] = items
    node["templates"] = templates
    return node


def _template_owner_node_id(connection: sqlite3.Connection, template_id: int) -> int | None:
    row = connection.execute(
        "SELECT node_id FROM mounting_node_templates WHERE template_id = ?",
        (template_id,),
    ).fetchone()
    return int(row["node_id"]) if row else None


def _expected_counts(existing_node: dict[str, Any] | None) -> dict[str, int]:
    current_counts = dict(_BACKFILL_CURRENT_COUNTS or {})
    expected = dict(current_counts)
    expected["mounting_nodes"] = 1
    expected["mounting_node_items"] = 1 if existing_node is None else len(existing_node.get("items", []))
    expected["mounting_node_templates"] = 1 if existing_node is None else len(existing_node.get("templates", []))
    return expected


def _current_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = (
        "fittings",
        "fitting_hole_templates",
        "fitting_hole_points",
        "mounting_nodes",
        "mounting_node_items",
        "mounting_node_templates",
    )
    return {
        table_name: int(
            connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        )
        for table_name in tables
    }


def _validate_target(connection: sqlite3.Connection, target: BackfillTarget) -> BackfillPlan:
    global _BACKFILL_CURRENT_COUNTS

    fitting = _load_fitting(connection, target.fitting_id)
    template = _load_template(connection, target.template_id)
    points = _load_points(connection, target.template_id)
    existing_node = _load_existing_node(connection, target.node_code)

    current_counts = _current_counts(connection)
    _BACKFILL_CURRENT_COUNTS = current_counts

    if fitting is None:
        return BackfillPlan(
            target=target,
            status="invalid",
            reason=f"fitting_id={target.fitting_id} does not exist",
            fitting=None,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if _normalize_text(fitting.get("article")) != EXPECTED_FITTING_ARTICLE:
        return BackfillPlan(
            target=target,
            status="invalid",
            reason=f"fitting article must be {EXPECTED_FITTING_ARTICLE}",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if _normalize_text(fitting.get("code")) != EXPECTED_FITTING_CODE:
        return BackfillPlan(
            target=target,
            status="invalid",
            reason=f"fitting code must be {EXPECTED_FITTING_CODE}",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if template is None:
        return BackfillPlan(
            target=target,
            status="invalid",
            reason=f"template_id={target.template_id} does not exist",
            fitting=fitting,
            template=None,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if int(template["fitting_id"]) != target.fitting_id:
        return BackfillPlan(
            target=target,
            status="invalid",
            reason=f"template_id={target.template_id} does not belong to fitting_id={target.fitting_id}",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if _normalize_text(template.get("mounting_variant_key")) != EXPECTED_MOUNTING_VARIANT_KEY:
        return BackfillPlan(
            target=target,
            status="invalid",
            reason=f"mounting_variant_key must be {EXPECTED_MOUNTING_VARIANT_KEY}",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if not bool(template.get("is_active")):
        return BackfillPlan(
            target=target,
            status="invalid",
            reason="template is not active",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if len(points) != 2:
        return BackfillPlan(
            target=target,
            status="invalid",
            reason="template must contain exactly two points",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    point_by_diameter = {
        round(float(point.get("diameter_mm") or 0), 3): point
        for point in points
    }
    through_point = point_by_diameter.get(7.0)
    blind_point = point_by_diameter.get(4.5)

    if through_point is None:
        return BackfillPlan(
            target=target,
            status="invalid",
            reason="missing Ø7 point",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if blind_point is None:
        return BackfillPlan(
            target=target,
            status="invalid",
            reason="missing Ø4.5 point",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if _normalize_text(through_point.get("target_panel")) != "vertical_panel":
        return BackfillPlan(
            target=target,
            status="invalid",
            reason="Ø7 point must target vertical_panel",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if _normalize_text(through_point.get("target_surface")) != "plane":
        return BackfillPlan(
            target=target,
            status="invalid",
            reason="Ø7 point must target plane",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if through_point.get("depth_mm") not in (None, ""):
        return BackfillPlan(
            target=target,
            status="invalid",
            reason="Ø7 point must be through/null depth",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if _normalize_text(blind_point.get("target_panel")) != "horizontal_panel":
        return BackfillPlan(
            target=target,
            status="invalid",
            reason="Ø4.5 point must target horizontal_panel",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if _normalize_text(blind_point.get("target_surface")) != "edge":
        return BackfillPlan(
            target=target,
            status="invalid",
            reason="Ø4.5 point must target edge",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    owner_node_id = _template_owner_node_id(connection, target.template_id)
    if existing_node is not None:
        if _matches_existing_node(existing_node, target, points):
            return BackfillPlan(
                target=target,
                status="already_applied",
                reason="already applied",
                fitting=fitting,
                template=template,
                points=points,
                existing_node=existing_node,
                expected_counts=_expected_counts(existing_node),
                current_counts=current_counts,
            )

        return BackfillPlan(
            target=target,
            status="invalid",
            reason="node code already exists with different content",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=existing_node,
            expected_counts=_expected_counts(existing_node),
            current_counts=current_counts,
        )

    if owner_node_id is not None:
        return BackfillPlan(
            target=target,
            status="invalid",
            reason=f"template_id={target.template_id} is already linked to node_id={owner_node_id}",
            fitting=fitting,
            template=template,
            points=points,
            existing_node=None,
            expected_counts=_expected_counts(None),
            current_counts=current_counts,
        )

    return BackfillPlan(
        target=target,
        status="valid",
        reason=None,
        fitting=fitting,
        template=template,
        points=points,
        existing_node=None,
        expected_counts=_expected_counts(None),
        current_counts=current_counts,
    )


def _matches_existing_node(
    node: dict[str, Any],
    target: BackfillTarget,
    points: list[dict[str, Any]],
) -> bool:
    items = node.get("items", [])
    templates = node.get("templates", [])
    if len(items) != 1 or len(templates) != 1:
        return False

    item = items[0]
    template = templates[0]
    if _normalize_text(node.get("code")) != target.node_code:
        return False
    if _normalize_text(node.get("name")) != target.node_name:
        return False
    if int(item.get("fitting_id") or 0) != target.fitting_id:
        return False
    if int(item.get("quantity") or 0) != 1:
        return False
    if _normalize_text(item.get("role")) != EXPECTED_ROLE:
        return False
    if not bool(item.get("is_required")) or not bool(item.get("affects_processing")):
        return False
    if int(template.get("template_id") or 0) != target.template_id:
        return False
    if not bool(template.get("is_default")):
        return False
    if int(template.get("order_index") or 0) != 0:
        return False
    return len(points) == 2


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _build_session_factory(database_path: Path):
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[unused-argument]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False), engine


def _print_plan(
    database_path: Path,
    plan: BackfillPlan,
    *,
    dry_run: bool,
    backup_path: Path | None = None,
    created_node: dict[str, Any] | None = None,
) -> None:
    print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    print(f"Database: {database_path}")
    print(f"Node code: {plan.target.node_code}")
    print(f"Fitting: id={plan.target.fitting_id}, article={plan.fitting['article'] if plan.fitting else 'n/a'}, code={plan.fitting['code'] if plan.fitting else 'n/a'}")
    print(
        f"Template: id={plan.target.template_id}, "
        f"mounting_variant_key={plan.template['mounting_variant_key'] if plan.template else 'n/a'}"
    )
    print(f"Points loaded: {len(plan.points)}")
    if plan.existing_node is not None:
        print(f"Existing node id: {plan.existing_node['id']}")
    print(f"Planned node name: {plan.target.node_name}")
    print(f"Planned role: {EXPECTED_ROLE}")
    print(f"Planned item quantity: 1")
    print(f"Planned template link default: true")
    print(
        "Current row counts: "
        + ", ".join(f"{key}={value}" for key, value in plan.current_counts.items())
    )
    print(
        "Expected row counts after apply: "
        + ", ".join(f"{key}={value}" for key, value in plan.expected_counts.items())
    )
    if backup_path is not None:
        print(f"Backup: {backup_path}")
        print(f"Backup size: {backup_path.stat().st_size}")
    if created_node is not None:
        print(f"Created node id: {created_node['id']}")
        print(f"Created item id: {created_node['items'][0]['id']}")
        print(f"Created template-link id: {created_node['templates'][0]['id']}")
    if plan.reason:
        print(f"Reason: {plan.reason}")


def _apply_backfill(database_path: Path, plan: BackfillPlan) -> dict[str, Any]:
    with sqlite3.connect(database_path) as connection:
        schema_plan = mounting_nodes_schema._build_plan(connection)
        if not schema_plan["prerequisite_missing"] and any(
            schema_plan[key]
            for key in ("missing_tables", "missing_indexes")
        ):
            mounting_nodes_schema._apply_plan(connection, schema_plan)

    session_factory, engine = _build_session_factory(database_path)
    try:
        with session_factory() as session:
            with MountingNodeService(session=session) as service:
                return service.create_mounting_node(
                    {
                        "code": plan.target.node_code,
                        "name": plan.target.node_name,
                        "description": DEFAULT_NODE_DESCRIPTION,
                        "is_active": True,
                        "items": [
                            {
                                "fitting_id": plan.target.fitting_id,
                                "quantity": 1,
                                "role": EXPECTED_ROLE,
                                "is_required": True,
                                "affects_processing": True,
                                "order_index": 0,
                            }
                        ],
                        "templates": [
                            {
                                "template_id": plan.target.template_id,
                                "is_default": True,
                                "order_index": 0,
                            }
                        ],
                    }
                )
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass

    args = parse_args(argv)
    database_path = _resolve_database_path(args.db_path)
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    target = BackfillTarget(
        node_code=args.node_code,
        node_name=DEFAULT_NODE_NAME,
        description=DEFAULT_NODE_DESCRIPTION,
        fitting_id=args.fitting_id,
        template_id=args.template_id,
    )

    with _open_sqlite(database_path, readonly=True) as connection:
        _require_schema(connection)
        _integrity_check(connection)
        fk_rows_before = _foreign_key_check(connection)
        if fk_rows_before:
            raise SystemExit(f"Foreign key check failed before backfill: {fk_rows_before}")
        plan = _validate_target(connection, target)
        _print_plan(database_path, plan, dry_run=args.dry_run or not args.apply)

    if plan.status == "invalid":
        raise SystemExit(1)

    if args.dry_run or not args.apply:
        return 0

    if plan.is_already_applied:
        print("already applied")
        return 0

    backup_path = _create_backup(database_path)
    created_node = _apply_backfill(database_path, plan)

    with _open_sqlite(database_path, readonly=True) as connection:
        _integrity_check(connection)
        fk_rows_after = _foreign_key_check(connection)
        if fk_rows_after:
            raise SystemExit(f"Foreign key check failed after backfill: {fk_rows_after}")
        current_counts = _current_counts(connection)
        plan = BackfillPlan(
            target=plan.target,
            status=plan.status,
            reason=plan.reason,
            fitting=plan.fitting,
            template=plan.template,
            points=plan.points,
            existing_node=_load_existing_node(connection, plan.target.node_code),
            expected_counts=plan.expected_counts,
            current_counts=current_counts,
        )
        _print_plan(
            database_path,
            plan,
            dry_run=False,
            backup_path=backup_path,
            created_node=created_node,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
