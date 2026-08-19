from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_DATABASE_NAME = "furniture_platform.db"
DEFAULT_NODE_ID = 1
DEFAULT_NODE_CODE = "mounting-node-node-cd9f6187"
DEFAULT_NODE_NAME = "Рафікс"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove an obsolete mounting node after dependency audit.")
    parser.add_argument("--database", default=DEFAULT_DATABASE_NAME, help="Path to furniture_platform.db.")
    parser.add_argument("--node-id", type=int, default=DEFAULT_NODE_ID, help="Expected mounting node id.")
    parser.add_argument("--node-code", default=DEFAULT_NODE_CODE, help="Expected mounting node code.")
    parser.add_argument("--node-name", default=DEFAULT_NODE_NAME, help="Expected mounting node name.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Without this flag the script only prints a dry-run plan.")
    return parser.parse_args()


def _open_sqlite(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


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


def _load_node(connection: sqlite3.Connection, node_id: int) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM mounting_nodes WHERE id = ?",
        (node_id,),
    ).fetchone()


def _discover_external_dependencies(connection: sqlite3.Connection, *, node_id: int) -> dict[str, list[int]]:
    dependencies: dict[str, list[int]] = defaultdict(list)
    allowed_tables = {"mounting_node_items", "mounting_node_templates"}
    tables = [
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchall()
    ]
    for table_name in tables:
        for fk in connection.execute(f"PRAGMA foreign_key_list({table_name})").fetchall():
            if str(fk["table"]) != "mounting_nodes":
                continue
            if table_name in allowed_tables:
                continue
            dependent_rows = connection.execute(
                f"SELECT id FROM {table_name} WHERE {fk['from']} = ?",
                (node_id,),
            ).fetchall()
            if dependent_rows:
                dependencies[table_name].extend(int(row["id"]) for row in dependent_rows)
    return dependencies


def _node_owned_counts(connection: sqlite3.Connection, node_id: int) -> dict[str, int]:
    counts = {
        "mounting_node_items": 0,
        "mounting_node_templates": 0,
        "mounting_node_versions": 0,
    }
    if _table_exists(connection, "mounting_node_items"):
        counts["mounting_node_items"] = int(
            connection.execute("SELECT COUNT(*) FROM mounting_node_items WHERE node_id = ?", (node_id,)).fetchone()[0]
        )
    if _table_exists(connection, "mounting_node_templates"):
        counts["mounting_node_templates"] = int(
            connection.execute("SELECT COUNT(*) FROM mounting_node_templates WHERE node_id = ?", (node_id,)).fetchone()[0]
        )
    if _table_exists(connection, "mounting_node_versions"):
        counts["mounting_node_versions"] = int(
            connection.execute("SELECT COUNT(*) FROM mounting_node_versions WHERE node_id = ?", (node_id,)).fetchone()[0]
        )
    return counts


def _build_plan(connection: sqlite3.Connection, *, node_id: int, node_code: str, node_name: str) -> dict[str, Any]:
    node = _load_node(connection, node_id)
    if node is None:
        return {"status": "not_found", "node": None, "external_dependencies": {}, "node_owned_counts": {}}

    exact_match = (
        int(node["id"]) == int(node_id)
        and str(node["code"]) == str(node_code)
        and str(node["name"]) == str(node_name)
        and node["owner_user_id"] is None
    )
    if not exact_match:
        return {
            "status": "mismatch",
            "node": dict(node),
            "external_dependencies": {},
            "node_owned_counts": _node_owned_counts(connection, node_id),
        }

    external_dependencies = _discover_external_dependencies(connection, node_id=node_id)
    node_owned_counts = _node_owned_counts(connection, node_id)
    can_apply = not external_dependencies
    return {
        "status": "ready" if can_apply else "blocked",
        "node": dict(node),
        "external_dependencies": external_dependencies,
        "node_owned_counts": node_owned_counts,
    }


def _apply_plan(connection: sqlite3.Connection, *, node_id: int) -> dict[str, int]:
    deleted_counts = {"mounting_node_versions": 0, "mounting_nodes": 0}
    if _table_exists(connection, "mounting_node_versions"):
        deleted_counts["mounting_node_versions"] = int(
            connection.execute("DELETE FROM mounting_node_versions WHERE node_id = ?", (node_id,)).rowcount
        )
    deleted_counts["mounting_nodes"] = int(
        connection.execute("DELETE FROM mounting_nodes WHERE id = ?", (node_id,)).rowcount
    )
    return deleted_counts


def cleanup_mounting_node(database_path: Path, *, node_id: int, node_code: str, node_name: str, apply: bool) -> dict[str, Any]:
    backup_path = _create_backup(database_path) if apply else None
    connection = _open_sqlite(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        plan = _build_plan(connection, node_id=node_id, node_code=node_code, node_name=node_name)
        if plan["status"] == "ready" and apply:
            deleted_counts = _apply_plan(connection, node_id=node_id)
            connection.commit()
        else:
            deleted_counts = {"mounting_node_versions": 0, "mounting_nodes": 0}
            connection.rollback()
        return {
            "apply": apply,
            "backup_path": backup_path,
            "plan": plan,
            "deleted_counts": deleted_counts,
            "integrity_check": _integrity_check(connection),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).expanduser().resolve()
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    result = cleanup_mounting_node(
        database_path,
        node_id=args.node_id,
        node_code=args.node_code,
        node_name=args.node_name,
        apply=args.apply,
    )
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Database: {database_path}")
    if result.get("backup_path"):
        print(f"Backup: {result['backup_path']}")
    print(f"Status: {result['plan']['status']}")
    if result["plan"].get("node"):
        node = result["plan"]["node"]
        print(f"Node: id={node['id']} code={node['code']} name={node['name']}")
    if result["plan"].get("node_owned_counts"):
        print("Node-owned rows:")
        for table_name, count in sorted(result["plan"]["node_owned_counts"].items()):
            print(f"  - {table_name}: {count}")
    if result["plan"].get("external_dependencies"):
        print("External blockers:")
        for table_name, ids in sorted(result["plan"]["external_dependencies"].items()):
            print(f"  - {table_name}: {ids}")
    print("Deleted counts: " + ", ".join(f"{k}={v}" for k, v in sorted(result["deleted_counts"].items())))
    print(f"Integrity check: {result['integrity_check']}")


if __name__ == "__main__":
    main()
