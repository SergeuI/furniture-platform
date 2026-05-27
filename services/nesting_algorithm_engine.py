# =====================================================
# NESTING ALGORITHM ENGINE
# Алгоритм розкладки
# =====================================================
from models.nesting_model import (
    FreeRectangle
)

# =====================================================
# CREATE FREE RECTANGLE
# Вільна область
# =====================================================

def create_free_rectangle(

    x,

    y,

    width,

    height
):

    rectangle = FreeRectangle(

        x=x,

        y=y,

        width=width,

        height=height
    )

    return rectangle.to_dict()


# =====================================================
# PART FITS
# Перевірка входження деталі
# =====================================================

def part_fits(

    part,

    rect
):

    return (

        part["width"]

        <= rect["width"]

        and

        part["height"]

        <= rect["height"]
    )


# =====================================================
# SPLIT RECTANGLE
# Поділ області
# =====================================================

def split_rectangle(

    rect,

    part
):

    right_rect = create_free_rectangle(

        rect["x"] + part["width"],

        rect["y"],

        rect["width"] - part["width"],

        part["height"]
    )

    bottom_rect = create_free_rectangle(

        rect["x"],

        rect["y"] + part["height"],

        rect["width"],

        rect["height"] - part["height"]
    )

    rectangles = []

    if (

        right_rect["width"] > 0

        and

        right_rect["height"] > 0
    ):

        rectangles.append(
            right_rect
        )

    if (

        bottom_rect["width"] > 0

        and

        bottom_rect["height"] > 0
    ):

        rectangles.append(
            bottom_rect
        )

    return rectangles


# =====================================================
# PLACE PART IN RECTANGLE
# Розміщення деталі
# =====================================================

def place_part_in_rectangle(

    part,

    rect
):

    placed = {

        **part,

        "sheet_position": {

            "x": rect["x"],

            "y": rect["y"]
        }
    }

    free_rectangles = split_rectangle(

        rect,

        part
    )

    return {

        "part": placed,

        "free_rectangles": free_rectangles
    }


# =====================================================
# BUILD NESTING
# Побудова nesting
# =====================================================

def build_advanced_nesting(

    parts,

    sheet
):

    new_sheet_rectangles = [

        create_free_rectangle(

            0,

            0,

            sheet["width"],

            sheet["height"]
        )
    ]

    placed_parts = []

    free_rectangles = []

    # =====================================
    # CURRENT SHEET COUNTER
    # =====================================

    current_sheet = sheet.get(
        "start_sheet_id",
        1
    )

    for part in parts:

        placed = False

        for rect in list(new_sheet_rectangles):

            if part_fits(

                part,

                rect
            ):

                result = place_part_in_rectangle(

                    part,

                    rect
                )

                result["part"]["sheet_id"] = current_sheet

                placed_parts.append(
                    result["part"]
                )

                new_sheet_rectangles.remove(
                    rect
                )

                new_sheet_rectangles.extend(

                    result[
                        "free_rectangles"
                    ]
                )

                free_rectangles = list(
                    new_sheet_rectangles
                )

                placed = True

                break

        if not placed:

            # =====================================
            # CREATE NEW SHEET
            # =====================================

            current_sheet += 1

            new_sheet_rectangles = [

                create_free_rectangle(

                    0,

                    0,

                    sheet["width"],

                    sheet["height"]
                )
            ]

            placed = False

            for rect in list(new_sheet_rectangles):

                if part_fits(part, rect):

                    part["sheet_id"] = current_sheet

                    part["sheet_position"] = {

                        "x": rect["x"],

                        "y": rect["y"]
                    }

                    placed_parts.append(
                        part
                    )

                    new_rectangles = split_rectangle(
                        rect,
                        part
                    )

                    new_sheet_rectangles.remove(rect)

                    new_sheet_rectangles.extend(
                        new_rectangles
                    )

                    free_rectangles = list(
                        new_sheet_rectangles
                    )

                    placed = True

                    break

            if not placed:

                part["unplaced"] = True

    # =============================================
    # UTILIZATION
    # =============================================

    used_area = 0

    for part in placed_parts:

        if not part.get(
            "unplaced"
        ):

            used_area += (

                part["width"]

                * part["height"]
            )

    total_sheet_count = current_sheet

    sheet_area = (

        sheet["width"]

        * sheet["height"]

        * total_sheet_count
    )

    utilization = round(

        (
            used_area
            / sheet_area
        ) * 100,

        2
    )

    return {

        "sheet": sheet,

        "parts": placed_parts,

        "utilization": utilization,

        "free_rectangles": free_rectangles
    }




def build_grouped_nesting(

    parts,

    sheet
):

    groups = {}

    for part in parts:

        geometry = part.get(
            "geometry",
            {}
        )

        material = geometry.get(
            "material",
            "unknown"
        )

        thickness = geometry.get(
            "thickness",
            0
        )

        key = (
            material,
            thickness
        )

        if key not in groups:

            groups[key] = []

        groups[key].append(
            part
        )

    result = []

    sheet_counter = 1

    for key, group_parts in groups.items():

        sheet_copy = dict(sheet)

        sheet_copy["start_sheet_id"] = (
            sheet_counter
        )

        nested = build_advanced_nesting(

            group_parts,

            sheet_copy
        )

        result.append(
            nested
        )

        max_sheet = max(

            part.get(
                "sheet_id",
                1
            )

            for part in nested["parts"]
        )

        sheet_counter = max_sheet + 1

    return result