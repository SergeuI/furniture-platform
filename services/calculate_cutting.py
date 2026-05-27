from core.bom.materials import (

    calculate_material_area,

    calculate_edge_length
)


def calculate_cutting(details):

    total_area = 0

    total_cut = 0

    total_edge_04 = 0

    total_edge_08 = 0

    for item in details:

        width = item["width"]

        height = item["height"]

        qty = item.get("qty", 1)

        # =====================================
        # ПЛОЩА
        # =====================================

        area = calculate_material_area(
            width,
            height
        )

        total_area += area * qty

        # =====================================
        # РІЗ
        # =====================================

        cut = (
            (width + height) * 2
        ) / 1000

        total_cut += cut * qty

        # =====================================
        # КРАЙКА
        # =====================================

        edges = item.get("edges", {})

        for side, edge_type in edges.items():

            # -----------------------------
            # ДОВЖИНА СТОРОНИ
            # -----------------------------

            if side in [
                "top",
                "bottom"
            ]:

                edge_size = width

            elif side in [
                "left",
                "right"
            ]:

                edge_size = height

            elif side == "front":

                edge_size = width

            else:
                continue

            edge_length = (
                calculate_edge_length(
                    edge_size,
                    0
                ) / 2
            ) * qty

            # мм -> п.м.

            edge_length = (
                edge_length / 1000
            ) * qty

            # -----------------------------
            # КРАЙКА 0.4
            # -----------------------------

            if edge_type == "0.4":

                total_edge_04 += edge_length

            # -----------------------------
            # КРАЙКА 0.8
            # -----------------------------

            elif edge_type == "0.8":

                total_edge_08 += edge_length

    return {

        "area": round(total_area, 2),

        "cut": round(total_cut, 2),

        "edge_04": round(total_edge_04, 2),

        "edge_08": round(total_edge_08, 2)
    }