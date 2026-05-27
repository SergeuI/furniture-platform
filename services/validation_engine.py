# =====================================================
# VALIDATION ENGINE
# =====================================================


# =====================================================
# VALIDATE PROJECT
# =====================================================

# =====================================================
# VALIDATION ENGINE
# =====================================================


# =====================================================
# VALIDATE PROJECT
# =====================================================

def validate_project(params):

    errors = []

    width = params.get(
        "width",
        0
    )

    height = params.get(
        "height",
        0
    )

    depth = params.get(
        "depth",
        0
    )

    sections = params.get(
        "sections",
        1
    )

    drawers_config = params.get(
        "drawers_config",
        []
    )

    slide_type = str(
        params.get(
            "slide_type",
            ""
        )
    ).lower()

    bottom_type = str(
        params.get(
            "bottom_type",
            ""
        )
    ).lower()

    
    # =================================================
    # BASIC SIZE LIMITS
    # =================================================

    if width < 300:

        errors.append(
            "Мінімальна ширина: 300 мм"
        )

    if width > 2600:

        errors.append(
            "Максимальна ширина: 2600 мм"
        )

    if height < 300:

        errors.append(
            "Мінімальна висота: 300 мм"
        )

    if height > 1500:

        errors.append(
            "Максимальна висота: 1500 мм"
        )

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

    if sections < 1:

        errors.append(
            "Мінімум 1 секція"
        )

    if sections > 12:

        errors.append(
            "Максимум 12 секцій"
        )

    # =================================================
    # DRAWERS CONFIG
    # =================================================

    if not drawers_config:

        errors.append(
            "Не вибрано шухляди"
        )

    for count in drawers_config:

        if count < 1:

            errors.append(
                "Некоректна кількість шухляд"
            )

        if count > 10:

            errors.append(
                "Забагато шухляд в секції"
            )

    # =================================================
    # DRAWER HEIGHT VALIDATION
    # =================================================

    total_drawers = sum(
        drawers_config
    )

    usable_height = height - 100

    if total_drawers > 0:

        avg_drawer_height = (
            usable_height / total_drawers
        )

        if avg_drawer_height < 90:

            errors.append(
                "Забагато шухляд для "
                "вказаної висоти"
            )

    # =================================================
    # SLIDE TYPE
    # =================================================

    allowed_slide_types = [

        "movento",

        "tandem",

        "telescopic"
    ]

    if not any(
        x in slide_type
        for x in allowed_slide_types
    ):

        errors.append(
            "Некоректний тип напрямних"
        )

    # =================================================
    # MOVENTO VALIDATION
    # =================================================

    if "movento" in slide_type:

        if depth < 450:

            errors.append(
                "MOVENTO потребує "
                "мінімум 450 мм глибини"
            )

    # =================================================
    # TANDEM VALIDATION
    # =================================================

    if "tandem" in slide_type:

        if depth < 300:

            errors.append(
                "TANDEM потребує "
                "мінімум 300 мм глибини"
            )

    # =================================================
    # TELESCOPIC VALIDATION
    # =================================================

    if "telescopic" in slide_type:

        if depth < 250:

            errors.append(
                "Телескопічні напрямні "
                "потребують мінімум 250 мм"
            )

    # =================================================
    # BOTTOM VALIDATION
    # =================================================

    allowed_bottoms = [

        "hdf",
        "hdf_3",

        "dsp",
        "dsp_18"
    ]

    if bottom_type not in allowed_bottoms:

        errors.append(
            "Некоректний тип дна"
        )

    # =================================================
    # IMPOSSIBLE GEOMETRY
    # =================================================

    section_width = int(
        width / sections
    )

    if section_width < 250:

        errors.append(
            "Секція занадто вузька"
        )

    # =================================================
    # RESULT
    # =================================================

    return {

        "success": len(errors) == 0,

        "errors": errors
    }