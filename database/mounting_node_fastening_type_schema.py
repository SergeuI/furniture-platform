"""Schema-only upgrade for mounting node fastening types (dry-run by default)."""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


def needs_upgrade(connection: sqlite3.Connection) -> bool:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(mounting_nodes)")}
    if not columns:
        raise ValueError("mounting_nodes table does not exist")
    return "fastening_type" not in columns


def apply_schema(connection: sqlite3.Connection) -> bool:
    if not needs_upgrade(connection):
        return False
    connection.execute("ALTER TABLE mounting_nodes ADD COLUMN fastening_type VARCHAR(32) NULL")
    connection.commit()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="furniture_platform.db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    path = Path(args.database).resolve()
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as connection:
        if not needs_upgrade(connection):
            print("Schema is up to date")
            return
        print("Add mounting_nodes.fastening_type VARCHAR(32) NULL; no data updates")
        if not args.apply:
            print("Dry run: database unchanged")
            return
        backup = path.with_name(f"{path.name}.{datetime.now():%Y%m%d-%H%M%S-%f}.bak")
        with sqlite3.connect(backup) as target:
            connection.backup(target)
    with sqlite3.connect(path) as connection:
        apply_schema(connection)
    print(f"Applied; backup: {backup}")


if __name__ == "__main__":
    main()
