import aiosqlite
from services.legacy_db_config import (
    DEFAULT_DB_PATH,
    TELEGRAM_USERS_TABLE,
)

DB_NAME = DEFAULT_DB_PATH



async def get_user_city(telegram_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            f"SELECT citi FROM {TELEGRAM_USERS_TABLE} WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_material_with_price(article: str, city: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT m.name, m.image, m.tg_file_id, p.price
            FROM materials m
            LEFT JOIN material_prices p
            ON m.article = p.article AND p.city = ?
            WHERE m.article = ?
        """, (city, article))

        row = await cursor.fetchone()

        if not row:
            return None

        return {
            "name": row[0],
            "image": row[1],
            "tg_file_id": row[2],
            "price": row[3] if row[3] is not None else 0
        }

