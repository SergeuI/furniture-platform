# =====================================================
# MATERIAL AREA
# =====================================================

def calculate_material_area(

    width: int,

    height: int

) -> float:

    area = (

        width * height
    ) / 1_000_000

    return round(area, 3)


# =====================================================
# EDGE LENGTH
# =====================================================

def calculate_edge_length(

    width: int,

    height: int

) -> float:

    edge = (

        width * 2
        + height * 2
    ) / 1000

    return round(edge, 3)


# =====================================================
# SHEET USAGE
# =====================================================

def calculate_sheet_usage(

    total_area: float,

    sheet_area: float = 5.796

) -> dict:

    sheets = total_area / sheet_area

    return {

        "sheet_area": sheet_area,

        "used_area": round(
            total_area,
            3
        ),

        "sheets": round(
            sheets,
            2
        )
    }