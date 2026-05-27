from collections import defaultdict

from services.generate_carcass import (
    generate_carcass
)

from services.generate_drawers import (
    generate_drawers
)


from services.calculate_cutting import (
    calculate_cutting
)
from services.generate_bom import (
    generate_bom
)

from services.legs_logic import (
    calculate_legs
)

def generate_project_data(data):

    # =========================================
    # ВСІ ДЕТАЛІ
    # =========================================

    details = []

    all_connections = []

    # =========================================
    # КАРКАС
    # =========================================

    carcass = generate_carcass(data)


    details.extend(

        carcass["details"]
    )

    all_connections.extend(

        carcass["connections"]
    )

    # =========================================
    # ШУХЛЯДИ
    # =========================================

    drawers = generate_drawers(data)

 

    # =========================================
    # ВСІ ДЕТАЛІ
    # =========================================

    details.extend(drawers["details"])



    legs_qty = calculate_legs(

        data["width"]
    )


    # =========================================
    # РОЗРАХУНОК РІЗУ
    # =========================================

    cutting = calculate_cutting(details)

    # =========================================
    # ГРУПУВАННЯ ПО ТИПУ
    # =========================================

    grouped = defaultdict(list)

    for item in details:

        item_type = item.get(
            "type",
            "other"
        )

        grouped[item_type].append(item)

    # =========================================
    # РЕЗУЛЬТАТ
    # =========================================
    bom = generate_bom(details)
    return {
        "connections": all_connections,

        "details": details,

        "grouped": dict(grouped),

        "cutting": cutting,

        "bom": bom,
        "legs_qty": legs_qty
    }