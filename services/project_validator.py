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
            "РњС–РЅС–РјР°Р»СЊРЅР° С€РёСЂРёРЅР°: 300 РјРј"
        )

    if width > 2600:

        errors.append(
            "РњР°РєСЃРёРјР°Р»СЊРЅР° С€РёСЂРёРЅР°: 2600 РјРј"
        )

    # =================================================
    # HEIGHT
    # =================================================

    if height < 300:

        errors.append(
            "РњС–РЅС–РјР°Р»СЊРЅР° РІРёСЃРѕС‚Р°: 300 РјРј"
        )

    if height > 1500:

        errors.append(
            "РњР°РєСЃРёРјР°Р»СЊРЅР° РІРёСЃРѕС‚Р°: 1500 РјРј"
        )

    # =================================================
    # DEPTH
    # =================================================

    if depth < 250:

        errors.append(
            "РњС–РЅС–РјР°Р»СЊРЅР° РіР»РёР±РёРЅР°: 250 РјРј"
        )

    if depth > 650:

        errors.append(
            "РњР°РєСЃРёРјР°Р»СЊРЅР° РіР»РёР±РёРЅР°: 650 РјРј"
        )

    # =================================================
    # SECTIONS
    # =================================================

    sections = project.sections.count

    if sections < 1:

        errors.append(
            "РњС–РЅС–РјСѓРј 1 СЃРµРєС†С–СЏ"
        )

    if sections > 6:

        errors.append(
            "РњР°РєСЃРёРјСѓРј 6 СЃРµРєС†С–Р№"
        )

    # =================================================
    # DRAWERS
    # =================================================

    total_drawers = sum(
        project.drawers.config
    )

    if total_drawers < 0:

        errors.append(
            "РќРµРєРѕСЂРµРєС‚РЅР° РєС–Р»СЊРєС–СЃС‚СЊ С€СѓС…Р»СЏРґ"
        )

    if total_drawers > 0:

        usable_height = height - 100

        avg_drawer_height = (
            usable_height / max(
                total_drawers,
                1
            )
        )

        if avg_drawer_height < 90:

            errors.append(
                "Р—Р°Р±Р°РіР°С‚Рѕ С€СѓС…Р»СЏРґ "
                "РґР»СЏ РІРєР°Р·Р°РЅРѕС— РІРёСЃРѕС‚Рё"
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

                "MOVENTO РїРѕС‚СЂРµР±СѓС” "
                "РјС–РЅС–РјСѓРј 450 РјРј РіР»РёР±РёРЅРё"
            )

    # =================================================
    # RESULT
    # =================================================

    return ValidationResult(

        success=len(errors) == 0,

        errors=errors
    )
