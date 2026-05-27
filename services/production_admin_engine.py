# =====================================================
# PRODUCTION ADMIN ENGINE
# Адміністрування виробництва
# =====================================================

from services.production_auth_engine import (
    register_user,

    get_user_role
)


# =====================================================
# VALID ROLES
# Дозволені ролі
# =====================================================

VALID_ROLES = [

    "admin",

    "cut_operator",

    "edgebanding_operator",

    "drilling_operator",

    "assembly_operator",

    "packaging_operator"
]


# =====================================================
# IS ADMIN
# Перевірка адміністратора
# =====================================================

def is_admin(

    telegram_id
):

    role = get_user_role(
        telegram_id
    )

    return role == "admin"


# =====================================================
# VALIDATE ROLE
# Перевірка ролі
# =====================================================

def validate_role(

    role
):

    return role in VALID_ROLES


# =====================================================
# CREATE OPERATOR
# Створення оператора
# =====================================================

def create_operator(

    admin_id,

    telegram_id,

    username,

    role
):

    # =============================================
    # ADMIN CHECK
    # =============================================

    if not is_admin(
        admin_id
    ):

        return {

            "success": False,

            "error": "access_denied"
        }

    # =============================================
    # ROLE VALIDATION
    # =============================================

    if not validate_role(
        role
    ):

        return {

            "success": False,

            "error": "invalid_role"
        }

    # =============================================
    # CREATE USER
    # =============================================

    register_user(

        telegram_id,

        username,

        role
    )

    return {

        "success": True,

        "telegram_id": telegram_id,

        "username": username,

        "role": role
    }