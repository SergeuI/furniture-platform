import aiosqlite
from services.legacy_db_config import DEFAULT_DB_PATH

DB_NAME = DEFAULT_DB_PATH


async def save_fitting(

    city,
    code,
    article,
    name,
    price
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(

            """
            INSERT INTO fittings (

                city,
                code,
                article,
                name,
                price

            )

            VALUES (?, ?, ?, ?, ?)
            """,

            (
                city,
                code,
                article,
                name,
                price
            )
        )

        await db.commit()
