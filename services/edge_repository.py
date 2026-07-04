import aiosqlite
from services.legacy_db_config import DEFAULT_DB_PATH

DB_NAME = DEFAULT_DB_PATH


# =====================================================
# SAVE EDGE LINKS
# =====================================================

async def save_material_edge(
    material_article,
    edge_04_article,
    edge_08_article
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
            INSERT OR REPLACE INTO material_edges (

                material_article,

                edge_04_article,
                edge_08_article

            )
            VALUES (?, ?, ?)
        """, (
            material_article,
            edge_04_article,
            edge_08_article
        ))

        await db.commit()


# =====================================================
# GET EDGE LINKS
# =====================================================

async def get_material_edges(material_article):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT

                edge_04_article,
                edge_08_article

            FROM material_edges

            WHERE material_article=?
        """, (
            material_article,
        ))

        row = await cursor.fetchone()

        if not row:
            return None

        return {
            "edge_04": row[0],
            "edge_08": row[1]
        }
