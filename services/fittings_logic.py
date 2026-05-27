# from services.fittings_config import FITTINGS
from services.mt_kits_parser import KITS

def get_slide_length(depth: int) -> int:
    if 290 <= depth < 340:
        return 250
    elif 340 <= depth < 390:
        return 300
    elif 390 <= depth < 440:
        return 350
    elif 440 <= depth < 490:
        return 400
    elif 490 <= depth < 540:
        return 450
    elif 540 <= depth < 590:
        return 500
    elif 590 <= depth < 640:
        return 550
    else:
        return 600
    
# Порядок відображення каруселі напрямних
def build_fittings(depth: int, has_tip_on: bool):

    length = get_slide_length(depth)

    if has_tip_on:

        order = [

            {
                "type": "viyar",
                "category": "slides_tipon",
                "length": length,
                "code": f"telescopic_{length}_tipon"
            },

            {
                "type": "mt_kit",
                "code": f"tandem_{length}_tipon"
            },

            {
                "type": "mt_kit",
                "code": f"movento_{length}_tipon"
            },
        ]

    else:

        order = [

            {
                "type": "viyar",
                "category": "slides_basic",
                "length": length,
                "code": f"telescopic_{length}"
            },

            {
                "type": "viyar",
                "category": "slides_softclose",
                "length": length,
                "code": f"telescopic_softclose_{length}"
            },

            {
                "type": "mt_kit",
                "code": f"tandem_{length}_softclose"
            },

            {
                "type": "mt_kit",
                "code": f"movento_{length}"
            },
        ]

    return order

# функцію вибору
async def choose_best_fitting(fittings, city, get_materials_func, get_kit_func):
    evaluated = []

    for item in fittings:
        try:
            if item["type"] == "viyar":
                materials = await get_materials_func(
                    item["category"],
                    item["length"],
                    city
                )

                if not materials:
                    continue

                mat = materials[0]

                evaluated.append({
                    "type": "viyar",
                    "price": mat["price"],
                    "data": mat,
                    "priority": get_priority(item)
                })

            elif item["type"] == "mt_kit":
                try:
                    kit = await get_kit_func(item["code"], city)
                    if not kit:
                        continue
                except Exception:
                    continue

                if not kit or not kit.get("price"):
                    continue

                evaluated.append({
                    "type": "mt_kit",
                    "price": kit["price"],
                    "data": kit,
                    "priority": get_priority(item)
                })

        except Exception as e:

            import logging

            logging.exception(
                f"FITTING ERROR: {e}"
            )

            continue

    if not evaluated:
        return None

    # 🔥 СОРТУВАННЯ:
    # 1. по пріоритету
    # 2. по ціні
    evaluated.sort(key=lambda x: (x["priority"], x["price"]))

    return evaluated[0]

# функція пріоритету
def get_priority(item):
    if item["type"] == "viyar":
        cat = item["category"]

        if cat == "slides_basic":
            return 1
        if cat == "slides_softclose":
            return 2
        if cat == "slides_tipon":
            return 1

    if item["type"] == "mt_kit":
        code = item["code"]

        if "tandem" in code:
            return 3
        if "movento" in code:
            return 4

    return 10