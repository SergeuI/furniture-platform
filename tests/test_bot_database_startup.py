from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from services import database as bot_database


class BotDatabaseStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_bot_init_db_skips_copying_legacy_fittings(self) -> None:
        mock_connection = AsyncMock()
        mock_connection.__aenter__.return_value = mock_connection
        mock_connection.__aexit__.return_value = False

        with patch.object(bot_database, "ensure_unified_legacy_schema") as ensure_schema, patch.object(
            bot_database,
            "migrate_legacy_sqlite_to_unified_db",
        ) as migrate_legacy, patch.object(bot_database.aiosqlite, "connect", return_value=mock_connection):
            await bot_database.init_db()

        ensure_schema.assert_called_once_with(bot_database.DB_NAME)
        migrate_legacy.assert_called_once_with(bot_database.DB_NAME, copy_fittings=False)
        mock_connection.execute.assert_any_call(
            """
            CREATE TABLE IF NOT EXISTS telegram_users (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                telegram_id INTEGER UNIQUE,

                name TEXT,
                phone TEXT,
                citi TEXT,
                email TEXT
            )
        """
        )


if __name__ == "__main__":
    unittest.main()
