from services.generate_drawers import (
    generate_drawers
)
from services.production_database_engine import (
    init_production_db
)
data = {

    "width": 800,

    "depth": 500,

    "height": 720,

    "sections": 1,

    "drawers": [3],

    "slide_type": "movento",

    "bottom_type": "HDF",

    "facade_type": "inset",

    "handle_type": "handle"
}

try:
    init_production_db()
    result = generate_drawers(
        data
    )

    print("\n=== SUCCESS ===\n")

    print(
        result.keys()
    )

    print(
        "\nDETAILS COUNT:"
    )

    print(
        len(
            result["details"]
        )
    )

    print(
        "\nFIRST DETAIL:\n"
    )

    print(
        result["details"][0]
    )

except Exception as error:

    print("\n=== ERROR ===\n")

    print(type(error))

    import traceback

    traceback.print_exc()


import json

with open(
    "result.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(

        result,

        file,

        ensure_ascii=False,

        indent=4
    )

print("\nJSON SAVED")
