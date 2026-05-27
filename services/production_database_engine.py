# =====================================================
# PRODUCTION DATABASE ENGINE
# MES / ERP база
# =====================================================

import sqlite3
from datetime import datetime


# =====================================================
# CONNECT
# Підключення
# =====================================================

def connect_db(

    db_path="mebli_calculator.db"
):

    return sqlite3.connect(
        db_path
    )


# =====================================================
# INIT DATABASE
# Ініціалізація ERP/MES
# =====================================================

def init_production_db(

    db_path="mebli_calculator.db"
):

    connection = connect_db(
        db_path
    )

    cursor = connection.cursor()

    # =================================================
    # ORDERS
    # =================================================

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS orders (

            order_id INTEGER PRIMARY KEY AUTOINCREMENT,

            client_name TEXT,

            project_name TEXT,

            created_at TEXT
        )

    """)

    # =================================================
    # PARTS
    # =================================================

    cursor.execute("""

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

            FOREIGN KEY(order_id)
            REFERENCES orders(order_id)
        )

    """)

    # =================================================
    # PRODUCTION STATES
    # =================================================

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS production_states (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            part_id TEXT,

            stage TEXT,

            operator TEXT,

            changed_at TEXT,

            FOREIGN KEY(part_id)
            REFERENCES parts(part_id)
        )

    """)

    # =================================================
    # MACHINING OPERATIONS
    # =================================================

    cursor.execute("""

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

            FOREIGN KEY(part_id)
            REFERENCES parts(part_id)
        )

    """)

    # =================================================
    # NESTING RESULTS
    # =================================================

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS nesting_results (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            part_id TEXT,

            sheet_id INTEGER,

            pos_x REAL,

            pos_y REAL,

            rotated INTEGER,

            created_at TEXT,

            FOREIGN KEY(part_id)
            REFERENCES parts(part_id)
        )

    """)

    connection.commit()

    connection.close()


# =====================================================
# CREATE ORDER
# Створення замовлення
# =====================================================

def create_order(

    client_name,

    project_name,

    db_path="mebli_calculator.db"
):

    connection = connect_db(
        db_path
    )

    cursor = connection.cursor()

    cursor.execute("""

        INSERT INTO orders (

            client_name,

            project_name,

            created_at
        )

        VALUES (?, ?, ?)

    """, (

        client_name,

        project_name,

        datetime.now().isoformat()
    ))

    connection.commit()

    order_id = cursor.lastrowid

    connection.close()

    return order_id


# =====================================================
# REGISTER PART
# Реєстрація деталі
# =====================================================

def register_part(

    tracking,

    geometry=None,

    order_id=None,

    db_path="mebli_calculator.db"
):

    connection = connect_db(
        db_path
    )

    cursor = connection.cursor()

    label = tracking["label"]

    geometry = geometry or {}

    cursor.execute("""

        INSERT OR REPLACE INTO parts (

            part_id,

            order_id,

            name,

            width,

            height,

            thickness,

            qty,

            material,

            created_at
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

    """, (

        label["part_id"],

        order_id,

        label["name"],

        geometry.get(
            "width",
            0
        ),

        geometry.get(
            "height",
            0
        ),

        geometry.get(
            "thickness",
            0
        ),

        geometry.get(
            "qty",
            1
        ),

        geometry.get(
            "material",
            "DSP"
        ),

        datetime.now().isoformat()
    ))

    cursor.execute("""

        INSERT INTO production_states (

            part_id,

            stage,

            operator,

            changed_at
        )

        VALUES (?, ?, ?, ?)

    """, (

        label["part_id"],

        tracking["stage"],

        "",

        datetime.now().isoformat()
    ))

    connection.commit()

    connection.close()


# =====================================================
# UPDATE STAGE
# Оновлення етапу
# =====================================================

def update_stage(

    part_id,

    new_stage,

    operator="",

    db_path="mebli_calculator.db"
):

    connection = connect_db(
        db_path
    )

    cursor = connection.cursor()

    cursor.execute("""

        INSERT INTO production_states (

            part_id,

            stage,

            operator,

            changed_at
        )

        VALUES (?, ?, ?, ?)

    """, (

        part_id,

        new_stage,

        operator,

        datetime.now().isoformat()
    ))

    connection.commit()

    connection.close()


# =====================================================
# GET PART
# Отримання деталі
# =====================================================

def get_part(

    part_id,

    db_path="mebli_calculator.db"
):

    connection = connect_db(
        db_path
    )

    cursor = connection.cursor()

    cursor.execute("""

        SELECT

            part_id,

            name,

            width,

            height,

            thickness,

            qty,

            material

        FROM parts

        WHERE part_id = ?

    """, (

        part_id,
    ))

    row = cursor.fetchone()

    connection.close()

    if not row:

        return None

    return {

        "part_id": row[0],

        "name": row[1],

        "width": row[2],

        "height": row[3],

        "thickness": row[4],

        "qty": row[5],

        "material": row[6]
    }