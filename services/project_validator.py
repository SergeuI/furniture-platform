from schemas.project_input import (
    ProjectInputSchema
)


# =====================================================
# VALIDATION RESULT
# =====================================================

class ValidationResult:

    def __init__(

        self,

        success: bool,

        errors: list[str]
    ):

        self.success = success

        self.errors = errors


# =====================================================
# VALIDATE PROJECT
# =====================================================

def validate_project_input(

    project: ProjectInputSchema

) -> ValidationResult:

    errors = []

    # =================================================
    # DIMENSIONS
    # =================================================

    width = project.dimensions.width

    height = project.dimensions.height

    depth = project.dimensions.depth

    # =================================================
    # WIDTH
    # =================================================

    if width < 300:

        errors.append(
            "Мінімальна ширина: 300 мм"
        )

    if width > 2600:

        errors.append(
            "Максимальна ширина: 2600 мм"
        )

    # =================================================
    # HEIGHT
    # =================================================

    if height < 300:

        errors.append(
            "Мінімальна висота: 300 мм"
        )

    if height > 1500:

        errors.append(
            "Максимальна висота: 1500 мм"
        )

    # =================================================
    # DEPTH
    # =================================================

    if depth < 250:

        errors.append(
            "Мінімальна глибина: 250 мм"
        )

    if depth > 650:

        errors.append(
            "Максимальна глибина: 650 мм"
        )

    # =================================================
    # SECTIONS
    # =================================================

    sections = project.sections.count

    if sections < 1:

        errors.append(
            "Мінімум 1 секція"
        )

    if sections > 6:

        errors.append(
            "Максимум 6 секцій"
        )

    # =================================================
    # DRAWERS
    # =================================================

    total_drawers = sum(
        project.drawers.config
    )

    if total_drawers < 1:

        errors.append(
            "Не вибрано шухляди"
        )

    usable_height = height - 100

    avg_drawer_height = (
        usable_height / max(
            total_drawers,
            1
        )
    )

    if avg_drawer_height < 90:

        errors.append(
            "Забагато шухляд "
            "для вказаної висоти"
        )

    # =================================================
    # FITTINGS
    # =================================================

    slide_type = (
        project.fittings.slide_type or ""
    ).lower()

    if "movento" in slide_type:

        if depth < 450:

            errors.append(

                "MOVENTO потребує "
                "мінімум 450 мм глибини"
            )

    # =================================================
    # RESULT
    # =================================================

    return ValidationResult(

        success=len(errors) == 0,

        errors=errors
    )