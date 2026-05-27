import os
import json
import aiosqlite

from dotenv import load_dotenv

load_dotenv()

DB_NAME = "mebli_calculator.db"

ADMIN_ID = os.getenv(
    "ADMIN_ID"
)

ADMIN_ID = (
    int(ADMIN_ID)
    if ADMIN_ID
    else None
)


async def cache_image(

    bot,

    url,

    article
):

    import aiohttp

    from aiogram.types import (
        BufferedInputFile
    )

    async with aiohttp.ClientSession() as session:

        async with session.get(
            url
        ) as resp:

            if resp.status != 200:

                return None

            data = await resp.read()

    msg = await bot.send_photo(

        chat_id=ADMIN_ID,

        photo=BufferedInputFile(
            data,
            filename="img.jpg"
        )
    )

    file_id = msg.photo[-1].file_id

    async with aiosqlite.connect(
        DB_NAME
    ) as db:

        await db.execute(
            """
            UPDATE materials
            SET tg_file_id = ?
            WHERE article = ?
            """,
            (
                file_id,
                article
            )
        )

        await db.commit()

    return file_id


async def save_calculation(

    tg_id,

    category,

    subcategory,

    params
):

    async with aiosqlite.connect(
        DB_NAME
    ) as db:

        await db.execute(
            """
            INSERT INTO calculations (
                telegram_id,
                category,
                subcategory,
                params
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                tg_id,
                category,
                subcategory,
                json.dumps(params)
            )
        )

        await db.commit()


async def seed_materials():

    materials = [

        (
            "215557",
            "ДСП Egger Дуб Сонома",
            "images/mat1.jpg"
        ),

        (
            "43102",
            "ДСП Білий",
            "images/mat2.jpg"
        ),
    ]

    prices = [

        (
            "215557",
            "kyiv",
            850
        ),

        (
            "215557",
            "lviv",
            870
        ),

        (
            "43102",
            "kyiv",
            620
        ),

        (
            "43102",
            "lviv",
            640
        ),
    ]

    async with aiosqlite.connect(
        DB_NAME
    ) as db:

        for m in materials:

            await db.execute(
                """
                INSERT OR IGNORE INTO materials (
                    article,
                    name,
                    image
                )
                VALUES (?, ?, ?)
                """,
                m
            )

        for p in prices:

            await db.execute(
                """
                INSERT OR REPLACE
                INTO material_prices (
                    article,
                    city,
                    price
                )
                VALUES (?, ?, ?)
                """,
                p
            )

        await db.commit()



