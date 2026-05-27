from aiogram import Router, F
import aiosqlite
from services.db_service import (

    cache_image,

    save_calculation,

    seed_materials
)
import os
from dotenv import load_dotenv
from handlers.materials import (
    router as materials_router,
     show_material_types
)
from handlers.fittings import (
    router as fittings_router
)
from handlers.dimensions import (
    router as dimensions_router
)
from handlers.sections import (
    router as sections_router,
    show_sections
)
from handlers.drawers import (
    router as drawers_router,
    show_drawers
)
from handlers.drawer_bottoms import (
    router as drawer_bottoms_router
)
from handlers.profile import (
    router as profile_router
)
from handlers.gpt import (
    router as gpt_router
)
from handlers.production import (
    router as production_router
)
from handlers.categories import (
    router as categories_router
)

load_dotenv()



router = Router()


router.include_router(
    categories_router
)
router.include_router(
    materials_router
)
router.include_router(
    fittings_router
)
router.include_router(
    dimensions_router
)    
router.include_router(
    sections_router
)
router.include_router(
    drawers_router
)
router.include_router(
    drawer_bottoms_router
)
router.include_router(
    profile_router
)
router.include_router(
    gpt_router
)
router.include_router(
    production_router
)
