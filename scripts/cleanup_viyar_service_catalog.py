import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.viyar_service_catalog_service import _is_blocked_viyar_service_name


def _backup_database(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _fetch_suspicious_items(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT id, external_code, name, is_active, item_type
        FROM service_catalog_items
        WHERE source = 'viyar'
          AND item_type = 'service'
        ORDER BY folder_path, sort_order, name
        """
    ).fetchall()

    return [row for row in rows if _is_blocked_viyar_service_name(row["name"])]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Disable suspicious Viyar service catalog rows without deleting them."
    )
    parser.add_argument("--database", default="furniture_platform.db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    database_path = Path(args.database).resolve()
    if not database_path.is_file():
        raise SystemExit(f"Database was not found: {database_path}")

    connection = sqlite3.connect(database_path)
    try:
        suspicious_items = _fetch_suspicious_items(connection)

        if not suspicious_items:
            print("No suspicious Viyar service rows were found.")
            return 0

        print(f"Suspicious Viyar service rows: {len(suspicious_items)}")
        for row in suspicious_items[:50]:
            status = "active" if row["is_active"] else "inactive"
            print(f"- {row['external_code']} | {row['name']} | {status}")

        if not args.apply:
            print("DRY RUN - no database changes were saved")
            return 0

        backup_path = _backup_database(database_path)
        connection.executemany(
            """
            UPDATE service_catalog_items
            SET is_active = 0
            WHERE id = ?
            """,
            [(row["id"],) for row in suspicious_items if row["is_active"]],
        )
        connection.commit()
        print(f"Backup: {backup_path}")
        print(f"Disabled rows: {sum(1 for row in suspicious_items if row['is_active'])}")
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
