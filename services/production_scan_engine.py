# =====================================================
# PRODUCTION SCAN ENGINE
# Сканування виробництва
# =====================================================

from services.production_database_engine import (

    get_part,

    update_stage
)

from services.production_state_engine import (
    update_part_state
)

from services.production_role_engine import (
    can_access_stage
)
# =====================================================
# PARSE BARCODE
# Парсинг barcode
# =====================================================

def parse_barcode(

    barcode
):

    if not barcode.startswith(
        "PART-"
    ):

        return None

    return barcode.replace(
        "PART-",
        ""
    )


# =====================================================
# FIND PART BY BARCODE
# Пошук деталі
# =====================================================

def find_part_by_barcode(

    barcode,

    db_path="mebli_calculator.db"
):

    parsed = parse_barcode(
        barcode
    )

    if not parsed:

        return None

    # =============================================
    # ПОШУК ПО PART_ID PREFIX
    # =============================================

    import sqlite3

    connection = sqlite3.connect(
        db_path
    )

    cursor = connection.cursor()

    cursor.execute("""

        SELECT

            part_id,

            barcode,

            name,

            part_type,

            current_stage

        FROM production_parts

        WHERE barcode = ?

    """, (

        barcode,
    ))

    row = cursor.fetchone()

    connection.close()

    if not row:

        return None

    return {

        "part_id": row[0],

        "barcode": row[1],

        "name": row[2],

        "type": row[3],

        "stage": row[4]
    }


# =====================================================
# PROCESS SCAN
# Обробка сканування
# =====================================================

def process_scan(

    barcode,

    next_stage,

    user_id
):

    part = find_part_by_barcode(
        barcode
    )

    # =============================================
    # ROLE ACCESS
    # =============================================

    if not can_access_stage(

        user_id,

        next_stage
    ):

        return {

            "success": False,

            "error": "access_denied"
        }

    if not part:

        return {

            "success": False,

            "error": "part_not_found"
        }

    # =============================================
    # FSM / MES STATE UPDATE
    # =============================================

    virtual_part = {

        "tracking": {

            "stage": part[
                "stage"
            ]
        }
    }

    state_result = update_part_state(

        virtual_part,

        next_stage
    )

    if not state_result[
        "success"
    ]:

        return state_result

    # =============================================
    # DATABASE UPDATE
    # =============================================

    update_stage(

        part[
            "part_id"
        ],

        part[
            "stage"
        ],

        next_stage
    )

    return {

        "success": True,

        "part_id": part[
            "part_id"
        ],

        "old_stage": part[
            "stage"
        ],

        "new_stage": next_stage
    }