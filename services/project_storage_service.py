import json
import uuid
import aiosqlite
import logging


DB_NAME = "mebli_calculator.db"


# =====================================================
# SAVE PROJECT
# =====================================================

async def save_project(

    telegram_id,
    params,
    project,
    cutting
):

    project_id = str(
        uuid.uuid4()
    )

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(

            """
            INSERT INTO projects (

                project_id,
                telegram_id,
                params_json,
                project_json,
                cutting_json

            )

            VALUES (?, ?, ?, ?, ?)
            """,

            (
                project_id,

                telegram_id,

                json.dumps(
                    params,
                    ensure_ascii=False
                ),

                json.dumps(
                    project,
                    ensure_ascii=False
                ),

                json.dumps(
                    cutting,
                    ensure_ascii=False
                )
            )
        )

        await db.commit()

    logging.info(
        f"PROJECT SAVED: {project_id}"
    )

    return project_id


# =====================================================
# GET PROJECT
# =====================================================

async def get_project(
    project_id
):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(

            """
            SELECT

                params_json,
                project_json,
                cutting_json

            FROM projects

            WHERE project_id = ?
            """,

            (project_id,)
        )

        row = await cursor.fetchone()

    if not row:
        return None

    return {

        "params": json.loads(row[0]),

        "project": json.loads(row[1]),

        "cutting": json.loads(row[2])
    }