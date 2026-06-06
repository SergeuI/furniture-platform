# =====================================================
# PRODUCTION DASHBOARD ENGINE
# Dashboard виробництва
# =====================================================

import sqlite3


# =====================================================
# GET STAGE COUNTS
# Кількість по етапах
# =====================================================

def get_stage_counts(

    db_path="furniture_platform.db"
):

    connection = sqlite3.connect(
        db_path
    )

    cursor = connection.cursor()

    cursor.execute("""

        SELECT

            current_stage,

            COUNT(*)

        FROM production_parts

        GROUP BY current_stage

    """)

    rows = cursor.fetchall()

    connection.close()

    result = {}

    for row in rows:

        result[
            row[0]
        ] = row[1]

    return result


# =====================================================
# GET TOTAL PARTS
# Загальна кількість деталей
# =====================================================

def get_total_parts(

    db_path="furniture_platform.db"
):

    connection = sqlite3.connect(
        db_path
    )

    cursor = connection.cursor()

    cursor.execute("""

        SELECT COUNT(*)

        FROM production_parts

    """)

    count = cursor.fetchone()[0]

    connection.close()

    return count


# =====================================================
# GET COMPLETED PARTS
# Завершені деталі
# =====================================================

def get_completed_parts(

    db_path="furniture_platform.db"
):

    connection = sqlite3.connect(
        db_path
    )

    cursor = connection.cursor()

    cursor.execute("""

        SELECT COUNT(*)

        FROM production_parts

        WHERE current_stage = 'completed'

    """)

    count = cursor.fetchone()[0]

    connection.close()

    return count


# =====================================================
# GET PRODUCTION STATS
# Статистика виробництва
# =====================================================

def get_production_stats(

    db_path="furniture_platform.db"
):

    total = get_total_parts(
        db_path
    )

    completed = get_completed_parts(
        db_path
    )

    stages = get_stage_counts(
        db_path
    )

    progress = 0

    if total > 0:

        progress = round(

            (
                completed
                / total
            ) * 100,

            2
        )

    return {

        "total_parts": total,

        "completed_parts": completed,

        "progress_percent": progress,

        "stages": stages
    }
