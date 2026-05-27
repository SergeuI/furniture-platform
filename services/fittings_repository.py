import aiosqlite


DB_NAME = "mebli_calculator.db"


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