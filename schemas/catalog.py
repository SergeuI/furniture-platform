from typing import List

from pydantic import BaseModel


class SpecificationCatalogResponseSchema(BaseModel):
    success: bool
    project_types: List[str]
    slide_types: List[str]
    bottom_types: List[str]
    material_thicknesses: List[int]
    edge_bandings: List[str]
    handle_positions: List[str]
