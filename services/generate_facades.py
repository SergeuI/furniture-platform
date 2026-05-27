# services/generate_facades.py

from services.facade_engine import (
    get_inset_facade_width,
    get_inset_facade_height
)

from services.cabinet_opening_engine import (
    get_section_opening_width,
    get_cabinet_opening_height
)
from services.gap_engine import (
    get_facade_gap
)
import uuid
# =====================================================
# GENERATE FACADES
# =====================================================

def generate_facades(data):

    params = data

    width = params.get("width")
    height = params.get("height")

    sections = params.get("sections", 1)

    drawers = params.get("drawers", [])

    details = []

    opening_width = (
        get_section_opening_width(
            width,
            sections
        )
    )

    opening_height = (
        get_cabinet_opening_height(
            height
        )
    )
  
    facade_width = int(

        get_inset_facade_width(

            opening_width,

            params.get(
                "slide_type",
                "movento"
            )
        )
    )

    for section_index, drawers_count in enumerate(drawers):

        facade_height = int(

            get_inset_facade_height(

                opening_height,

                drawers_count,

                params.get(
                    "slide_type",
                    "movento"
                )
            )
        )

        for i in range(drawers_count):

            details.append({

                "id": str(uuid.uuid4()),

                "type": "facade",

                "name": (
                    f"Фасад "
                    f"S{section_index+1}-{i+1}"
                ),

                "width": round(
                    facade_width
                ),

                "height": round(
                    facade_height
                ),

                "qty": 1,

                "edges": {

                    "top": "0.8",

                    "bottom": "0.8",

                    "left": "0.8",

                    "right": "0.8"
                }
            })

    return {
        "details": details
    }