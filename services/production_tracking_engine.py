# =====================================================
# PRODUCTION TRACKING ENGINE
# Виробничий трекінг
# =====================================================
from services.production_database_engine import (
    register_part
)


import uuid


# =====================================================
# CREATE PART LABEL
# Створення label
# =====================================================

def create_part_label(

    part
):

    return {

        "part_id": str(
            uuid.uuid4()
        ),

        "name": part.get(
            "name",
            "Unknown"
        ),

        "type": part.get(
            "type",
            "part"
        ),

        "width": part.get(
            "width",
            0
        ),

        "height": part.get(
            "height",
            0
        )
    }


# =====================================================
# CREATE BARCODE
# Генерація barcode
# =====================================================

def create_barcode(

    label
):

    return (

        f"PART-"

        f"{label['part_id'][:8]}"
    )


# =====================================================
# CREATE QR DATA
# Дані для QR
# =====================================================

def create_qr_data(

    label
):

    return {

        "part_id": label[
            "part_id"
        ],

        "name": label[
            "name"
        ],

        "type": label[
            "type"
        ]
    }


# =====================================================
# APPLY TRACKING
# Додавання tracking
# =====================================================

def apply_tracking(

    parts
):

    tracked = []

    for part in parts:

        label = create_part_label(
            part
        )

        barcode = create_barcode(
            label
        )

        qr_data = create_qr_data(
            label
        )

        tracking_data = {

            "label": label,

            "barcode": barcode,

            "qr_data": qr_data,

            "stage": "queue"
        }

        register_part(

            tracking_data,

            geometry=part
        )

        tracked.append({

            **part,

            "tracking": tracking_data
        })

    return tracked