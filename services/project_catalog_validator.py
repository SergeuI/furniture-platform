from schemas.project_input import (
    ProjectInputSchema
)

from database.repositories.catalog_repository import (
    get_specification_catalog
)


def _validate_optional_catalog_value(

    errors: list[str],

    value,

    allowed_values: list,

    message: str
):

    if value is None or value == "":

        return

    if str(value) not in [
        str(allowed_value)
        for allowed_value in allowed_values
    ]:

        errors.append(
            message
        )


# =====================================================
# VALIDATE PROJECT CATALOG VALUES
# =====================================================

def validate_project_catalog_values(

    project: ProjectInputSchema
) -> list[str]:

    errors = []

    catalog = get_specification_catalog()

    _validate_optional_catalog_value(

        errors=errors,

        value=project.metadata.type,

        allowed_values=catalog["project_types"],

        message="Invalid project type"
    )

    _validate_optional_catalog_value(

        errors=errors,

        value=project.materials.edge_banding,

        allowed_values=catalog["edge_bandings"],

        message="Invalid edge banding"
    )

    _validate_optional_catalog_value(

        errors=errors,

        value=project.materials.thickness,

        allowed_values=catalog["material_thicknesses"],

        message="Invalid material thickness"
    )

    _validate_optional_catalog_value(

        errors=errors,

        value=project.fittings.slide_type,

        allowed_values=catalog["slide_types"],

        message="Invalid slide type"
    )

    _validate_optional_catalog_value(

        errors=errors,

        value=project.fittings.bottom_type,

        allowed_values=catalog["bottom_types"],

        message="Invalid bottom type"
    )

    _validate_optional_catalog_value(

        errors=errors,

        value=project.fittings.handle_position,

        allowed_values=catalog["handle_positions"],

        message="Invalid handle position"
    )

    return errors
