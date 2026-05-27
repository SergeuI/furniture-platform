# =====================================================
# PRODUCTION ROLE ENGINE
# Ролі виробництва
# =====================================================
from services.production_auth_engine import (
    get_user_role
)

# =====================================================
# ROLE PERMISSIONS
# Дозволи ролей
# =====================================================

ROLE_PERMISSIONS = {

    "admin": [

        "queue",

        "cutting",

        "edgebanding",

        "drilling",

        "assembly",

        "packaging",

        "completed"
    ],

    "cut_operator": [

        "cutting"
    ],

    "edgebanding_operator": [

        "edgebanding"
    ],

    "drilling_operator": [

        "drilling"
    ],

    "assembly_operator": [

        "assembly"
    ],

    "packaging_operator": [

        "packaging"
    ]
}


# =====================================================
# USER ROLES
# Ролі користувачів
# =====================================================

# USER_ROLES = {

#     # Telegram user_id
#     # приклад:
#     # 123456789: "admin"
# }


# =====================================================
# GET USER ROLE
# Отримання ролі
# =====================================================

# def get_user_role(

#     user_id
# ):

#     return USER_ROLES.get(

#         user_id,

#         "guest"
#     )


# =====================================================
# CAN ACCESS STAGE
# Перевірка доступу
# =====================================================

def can_access_stage(

    user_id,

    stage
):

    role = get_user_role(
        user_id
    )

    permissions = ROLE_PERMISSIONS.get(

        role,

        []
    )

    return stage in permissions


# =====================================================
# REGISTER USER ROLE
# Реєстрація ролі
# =====================================================

# def register_user_role(

#     user_id,

#     role
# ):

#     USER_ROLES[
#         user_id
#     ] = role