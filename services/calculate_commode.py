from services.generate_full_project import (
    generate_full_project
)
from services.calculate_cutting import (
    calculate_cutting
)
from services.calculate_edgeband import (
    calculate_edgeband
)
from services.production_dashboard_engine import (
    save_project_to_production
)

# =====================================================
# CALCULATE COMMODE
# =====================================================

def calculate_commode(data):

    # =================================================
    # GENERATE FULL PROJECT
    # =================================================

    project = generate_full_project(data)

    details = project.get(
        "details",
        []
    )

    connections = project.get(
        "connections",
        []
    )

    # =================================================
    # VALIDATION
    # =================================================

    if not details:

        raise ValueError(
            "Project has no details"
        )

    for i, part in enumerate(details):

        if not isinstance(part, dict):

            raise TypeError(
                f"Part #{i} is not dict: {type(part)}"
            )

        if "id" not in part:

            raise ValueError(
                f"Part must have id: {part}"
            )

        if "name" not in part:

            raise ValueError(
                f"Part must have name: {part}"
            )

        if "width" not in part:

            raise ValueError(
                f"Part must have width: {part}"
            )

        if "height" not in part:

            raise ValueError(
                f"Part must have height: {part}"
            )

    # =================================================
    # CUTTING
    # =================================================

    cutting = calculate_cutting(
        details
    )

    # =================================================
    # EDGEBAND
    # =================================================

    edgeband = calculate_edgeband(
        details
    )

    # =================================================
    # SAVE TO PRODUCTION   
    # =================================================

    production_result = (
        save_project_to_production(
            {
                "details": details,
                "connections": connections,
                "cutting": cutting,
                "edgeband": edgeband
            }
        )
    )

    # =================================================
    # RESULT  
    # =================================================

    return {

        "success": True,

        "details": details,

        "connections": connections,

        "cutting": cutting,

        "edgeband": edgeband,

        "production": production_result
    }  