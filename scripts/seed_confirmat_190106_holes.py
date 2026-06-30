"""Repeatable seed for confirmat 190106 hole templates and points."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ARTICLE = "190106"
TEMPLATE_NAME = "Основний шаблон"
MOUNTING_VARIANT_KEY = "face_to_edge"

DESIRED_TEMPLATE = {
    "name": TEMPLATE_NAME,
    "template_type": "manual",
    "side": "left",
    "coordinate_system": "2d",
    "mounting_variant_key": MOUNTING_VARIANT_KEY,
    "is_default": 1,
    "is_active": 1,
    "notes": None,
}

DESIRED_POINTS = [
    {
        "label": "P1",
        "x_mm": 37.0,
        "y_mm": 50.0,
        "z_mm": 0.0,
        "diameter_mm": 7.0,
        "depth_mm": None,
        "side": "front",
        "operation": "drill",
        "order_index": 1,
        "quantity": 1,
        "mirrored": 0,
        "notes": None,
    },
    {
        "label": "P2",
        "x_mm": 37.0,
        "y_mm": 50.0,
        "z_mm": 0.0,
        "diameter_mm": 4.5,
        "depth_mm": 34.0,
        "side": "left",
        "operation": "drill",
        "order_index": 2,
        "quantity": 1,
        "mirrored": 0,
        "notes": None,
    },
]


@dataclass
class Summary:
    fittings_found: int = 0
    templates_created: int = 0
    templates_updated: int = 0
    templates_skipped: int = 0
    points_inserted: int = 0
    points_updated: int = 0
    points_skipped: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed confirmat 190106 hole templates and points.",
    )
    parser.add_argument(
        "--database",
        default="furniture_platform.db",
        help="Path to furniture_platform.db.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag the script only prints a dry-run plan.",
    )
    return parser.parse_args()


def ensure_safe_database(database_path: Path) -> None:
    if database_path.name == "mebli_calculator.db":
        raise SystemExit("Refusing to modify mebli_calculator.db.")
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")


def create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def values_match(existing: Any, desired: Any) -> bool:
    if existing is None and desired is None:
        return True
    if isinstance(existing, (int, float)) and isinstance(desired, (int, float)):
        return float(existing) == float(desired)
    return existing == desired


def row_matches(row: sqlite3.Row, desired: dict[str, Any]) -> bool:
    for key, value in desired.items():
        if key not in row.keys():
            continue
        if not values_match(row[key], value):
            return False
    return True


def fetch_fittings(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT id, city, article, name FROM fittings WHERE article = ? ORDER BY id",
        (ARTICLE,),
    ).fetchall()


def select_template_candidates(
    connection: sqlite3.Connection,
    fitting_id: int,
    has_mounting_variant_key: bool,
) -> list[sqlite3.Row]:
    columns = [
        "id",
        "fitting_id",
        "name",
        "template_type",
        "side",
        "coordinate_system",
    ]
    if has_mounting_variant_key:
        columns.append("mounting_variant_key")
    columns.extend(["is_default", "is_active", "notes"])

    order_parts = [
        "CASE WHEN name = ? THEN 0 ELSE 1 END",
    ]
    params: list[Any] = [TEMPLATE_NAME]
    if has_mounting_variant_key:
        order_parts.append("CASE WHEN mounting_variant_key = ? THEN 0 ELSE 1 END")
        params.append(MOUNTING_VARIANT_KEY)
    order_parts.extend(["is_default DESC", "is_active DESC", "id ASC"])

    query = f"""
        SELECT {', '.join(columns)}
        FROM fitting_hole_templates
        WHERE fitting_id = ?
        ORDER BY {', '.join(order_parts)}
    """
    params.insert(0, fitting_id)
    return connection.execute(query, params).fetchall()


def choose_template_candidate(candidates: list[sqlite3.Row]) -> sqlite3.Row | None:
    for row in candidates:
        if str(row["name"]).strip() == TEMPLATE_NAME:
            return row
    if candidates:
        return candidates[0]
    return None


def create_template(
    connection: sqlite3.Connection,
    fitting_id: int,
    has_mounting_variant_key: bool,
) -> int:
    columns = [
        "fitting_id",
        "name",
        "template_type",
        "side",
        "coordinate_system",
    ]
    values: list[Any] = [
        fitting_id,
        DESIRED_TEMPLATE["name"],
        DESIRED_TEMPLATE["template_type"],
        DESIRED_TEMPLATE["side"],
        DESIRED_TEMPLATE["coordinate_system"],
    ]
    if has_mounting_variant_key:
        columns.append("mounting_variant_key")
        values.append(DESIRED_TEMPLATE["mounting_variant_key"])
    columns.extend(["is_default", "is_active", "notes"])
    values.extend(
        [
            DESIRED_TEMPLATE["is_default"],
            DESIRED_TEMPLATE["is_active"],
            DESIRED_TEMPLATE["notes"],
        ]
    )
    placeholders = ", ".join(["?"] * len(values))
    connection.execute(
        f"INSERT INTO fitting_hole_templates ({', '.join(columns)}) VALUES ({placeholders})",
        values,
    )
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def update_template(
    connection: sqlite3.Connection,
    template_id: int,
    has_mounting_variant_key: bool,
) -> None:
    columns = [
        "name = ?",
        "template_type = ?",
        "side = ?",
        "coordinate_system = ?",
    ]
    values: list[Any] = [
        DESIRED_TEMPLATE["name"],
        DESIRED_TEMPLATE["template_type"],
        DESIRED_TEMPLATE["side"],
        DESIRED_TEMPLATE["coordinate_system"],
    ]
    if has_mounting_variant_key:
        columns.append("mounting_variant_key = ?")
        values.append(DESIRED_TEMPLATE["mounting_variant_key"])
    columns.extend(["is_default = ?", "is_active = ?", "notes = ?", "updated_at = CURRENT_TIMESTAMP"])
    values.extend(
        [
            DESIRED_TEMPLATE["is_default"],
            DESIRED_TEMPLATE["is_active"],
            DESIRED_TEMPLATE["notes"],
        ]
    )
    values.append(template_id)
    connection.execute(
        f"UPDATE fitting_hole_templates SET {', '.join(columns)} WHERE id = ?",
        values,
    )


def point_columns(existing_columns: set[str]) -> list[str]:
    ordered = [
        "template_id",
        "label",
        "x_mm",
        "y_mm",
        "z_mm",
        "diameter_mm",
        "depth_mm",
        "side",
        "operation",
        "order_index",
        "quantity",
        "mirrored",
        "notes",
    ]
    return [column for column in ordered if column in existing_columns]


def fetch_template_points(connection: sqlite3.Connection, template_id: int) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT *
        FROM fitting_hole_points
        WHERE template_id = ?
        ORDER BY order_index ASC, id ASC
        """,
        (template_id,),
    ).fetchall()


def upsert_points(
    connection: sqlite3.Connection,
    template_id: int,
    apply: bool,
) -> tuple[int, int, int]:
    existing_columns = column_names(connection, "fitting_hole_points")
    columns = point_columns(existing_columns)
    current_rows = fetch_template_points(connection, template_id)
    rows_by_label: dict[str, list[sqlite3.Row]] = {}
    for row in current_rows:
        rows_by_label.setdefault(str(row["label"]), []).append(row)

    inserted = 0
    updated = 0
    skipped = 0
    seen_labels = {point["label"] for point in DESIRED_POINTS}

    for desired in DESIRED_POINTS:
        matches = rows_by_label.get(desired["label"], [])
        primary = matches[0] if matches else None

        if primary is None:
            inserted += 1
            if apply:
                insert_columns = columns
                insert_values = [
                    template_id if column == "template_id" else desired[column]
                    for column in insert_columns
                ]
                placeholders = ", ".join(["?"] * len(insert_values))
                connection.execute(
                    f"INSERT INTO fitting_hole_points ({', '.join(insert_columns)}) VALUES ({placeholders})",
                    insert_values,
                )
            continue

        if row_matches(primary, desired):
            skipped += 1
        else:
            updated += 1
            if apply:
                update_parts = []
                update_values: list[Any] = []
                for column in columns:
                    if column == "template_id":
                        continue
                    update_parts.append(f"{column} = ?")
                    update_values.append(desired[column])
                update_parts.append("updated_at = CURRENT_TIMESTAMP")
                update_values.append(int(primary["id"]))
                connection.execute(
                    f"UPDATE fitting_hole_points SET {', '.join(update_parts)} WHERE id = ?",
                    update_values,
                )

        if len(matches) > 1:
            skipped += len(matches) - 1
            if apply:
                for duplicate in matches[1:]:
                    connection.execute(
                        "DELETE FROM fitting_hole_points WHERE id = ?",
                        (int(duplicate["id"]),),
                    )

    for row in current_rows:
        if str(row["label"]) not in seen_labels:
            skipped += 1
            if apply:
                connection.execute(
                    "DELETE FROM fitting_hole_points WHERE id = ?",
                    (int(row["id"]),),
                )

    return inserted, updated, skipped


def print_summary(summary: Summary, backup_path: Path | None) -> None:
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    print(f"fittings found: {summary.fittings_found}")
    print(f"templates created: {summary.templates_created}")
    print(f"templates updated: {summary.templates_updated}")
    print(f"templates skipped: {summary.templates_skipped}")
    print(f"points inserted: {summary.points_inserted}")
    print(f"points updated: {summary.points_updated}")
    print(f"points skipped: {summary.points_skipped}")


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()
    ensure_safe_database(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        for table in ("fittings", "fitting_hole_templates", "fitting_hole_points"):
            if not table_exists(connection, table):
                raise SystemExit(f"Table '{table}' does not exist.")

        has_mounting_variant_key = "mounting_variant_key" in column_names(
            connection,
            "fitting_hole_templates",
        )

        fittings = fetch_fittings(connection)
        summary = Summary(fittings_found=len(fittings))
        backup_path = create_backup(database_path) if args.apply else None

        if args.apply:
            connection.execute("BEGIN IMMEDIATE")

        for fitting in fittings:
            fitting_id = int(fitting["id"])
            candidates = select_template_candidates(
                connection,
                fitting_id,
                has_mounting_variant_key,
            )
            template = choose_template_candidate(candidates)

            if template is None:
                summary.templates_created += 1
                if args.apply:
                    template_id = create_template(
                        connection,
                        fitting_id,
                        has_mounting_variant_key,
                    )
                    inserted, updated, skipped = upsert_points(
                        connection,
                        template_id,
                        apply=True,
                    )
                    summary.points_inserted += inserted
                    summary.points_updated += updated
                    summary.points_skipped += skipped
                else:
                    summary.points_inserted += 2
                continue

            template_id = int(template["id"])
            if row_matches(template, DESIRED_TEMPLATE):
                summary.templates_skipped += 1
            else:
                summary.templates_updated += 1
                if args.apply:
                    update_template(
                        connection,
                        template_id,
                        has_mounting_variant_key,
                    )

            if len(candidates) > 1:
                summary.templates_skipped += len(candidates) - 1
                if args.apply:
                    # Keep the chosen template and leave other template rows untouched
                    # only if they are outside the exact seed scope.
                    pass

            if args.apply:
                inserted, updated, skipped = upsert_points(
                    connection,
                    template_id,
                    apply=True,
                )
            else:
                inserted, updated, skipped = upsert_points(
                    connection,
                    template_id,
                    apply=False,
                )

            summary.points_inserted += inserted
            summary.points_updated += updated
            summary.points_skipped += skipped

        if args.apply:
            connection.commit()

        print_summary(summary, backup_path)


if __name__ == "__main__":
    main()
