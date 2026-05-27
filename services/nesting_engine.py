# =====================================================
# NESTING ENGINE
# Розкладка листа
# =====================================================

from services.nesting_optimizer_engine import (
    optimize_nesting
)
from services.nesting_algorithm_engine import (
    build_grouped_nesting
)
from services.sheet_cutting_engine import (
    build_cutting_map
)
from services.cutting_optimization_engine import (
    optimize_cutting_map
)
from models.nesting_model import (
    SheetModel
)
# =====================================================
# DEFAULT SHEET
# Стандартний лист
# =====================================================

DEFAULT_SHEET = SheetModel(

    sheet_id=1,

    width=2800,

    height=2070
).to_dict()
# =====================================================
# PLACE PART
# Розміщення деталі
# =====================================================

def place_part(

    part,

    x,

    y
):

    return {

        **part,

        "sheet_position": {

            "x": x,

            "y": y
        }
    }


# =====================================================
# SIMPLE NESTING
# Проста розкладка
# =====================================================

def build_simple_nesting(

    parts,

    sheet=None
):

    if sheet is None:

        sheet = DEFAULT_SHEET

    parts = optimize_nesting(

        parts,

        sheet["width"]
    )

    nesting = build_grouped_nesting(

        parts,

        sheet
    )

    cutting_maps = []

    for nesting_group in nesting:

        cutting_map = build_cutting_map(
            nesting_group
        )

        cutting_map = optimize_cutting_map(
            cutting_map
        )

        cutting_maps.append(
            cutting_map
        )

    return {

        "nesting": nesting,

        "cutting_maps": cutting_maps
    }
