"""Safely initialize or migrate the active SQLite databases.

This script backs up the target database files before running the existing
additive initialization/migration logic.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _resolve_path(raw_value: str | None, default_name: str) -> Path:
    if raw_value:
        path = Path(raw_value).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()
    return (PROJECT_ROOT / default_name).resolve()


def _backup_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.name}.{timestamp}.bak")
    shutil.copy2(path, backup_path)
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Back up and safely initialize the project SQLite databases."
    )
    parser.add_argument(
        "--database",
        default=os.getenv("FURNITURE_PLATFORM_DB_PATH", "furniture_platform.db"),
        help="Path to the main furniture platform database.",
    )
    parser.add_argument(
        "--legacy-database",
        default=os.getenv("FURNITURE_LEGACY_DB_PATH"),
        help="Path to the legacy helper database.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip file backups before running migrations.",
    )
    args = parser.parse_args()

    database_path = _resolve_path(args.database, "furniture_platform.db")
    legacy_database_path = _resolve_path(args.legacy_database, "mebli_calculator.db") if args.legacy_database else None

    if not database_path.exists():
        raise SystemExit(f"Main database was not found: {database_path}")

    if not args.no_backup:
        main_backup = _backup_file(database_path)
        print(f"Main backup: {main_backup}")
        if legacy_database_path is not None and legacy_database_path.exists():
            legacy_backup = _backup_file(legacy_database_path)
            print(f"Legacy backup: {legacy_backup}")
        elif legacy_database_path is not None:
            print(f"Legacy database not found, skipping backup: {legacy_database_path}")

    os.environ["FURNITURE_PLATFORM_DB_PATH"] = str(database_path)
    if legacy_database_path is not None:
        os.environ["FURNITURE_LEGACY_DB_PATH"] = str(legacy_database_path)

    from database.init_db import init_database

    init_database(run_legacy_migration=False)

    print("Database initialization and additive migrations completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
