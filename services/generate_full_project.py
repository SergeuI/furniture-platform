from services.generate_carcass import generate_carcass
from services.generate_drawers import generate_drawers
from services.generate_facades import generate_facades
import logging

def generate_full_project(data):

    details = []

    # корпус
    carcass = generate_carcass(data)

    # шухляди
    drawers = generate_drawers(data)

    # фасади
    facades = generate_facades(data)

    # збираємо все
    details.extend(
        carcass["details"]
    )



    details.extend(drawers["details"])


    details.extend(facades["details"])


    logging.info(

        f"PROJECT GENERATED: {len(details)} parts"
    )


    return {

        "details": details,

        "connections": carcass["connections"]
    }
