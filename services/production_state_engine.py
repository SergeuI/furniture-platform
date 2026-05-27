# =====================================================
# PRODUCTION STATE ENGINE
# Стан виробництва
# =====================================================


# =====================================================
# VALID STATES
# Стан виробництва
# =====================================================

VALID_STATES = [

    "queue",

    "cutting",

    "edgebanding",

    "drilling",

    "assembly",

    "packaging",

    "completed"
]


# =====================================================
# VALID TRANSITIONS
# Дозволені переходи
# =====================================================

VALID_TRANSITIONS = {

    "queue": [

        "cutting"
    ],

    "cutting": [

        "edgebanding"
    ],

    "edgebanding": [

        "drilling"
    ],

    "drilling": [

        "assembly"
    ],

    "assembly": [

        "packaging"
    ],

    "packaging": [

        "completed"
    ]
}


# =====================================================
# VALIDATE STATE
# Перевірка стану
# =====================================================

def validate_state(

    state
):

    return state in VALID_STATES


# =====================================================
# CAN TRANSITION
# Перевірка переходу
# =====================================================

def can_transition(

    current_state,

    next_state
):

    allowed = VALID_TRANSITIONS.get(

        current_state,

        []
    )

    return next_state in allowed


# =====================================================
# UPDATE PART STATE
# Оновлення стану
# =====================================================

def update_part_state(

    part,

    next_state
):

    tracking = part.get(
        "tracking",
        {}
    )

    current_state = tracking.get(
        "stage",
        "queue"
    )

    if not validate_state(
        next_state
    ):

        return {

            "success": False,

            "error": "invalid_state"
        }

    if not can_transition(

        current_state,

        next_state
    ):

        return {

            "success": False,

            "error": "invalid_transition"
        }

    tracking["stage"] = next_state

    part["tracking"] = tracking

    return {

        "success": True,

        "part": part
    }


# =====================================================
# BULK UPDATE
# Масове оновлення
# =====================================================

def bulk_update_parts(

    parts,

    next_state
):

    updated = []

    errors = []

    for part in parts:

        result = update_part_state(

            part,

            next_state
        )

        if result["success"]:

            updated.append(
                result["part"]
            )

        else:

            errors.append({

                "part": part,

                "error": result[
                    "error"
                ]
            })

    return {

        "updated": updated,

        "errors": errors
    }