# =====================================================
# PRODUCTION AUTH ENGINE
# Авторизація виробництва
# =====================================================

import sqlite3


# =====================================================
# INIT AUTH TABLE
# Таблиця ролей
# =====================================================

def init_auth_tables(

    db_path="furniture_platform.db"
):

    connection = sqlite3.connect(
        db_path
    )

    cursor = connection.cursor()

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS production_users (

            telegram_id INTEGER PRIMARY KEY,

            username TEXT,

            role TEXT
        )

    """)

    connection.commit()

    connection.close()


# =====================================================
# REGISTER USER
# Реєстрація оператора
# =====================================================

def register_user(

    telegram_id,

    username,

    role,

    db_path="furniture_platform.db"
):

    connection = sqlite3.connect(
        db_path
    )

    cursor = connection.cursor()

    cursor.execute("""

        INSERT OR REPLACE INTO
        production_users (

            telegram_id,

            username,

            role
        )

        VALUES (?, ?, ?)

    """, (

        telegram_id,

        username,

        role
    ))

    connection.commit()

    connection.close()


# =====================================================
# GET USER ROLE
# Отримання ролі
# =====================================================

def get_user_role(

    telegram_id,

    db_path="furniture_platform.db"
):

    connection = sqlite3.connect(
        db_path
    )

    cursor = connection.cursor()

    cursor.execute("""

        SELECT role

        FROM production_users

        WHERE telegram_id = ?

    """, (

        telegram_id,
    ))

    row = cursor.fetchone()

    connection.close()

    if not row:

        return "guest"

    return row[0]
