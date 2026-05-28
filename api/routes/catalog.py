from fastapi import APIRouter

from schemas.catalog import (
    SpecificationCatalogResponseSchema
)
from database.repositories.catalog_repository import (
    get_specification_catalog
)

router = APIRouter()


@router.get(
    "/specification",
    response_model=SpecificationCatalogResponseSchema
)
async def get_specification_catalog_route():
    catalog = get_specification_catalog()

    return {
        "success": True,
        **catalog
    }
