import asyncio
import copy
import logging
import time

from services.generate_full_project import (
    generate_full_project
)

from services.calculate_cutting import (
    calculate_cutting
)


# =====================================================
# GENERATE PROJECT PACKAGE
# =====================================================

async def generate_project_package(
    params
):

    safe_params = copy.deepcopy(
        params
    )

    started = time.time()

    logging.info(
        f"START GENERATION"
    )

    project = await asyncio.to_thread(

        generate_full_project,

        safe_params
    )

    cutting = await asyncio.to_thread(

        calculate_cutting,

        project["details"]
    )

    logging.info(
        "CUTTING CALCULATED"
    )

    elapsed = round(

        time.time() - started,

        2
    )

    logging.info(

        f"PROJECT GENERATED IN {elapsed}s"
    )

    return {

        "project": project,

        "cutting": cutting,

        "elapsed": elapsed
    }