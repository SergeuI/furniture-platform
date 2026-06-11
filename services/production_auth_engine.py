# =====================================================
# PRODUCTION AUTH ENGINE
# Авторизація виробництва
# =====================================================

import sqlite3

from database.repositories.user_repository import (
    get_user_by_telegram_id,
)
from services.telegram_identity_service import (
    ensure_telegram_identity,
)
from services.user_roles import (
    normalize_user_role,
    ROLE_GUEST,
)


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

    core_user = get_user_by_telegram_id(telegram_id)

    if not core_user:
        ensure_telegram_identity(
            telegram_id=telegram_id,
            email=f"tg_{telegram_id}@telegram.local",
            display_name=username,
            role=ROLE_GUEST,
        )

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

    if row:
        return row[0]

    core_user = get_user_by_telegram_id(telegram_id)

    if not core_user:

        return ROLE_GUEST

    return normalize_user_role(core_user.role)
