from services.blum_rules import (
    MOVENTO_RULES,
    TANDEM_RULES
)


def get_slide_rules(slide_type: str):

    systems = {

        "movento": MOVENTO_RULES,

        "tandem": TANDEM_RULES
    }

    return systems.get(
        slide_type,
        TANDEM_RULES
    )