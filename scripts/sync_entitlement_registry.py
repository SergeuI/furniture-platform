"""Dry-run/apply sync for the centralized entitlement registry."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from services.entitlement_registry_sync_service import EntitlementRegistrySyncService


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize the centralized entitlement registry.",
    )
    parser.add_argument(
        "--database",
        default="furniture_platform.db",
        help="Path to the SQLite database.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes after dry-run validation.",
    )
    return parser.parse_args()


def _create_backup(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.name}.{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def _print_plan(plan: dict[str, object]) -> None:
    print(f"New features: {len(plan['new_features'])}")
    if plan["new_features"]:
        print("  - " + ", ".join(item["feature_key"] for item in plan["new_features"]))
    print(f"Metadata updates: {len(plan['metadata_updates'])}")
    if plan["metadata_updates"]:
        print("  - " + ", ".join(item["feature_key"] for item in plan["metadata_updates"]))
    print(f"Missing plan rows: {len(plan['missing_plan_rows'])}")
    if plan["missing_plan_rows"]:
        print(
            "  - "
            + ", ".join(
                f"{item['feature_key']}[{', '.join(item['missing_plan_codes'])}]"
                for item in plan["missing_plan_rows"]
            )
        )
    print(f"Conflicts: {len(plan['conflicts'])}")
    if plan["conflicts"]:
        print(
            "  - "
            + ", ".join(
                f"{item['feature_key']}:{item['reason']}"
                for item in plan["conflicts"]
            )
        )
    print(f"Unchanged: {len(plan['unchanged'])}")
    if plan["unchanged"]:
        print("  - " + ", ".join(plan["unchanged"]))
    print(
        "Registry features missing from DB: "
        f"{len(plan['registry_features_missing_from_db'])}"
    )
    if plan["registry_features_missing_from_db"]:
        print("  - " + ", ".join(plan["registry_features_missing_from_db"]))
    print(
        "DB system features missing from registry: "
        f"{len(plan['db_system_features_missing_from_registry'])}"
    )
    if plan["db_system_features_missing_from_registry"]:
        print("  - " + ", ".join(plan["db_system_features_missing_from_registry"]))


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()
    if not database_path.exists():
        raise SystemExit(f"Database does not exist: {database_path}")

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    backup_path: Path | None = None
    try:
        with Session() as session:
            service = EntitlementRegistrySyncService(session=session)
            plan = service.plan_sync()

            print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
            print(f"Database: {database_path}")
            _print_plan(plan)

            if plan["conflicts"]:
                raise SystemExit(1)

            if not args.apply:
                return

            if any(
                plan[key]
                for key in ("new_features", "metadata_updates", "missing_plan_rows")
            ):
                backup_path = _create_backup(database_path)
                print(f"Backup: {backup_path}")
                result = service.apply_sync()
                print(f"Applied: {result['applied']}")
                print(f"Created features: {len(result['created_features'])}")
                print(f"Updated features: {len(result['updated_features'])}")
                print(f"Created plan rows: {len(result['created_plan_rows'])}")
                print(
                    "Orphaned system features: "
                    f"{len(result['orphaned_system_feature_keys'])}"
                )
            else:
                print("No changes required.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
