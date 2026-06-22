import argparse
import base64
import json
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


CATALOG_TABLES = (
    "materials",
    "material_prices",
    "material_edge_options",
    "material_edge_prices",
    "fittings",
    "service_catalog_items",
)


def _encode_value(value):
    if isinstance(value, bytes):
        return {"__bytes__": base64.b64encode(value).decode("ascii")}
    return value


def _decode_value(value):
    if isinstance(value, dict) and set(value) == {"__bytes__"}:
        return base64.b64decode(value["__bytes__"])
    return value


def _rows(connection: sqlite3.Connection, query: str, parameters=()) -> list[dict]:
    cursor = connection.execute(query, parameters)
    columns = [item[0] for item in cursor.description]
    return [
        {column: _encode_value(value) for column, value in zip(columns, row)}
        for row in cursor.fetchall()
    ]


def export_snapshot(database_path: Path, output_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    try:
        edge_rows = _rows(connection, "SELECT * FROM material_edge_options")
        edge_lookup = {
            row["id"]: (row["material_article"], row["edge_key"])
            for row in edge_rows
        }
        edge_prices = _rows(connection, "SELECT * FROM material_edge_prices")
        for row in edge_prices:
            material_article, edge_key = edge_lookup.get(row["edge_option_id"], (None, None))
            row["_material_article"] = material_article
            row["_edge_key"] = edge_key

        payload = {
            "format": "mproject-catalog-v1",
            "tables": {
                "materials": _rows(connection, "SELECT * FROM materials"),
                "material_prices": _rows(connection, "SELECT * FROM material_prices"),
                "material_edge_options": edge_rows,
                "material_edge_prices": edge_prices,
                "fittings": _rows(
                    connection,
                    "SELECT * FROM fittings WHERE COALESCE(is_system, 1) = 1",
                ),
                "service_catalog_items": _rows(
                    connection,
                    "SELECT * FROM service_catalog_items WHERE source = 'viyar'",
                ),
            },
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    finally:
        connection.close()

    counts = {name: len(rows) for name, rows in payload["tables"].items()}
    print(f"Snapshot: {output_path}")
    print("Rows: " + ", ".join(f"{name}={count}" for name, count in counts.items()))


def _find_id(connection, table: str, conditions: dict):
    clauses = []
    values = []
    for column, value in conditions.items():
        if value is None:
            clauses.append(f"{column} IS NULL")
        else:
            clauses.append(f"{column} = ?")
            values.append(value)
    row = connection.execute(
        f"SELECT id FROM {table} WHERE {' AND '.join(clauses)} LIMIT 1",
        values,
    ).fetchone()
    return row[0] if row else None


def _upsert_row(connection, table: str, raw_row: dict, conditions: dict):
    row = {
        key: _decode_value(value)
        for key, value in raw_row.items()
        if not key.startswith("_")
    }
    existing_id = _find_id(connection, table, conditions)
    writable = {key: value for key, value in row.items() if key != "id"}

    if existing_id is not None:
        assignments = ", ".join(f"{key} = ?" for key in writable)
        connection.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?",
            [*writable.values(), existing_id],
        )
        return existing_id

    columns = list(writable)
    values = list(writable.values())
    if table == "service_catalog_items":
        columns.insert(0, "id")
        values.insert(0, str(uuid.uuid4()))
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        values,
    )
    return connection.execute("SELECT last_insert_rowid()").fetchone()[0]


def import_snapshot(database_path: Path, input_path: Path, apply: bool) -> None:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload.get("format") != "mproject-catalog-v1":
        raise SystemExit("Unsupported catalog snapshot format")

    backup_path = None
    if apply:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
        shutil.copy2(database_path, backup_path)

    connection = sqlite3.connect(database_path)
    counts = {name: 0 for name in CATALOG_TABLES}
    edge_id_map = {}
    try:
        connection.execute("BEGIN")
        tables = payload["tables"]

        for row in tables["materials"]:
            _upsert_row(connection, "materials", row, {"article": row["article"]})
            counts["materials"] += 1

        for row in tables["material_prices"]:
            _upsert_row(
                connection,
                "material_prices",
                row,
                {"article": row["article"], "city": row.get("city")},
            )
            counts["material_prices"] += 1

        for row in tables["material_edge_options"]:
            target_id = _upsert_row(
                connection,
                "material_edge_options",
                row,
                {
                    "material_article": row["material_article"],
                    "edge_key": row["edge_key"],
                },
            )
            edge_id_map[row["id"]] = target_id
            counts["material_edge_options"] += 1

        for row in tables["material_edge_prices"]:
            target_edge_id = edge_id_map.get(row["edge_option_id"])
            if target_edge_id is None and row.get("_material_article") and row.get("_edge_key"):
                target_edge_id = _find_id(
                    connection,
                    "material_edge_options",
                    {
                        "material_article": row["_material_article"],
                        "edge_key": row["_edge_key"],
                    },
                )
            if target_edge_id is None:
                continue
            row = {**row, "edge_option_id": target_edge_id}
            _upsert_row(
                connection,
                "material_edge_prices",
                row,
                {"edge_option_id": target_edge_id, "city": row["city"]},
            )
            counts["material_edge_prices"] += 1

        for row in tables["fittings"]:
            source_url = str(row.get("source_url") or "").strip()
            conditions = (
                {"source_url": source_url}
                if source_url
                else {
                    "article": row.get("article"),
                    "city": row.get("city"),
                    "name": row.get("name"),
                }
            )
            _upsert_row(connection, "fittings", row, conditions)
            counts["fittings"] += 1

        for row in tables["service_catalog_items"]:
            _upsert_row(
                connection,
                "service_catalog_items",
                row,
                {"source": row["source"], "external_code": row["external_code"]},
            )
            counts["service_catalog_items"] += 1

        if apply:
            connection.commit()
        else:
            connection.rollback()
    finally:
        connection.close()

    print("APPLIED" if apply else "DRY RUN - no database changes were saved")
    if backup_path:
        print(f"Backup: {backup_path}")
    print("Rows: " + ", ".join(f"{name}={count}" for name, count in counts.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description="Export or merge MProject catalog data.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--database", default="furniture_platform.db")
    export_parser.add_argument("--output", required=True)

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--database", default="furniture_platform.db")
    import_parser.add_argument("--input", required=True)
    import_parser.add_argument("--apply", action="store_true")

    args = parser.parse_args()
    database_path = Path(args.database).resolve()
    if not database_path.is_file():
        raise SystemExit(f"Database was not found: {database_path}")

    if args.command == "export":
        export_snapshot(database_path, Path(args.output).resolve())
    else:
        import_snapshot(database_path, Path(args.input).resolve(), args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
