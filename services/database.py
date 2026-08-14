import aiosqlite
from services.legacy_db_config import (
    DEFAULT_DB_PATH,
    TELEGRAM_PROJECTS_TABLE,
    TELEGRAM_USERS_TABLE,
    ensure_unified_legacy_schema,
    migrate_legacy_sqlite_to_unified_db,
)

DB_NAME = DEFAULT_DB_PATH

# =====================================================
# INIT DATABASE
# =====================================================

async def init_db():

    ensure_unified_legacy_schema(DB_NAME)
    # Normal bot startup must not repopulate legacy fittings.
    migrate_legacy_sqlite_to_unified_db(DB_NAME, copy_fittings=False)

    async with aiosqlite.connect(DB_NAME) as db:

        # =====================================================
        # USERS
        # =====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS telegram_users (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                telegram_id INTEGER UNIQUE,

                name TEXT,
                phone TEXT,
                citi TEXT,
                email TEXT
            )
        """)

        # =====================================================
        # CALCULATIONS
        # =====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS calculations (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                telegram_id INTEGER,

                category TEXT,
                subcategory TEXT,

                params TEXT
            )
        """)

        # =====================================================
        # MATERIALS
        # =====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS materials (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                article TEXT UNIQUE,

                name TEXT,
                image TEXT,

                category TEXT,

                tg_file_id TEXT
            )
        """)

        # =====================================================
        # MATERIAL PRICES
        # =====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS material_prices (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                article TEXT,
                city TEXT,

                price REAL,

                UNIQUE(article, city)
            )
        """)

        # =====================================================
        # SERVICES PRICES
        # =====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS services_prices (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                article TEXT,

                name TEXT,

                city TEXT,

                service_type TEXT,

                price REAL,

                UNIQUE(article, city)
            )
        """)

        # =====================================================
        # MATERIAL EDGES
        # =====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS material_edges (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                material_article TEXT UNIQUE,

                edge_04_article TEXT,
                edge_08_article TEXT
            )
        """)


        # =====================================================
        # Fiting
        # =====================================================

        await db.execute("""
            CREATE TABLE IF NOT EXISTS fittings (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                city TEXT,

                code TEXT,

                article TEXT,

                name TEXT,

                price REAL,

                stock TEXT,

                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS telegram_projects (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                project_id TEXT UNIQUE,

                telegram_id INTEGER,

                params_json TEXT,

                project_json TEXT,

                cutting_json TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)    

        # =====================================================
        # INDEXES
        # =====================================================

        await db.execute("""

        CREATE INDEX IF NOT EXISTS idx_users_tg

        ON telegram_users(telegram_id)

        """)

        await db.execute("""

        CREATE INDEX IF NOT EXISTS idx_projects_tg

        ON telegram_projects(telegram_id)

        """)

        await db.execute("""

        CREATE INDEX IF NOT EXISTS idx_material_prices

        ON material_prices(article, city)

        """)

        await db.execute("""

        CREATE INDEX IF NOT EXISTS idx_materials_article

        ON materials(article)

        """)   

        await db.commit()


async def get_materials_by_category_and_length(category, length, city):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute("""
            SELECT 
                m.article,
                m.name,
                m.image,
                mp.price,
                m.tg_file_id
            FROM materials m

            LEFT JOIN material_prices mp
                ON m.article = mp.article
                AND mp.city = ?

            WHERE m.category = ?
            AND (
                m.name LIKE ?
                OR m.name LIKE ?
                OR m.name LIKE ?
                OR m.name LIKE ?
                OR m.name LIKE ?
                OR m.name LIKE ?
            )
        """, (
            city,
            category,
            f"%L={length}%",
            f"%NL={length}%",
            f"%{length}mm%",
            f"%{length} mm%",
            f"%{length}мм%",
            f"%{length} мм%",
        ))

        rows = await cursor.fetchall()

        # =========================
        # FALLBACK ДЛЯ slides_tipon
        # =========================

        if not rows and category == "slides_tipon" and length == 600:

            cursor = await db.execute("""
                SELECT 
                    m.article,
                    m.name,
                    m.image,
                    mp.price,
                    m.tg_file_id
                FROM materials m

                LEFT JOIN material_prices mp
                    ON m.article = mp.article
                    AND mp.city = ?

                WHERE m.category = ?
                AND (
                    m.name LIKE ?
                    OR m.name LIKE ?
                    OR m.name LIKE ?
                    OR m.name LIKE ?
                    OR m.name LIKE ?
                    OR m.name LIKE ?
                )
            """, (
                city,
                category,
                "%L=550%",
                "%NL=550%",
                "%550mm%",
                "%550 mm%",
                "%550мм%",
                "%550 мм%",
            ))

            rows = await cursor.fetchall()

    result = []

    for r in rows:
        result.append({
            "article": r[0],
            "name": r[1],
            "image": r[2],
            "price": r[3] if r[3] else 0,
            "tg_file_id": r[4]
        })

    return result
