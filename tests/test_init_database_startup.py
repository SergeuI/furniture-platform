from __future__ import annotations

import unittest
from unittest.mock import patch

from database import init_db


class InitDatabaseStartupTests(unittest.TestCase):
    def test_init_database_calls_legacy_migration_without_copying_fittings(self) -> None:
        with patch("database.init_db.Base.metadata.create_all") as create_all, patch(
            "database.init_db.ensure_unified_legacy_schema",
        ) as ensure_unified_legacy_schema, patch(
            "database.init_db.migrate_legacy_sqlite_to_unified_db",
        ) as migrate_legacy_sqlite_to_unified_db, patch(
            "database.init_db.upgrade_sqlite_schema",
        ) as upgrade_sqlite_schema, patch(
            "database.init_db.ensure_fittings_foundation_schema",
        ) as ensure_fittings_foundation_schema, patch(
            "database.init_db.ensure_fitting_products_schema",
        ) as ensure_fitting_products_schema, patch(
            "database.init_db.ensure_fitting_taxonomy_schema",
        ) as ensure_fitting_taxonomy_schema, patch(
            "database.init_db.ensure_mounting_schemes_schema",
        ) as ensure_mounting_schemes_schema, patch(
            "database.init_db._backfill_mounting_node_versions",
        ) as backfill_mounting_node_versions, patch(
            "database.init_db.seed_demo_access_users",
        ) as seed_demo_access_users, patch(
            "database.init_db.seed_default_catalog_items",
        ) as seed_default_catalog_items, patch(
            "database.init_db.seed_default_viyar_service_catalog",
        ) as seed_default_viyar_service_catalog:
            init_db.init_database()

        create_all.assert_called_once()
        ensure_unified_legacy_schema.assert_called_once()
        migrate_legacy_sqlite_to_unified_db.assert_called_once_with(copy_fittings=False)
        upgrade_sqlite_schema.assert_called_once()
        ensure_fittings_foundation_schema.assert_called_once()
        ensure_fitting_products_schema.assert_called_once()
        ensure_fitting_taxonomy_schema.assert_called_once()
        ensure_mounting_schemes_schema.assert_called_once()
        backfill_mounting_node_versions.assert_called_once()
        seed_demo_access_users.assert_called_once()
        seed_default_catalog_items.assert_called_once()
        seed_default_viyar_service_catalog.assert_called_once()


if __name__ == "__main__":
    unittest.main()
