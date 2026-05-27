# services/calculator.py

def generate_commode_details(data):
    """
    Генерація деталей комода
    """

    width = int(data["width"])
    height = int(data["height"])
    depth = int(data["depth"])

    material_thickness = 18

    details = []

    # =====================================================
    # БОКОВИНИ
    # =====================================================

    details.append({
        "name": "Бок ліва",
        "width": depth,
        "height": height,
        "qty": 1,
        "edge": ["front"]
    })

    details.append({
        "name": "Бок права",
        "width": depth,
        "height": height,
        "qty": 1,
        "edge": ["front"]
    })

    # =====================================================
    # ДНО
    # =====================================================

    details.append({
        "name": "Дно",
        "width": width - (material_thickness * 2),
        "height": depth,
        "qty": 1,
        "edge": ["front"]
    })

    # =====================================================
    # КРИШКА
    # =====================================================

    details.append({
        "name": "Кришка",
        "width": width - (material_thickness * 2),
        "height": depth,
        "qty": 1,
        "edge": ["front"]
    })

    # =====================================================
    # ПЕРЕГОРОДКИ
    # =====================================================

    sections = int(data.get("sections", 1))

    if sections > 1:

        divider_count = sections - 1

        divider_width = (
            width
            - (material_thickness * 2)
            - (divider_count * material_thickness)
        ) / sections

        for i in range(divider_count):

            details.append({
                "name": f"Перегородка {i+1}",
                "width": depth,
                "height": height - (material_thickness * 2),
                "qty": 1,
                "edge": ["front"]
            })

    return details

