from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from services import database as bot_database


class BotDatabaseStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_bot_init_db_skips_copying_legacy_fittings_by_default(self) -> None:
        mock_connection = AsyncMock()
        mock_connection.__aenter__.return_value = mock_connection
        mock_connection.__aexit__.return_value = False

        with patch.object(bot_database, "ensure_unified_legacy_schema") as ensure_schema, patch.object(
            bot_database,
            "migrate_legacy_sqlite_to_unified_db",
        ) as migrate_legacy, patch.object(bot_database.aiosqlite, "connect", return_value=mock_connection):
            await bot_database.init_db()

        ensure_schema.assert_called_once_with(bot_database.DB_NAME)
        migrate_legacy.assert_not_called()
        self.assertGreater(mock_connection.execute.call_count, 0)

    async def test_bot_init_db_can_explicitly_run_legacy_migration(self) -> None:
        mock_connection = AsyncMock()
        mock_connection.__aenter__.return_value = mock_connection
        mock_connection.__aexit__.return_value = False

        with patch.object(bot_database, "ensure_unified_legacy_schema"), patch.object(
            bot_database,
            "migrate_legacy_sqlite_to_unified_db",
        ) as migrate_legacy, patch.object(bot_database.aiosqlite, "connect", return_value=mock_connection):
            await bot_database.init_db(run_legacy_migration=True)

        migrate_legacy.assert_called_once_with(bot_database.DB_NAME, copy_fittings=False)


if __name__ == "__main__":
    unittest.main()
