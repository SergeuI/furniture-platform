# =====================================================
# FACADE DRILLING ENGINE
# Свердління фасадів
# =====================================================

# Імпорт логіки напрямку свердління
# Потрібно для CNC та CAM систем
from services.drilling_direction_engine import (

    drilling_front_to_back
)

from services.machining_operation_engine import (

    create_through_drilling_operation,

    create_blind_drilling_operation
)
# =====================================================
# HANDLE DRILLING
# Свердління під ручку
# =====================================================

def create_handle_drilling(

    facade_width,

    facade_height,

    handle_distance=160
):

    # =================================================
    # ЦЕНТР ФАСАДУ
    # =================================================

    # Центр по ширині
    center_x = (
        facade_width / 2
    )

    # Центр по висоті
    center_y = (
        facade_height / 2
    )

    # =================================================
    # ЗАХИСТ ВІД ВИХОДУ ОТВОРІВ ЗА МЕЖІ ФАСАДУ
    # =================================================

    # Мінімальний відступ 20 мм від країв
    max_distance = max(

        0,

        facade_width - 40
    )

    # Якщо ручка ширша за фасад —
    # автоматично зменшуємо міжосьову відстань
    handle_distance = min(

        handle_distance,

        max_distance
    )

    if handle_distance < 32:

        handle_distance = 32

    # =================================================
    # НАПРЯМОК СВЕРДЛІННЯ
    # =================================================

    # Свердління:
    # FRONT → BACK
    direction = (
        drilling_front_to_back()
    )


    # =================================================
    # ПОВЕРНЕННЯ ОТВОРІВ
    # =================================================

    return [

        {

            # Тип отвору
            "type": "handle_hole",

            # Діаметр свердління
            "diameter": 5,

            # Лівий отвір по X
            "x": round(
                center_x
                - handle_distance / 2,
                2
            ),

            # Позиція по Y
            "y": round(
                center_y,
                2
            ),

            # Позиція по Z
            "z": 0,

            # Напрямок свердління
            "direction": direction,
            

            "operation": create_through_drilling_operation(
                5
            )
        },

        {

            # Тип отвору
            "type": "handle_hole",

            # Діаметр свердління
            "diameter": 5,

            # Правий отвір по X
            "x": round(
                center_x
                + handle_distance / 2,
                2
            ),

            # Позиція по Y
            "y": round(
                center_y,
                2
            ),

            # Позиція по Z
            "z": 0,

            # Напрямок свердління
            "direction": direction,


            "operation": create_through_drilling_operation(
                5
            )
        }
    ]


# =====================================================
# TIP-ON DRILLING
# Свердління під TIP-ON
# =====================================================

def create_tipon_drilling():

    # =================================================
    # НАПРЯМОК СВЕРДЛІННЯ
    # =================================================

    direction = (
        drilling_front_to_back()
    )



    # =================================================
    # ПОВЕРНЕННЯ ОТВОРУ
    # =================================================

    return [

        {

            # Тип свердління
            "type": "tipon_hole",

            # Діаметр отвору
            "diameter": 10,

            # Позиція по X
            "x": 37,

            # Позиція по Y
            "y": 20,

            # Позиція по Z
            "z": 0,

            # Напрямок свердління
            "direction": direction,

            "operation": create_blind_drilling_operation(
                10,
                13
            )
        }
    ]


# =====================================================
# FRONT FIXING
# Кріплення фасаду до шухляди
# =====================================================

def create_front_fixing_drilling(

    facade_width,

    facade_height
):

    # =================================================
    # НАПРЯМОК СВЕРДЛІННЯ
    # =================================================

    direction = (
        drilling_front_to_back()
    )



    # =================================================
    # ПОВЕРНЕННЯ КРІПЛЕНЬ
    # =================================================

    return [

        {

            # Тип отвору
            "type": "front_fixing",

            # Діаметр свердління
            "diameter": 8,

            # Ліве кріплення
            "x": 37,

            # Відступ зверху
            "y": 37,

            # Позиція по Z
            "z": 0,

            # Напрямок свердління
            "direction": direction,

            "operation": create_blind_drilling_operation(
                8,
                12
            )
        },

        {

            # Тип отвору
            "type": "front_fixing",

            # Діаметр свердління
            "diameter": 8,

            # Праве кріплення
            "x": facade_width - 37,

            # Відступ зверху
            "y": 37,

            # Позиція по Z
            "z": 0,

            # Напрямок свердління
            "direction": direction,

            "operation": create_blind_drilling_operation(
                8,
                12
            )
        }
    ]