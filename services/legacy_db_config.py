import os
import sqlite3


DEFAULT_DB_PATH = "furniture_platform.db"
LEGACY_DB_PATH = "mebli_calculator.db"

TELEGRAM_USERS_TABLE = "telegram_users"
TELEGRAM_PROJECTS_TABLE = "telegram_projects"


def _table_exists(
    cursor,
    schema_name: str,
    table_name: str
) -> bool:

    cursor.execute(
        f"""
        SELECT 1
        FROM {schema_name}.sqlite_master
        WHERE type = 'table'
        AND name = ?
        """,
        (table_name,)
    )

    return cursor.fetchone() is not None


def ensure_unified_legacy_schema(
    db_path: str = DEFAULT_DB_PATH
) -> None:

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TELEGRAM_USERS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            name TEXT,
            phone TEXT,
            citi TEXT,
            email TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            category TEXT,
            subcategory TEXT,
            params TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article TEXT UNIQUE,
            name TEXT,
            description TEXT,
            color TEXT,
            dimensions TEXT,
            thickness TEXT,
            image TEXT,
            source_url TEXT,
            owner_user_id TEXT,
            category TEXT,
            tg_file_id TEXT,
            is_default INTEGER NOT NULL DEFAULT 0,
            image_cached_bytes BLOB,
            image_cached_content_type TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS material_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article TEXT,
            city TEXT,
            price REAL,
            UNIQUE(article, city)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS material_edge_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_article TEXT,
            edge_key TEXT,
            article TEXT,
            name TEXT,
            thickness_label TEXT,
            image TEXT,
            source_url TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS material_edge_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            edge_option_id INTEGER,
            city TEXT,
            price REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS services_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article TEXT,
            name TEXT,
            city TEXT,
            service_type TEXT,
            price REAL,
            UNIQUE(article, city)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS material_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_article TEXT UNIQUE,
            edge_04_article TEXT,
            edge_08_article TEXT
        )
        """
    )

    cursor.execute(
        """
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
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TELEGRAM_PROJECTS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT UNIQUE,
            telegram_id INTEGER,
            params_json TEXT,
            project_json TEXT,
            cutting_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS production_users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            project_name TEXT,
            created_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS parts (
            part_id TEXT PRIMARY KEY,
            order_id INTEGER,
            name TEXT,
            width REAL,
            height REAL,
            thickness REAL,
            qty INTEGER,
            material TEXT,
            created_at TEXT,
            FOREIGN KEY(order_id) REFERENCES orders(order_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS production_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id TEXT,
            stage TEXT,
            operator TEXT,
            changed_at TEXT,
            FOREIGN KEY(part_id) REFERENCES parts(part_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS machining_operations (
            operation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id TEXT,
            operation_type TEXT,
            tool_id TEXT,
            x REAL,
            y REAL,
            z REAL,
            depth REAL,
            created_at TEXT,
            FOREIGN KEY(part_id) REFERENCES parts(part_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS nesting_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id TEXT,
            sheet_id INTEGER,
            pos_x REAL,
            pos_y REAL,
            rotated INTEGER,
            created_at TEXT,
            FOREIGN KEY(part_id) REFERENCES parts(part_id)
        )
        """
    )

    cursor.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{TELEGRAM_USERS_TABLE}_tg
        ON {TELEGRAM_USERS_TABLE}(telegram_id)
        """
    )

    cursor.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{TELEGRAM_PROJECTS_TABLE}_tg
        ON {TELEGRAM_PROJECTS_TABLE}(telegram_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_material_prices
        ON material_prices(article, city)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_material_edge_options_material
        ON material_edge_options(material_article, edge_key)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_material_edge_prices_lookup
        ON material_edge_prices(edge_option_id, city)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_materials_article
        ON materials(article)
        """
    )

    connection.commit()
    connection.close()


def migrate_legacy_sqlite_to_unified_db(
    target_db_path: str = DEFAULT_DB_PATH,
    legacy_db_path: str = LEGACY_DB_PATH
) -> None:

    if not os.path.exists(legacy_db_path):
        return

    if os.path.abspath(target_db_path) == os.path.abspath(legacy_db_path):
        return

    ensure_unified_legacy_schema(target_db_path)

    connection = sqlite3.connect(target_db_path)
    cursor = connection.cursor()

    cursor.execute(
        "ATTACH DATABASE ? AS legacydb",
        (legacy_db_path,)
    )

    mappings = [
        (
            TELEGRAM_USERS_TABLE,
            "users",
            ["id", "telegram_id", "name", "phone", "citi", "email"],
            "INSERT OR IGNORE",
        ),
        (
            "calculations",
            "calculations",
            ["id", "telegram_id", "category", "subcategory", "params"],
            "INSERT OR IGNORE",
        ),
        (
            "materials",
            "materials",
            ["id", "article", "name", "image", "category", "tg_file_id"],
            "INSERT OR IGNORE",
        ),
        (
            "material_prices",
            "material_prices",
            ["id", "article", "city", "price"],
            "INSERT OR IGNORE",
        ),
        (
            "services_prices",
            "services_prices",
            ["id", "article", "name", "city", "service_type", "price"],
            "INSERT OR IGNORE",
        ),
        (
            "material_edges",
            "material_edges",
            ["id", "material_article", "edge_04_article", "edge_08_article"],
            "INSERT OR IGNORE",
        ),
        (
            "fittings",
            "fittings",
            ["id", "city", "code", "article", "name", "price", "stock", "updated_at"],
            "INSERT OR IGNORE",
        ),
        (
            TELEGRAM_PROJECTS_TABLE,
            "projects",
            ["id", "project_id", "telegram_id", "params_json", "project_json", "cutting_json", "created_at"],
            "INSERT OR IGNORE",
        ),
        (
            "production_users",
            "production_users",
            ["telegram_id", "username", "role"],
            "INSERT OR REPLACE",
        ),
        (
            "orders",
            "orders",
            ["order_id", "client_name", "project_name", "created_at"],
            "INSERT OR IGNORE",
        ),
        (
            "parts",
            "parts",
            ["part_id", "order_id", "name", "width", "height", "thickness", "qty", "material", "created_at"],
            "INSERT OR IGNORE",
        ),
        (
            "production_states",
            "production_states",
            ["id", "part_id", "stage", "operator", "changed_at"],
            "INSERT OR IGNORE",
        ),
        (
            "machining_operations",
            "machining_operations",
            ["operation_id", "part_id", "operation_type", "tool_id", "x", "y", "z", "depth", "created_at"],
            "INSERT OR IGNORE",
        ),
        (
            "nesting_results",
            "nesting_results",
            ["id", "part_id", "sheet_id", "pos_x", "pos_y", "rotated", "created_at"],
            "INSERT OR IGNORE",
        ),
    ]

    for target_table, source_table, columns, insert_mode in mappings:

        if not _table_exists(cursor, "legacydb", source_table):
            continue

        columns_sql = ", ".join(columns)

        cursor.execute(
            f"""
            {insert_mode} INTO {target_table} ({columns_sql})
            SELECT {columns_sql}
            FROM legacydb.{source_table}
            """
        )

    connection.commit()
    cursor.execute("DETACH DATABASE legacydb")
    connection.close()
