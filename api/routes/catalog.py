from fastapi import APIRouter

from schemas.catalog import (
    SpecificationCatalogResponseSchema
)

router = APIRouter()

PROJECT_TYPES = [
    "dresser",
    "wardrobe",
    "cabinet",
    "kitchen",
    "drawer_unit"
]

SLIDE_TYPES = [
    "tandem",
    "movento",
    "telescopic"
]

BOTTOM_TYPES = [
    "hdf",
    "hdf_3",
    "dsp",
    "dsp_18"
]

MATERIAL_THICKNESSES = [
    16,
    18,
    19
]

EDGE_BANDINGS = [
    "abs_0_5",
    "abs_1",
    "abs_2",
    "pvc_0_5",
    "pvc_1",
    "pvc_2"
]

HANDLE_POSITIONS = [
    "top",
    "center",
    "bottom",
    "left",
    "right",
    "integrated"
]


@router.get(
    "/specification",
    response_model=SpecificationCatalogResponseSchema
)
async def get_specification_catalog_route():
    return {
        "success": True,
        "project_types": PROJECT_TYPES,
        "slide_types": SLIDE_TYPES,
        "bottom_types": BOTTOM_TYPES,
        "material_thicknesses": MATERIAL_THICKNESSES,
        "edge_bandings": EDGE_BANDINGS,
        "handle_positions": HANDLE_POSITIONS
    }
