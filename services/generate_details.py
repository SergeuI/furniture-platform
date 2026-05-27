from services.generate_carcass import (
    generate_carcass
)

from services.generate_drawers import (
    generate_drawers
)

from services.generate_facades import (
    generate_facades
)


# =====================================================
# GENERATE ALL DETAILS
# =====================================================

def generate_all_details(data):

    details = []

    # =================================================
    # GENERATE MODULES
    # =================================================

    carcass = generate_carcass(data)

    drawers = generate_drawers(data)

    facades = generate_facades(data)

    # =================================================
    # DEBUG
    # =================================================

    print("\n========== CARCASS ==========")
    print(type(carcass))

    print("\n========== DRAWERS ==========")
    print(type(drawers))

    print("\n========== FACADES ==========")
    print(type(facades))

    # =================================================
    # MERGE DETAILS
    # =================================================

    details.extend(
        carcass["details"]
    )

    details.extend(
        drawers["details"]
    )

    details.extend(
        facades["details"]
    )

    # =================================================
    # FINAL DEBUG
    # =================================================

    print("\n========== FINAL DETAILS ==========")

    for i, item in enumerate(details):

        print(f"\nINDEX: {i}")

        print(type(item))

        print(item)

    return details