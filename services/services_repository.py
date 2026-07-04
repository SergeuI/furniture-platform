import aiosqlite
from services.legacy_db_config import DEFAULT_DB_PATH

DB_NAME = DEFAULT_DB_PATH


# =====================================================
# GET SERVICE PRICE
# =====================================================

async def get_service_price(
    service_type,
    city
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT price

            FROM services_prices

            WHERE service_type=?
            AND city=?

            LIMIT 1
        """, (
            service_type,
            city
        ))

        row = await cursor.fetchone()

        if not row:
            return 0

        return row[0]
