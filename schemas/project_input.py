from pydantic import BaseModel

from typing import List
from typing import Optional


# =====================================================
# DIMENSIONS
# =====================================================

class DimensionsSchema(BaseModel):

    width: int

    height: int

    depth: int


# =====================================================
# SECTIONS
# =====================================================

class SectionsSchema(BaseModel):

    count: int

    config: List[int] = []


# =====================================================
# DRAWERS
# =====================================================

class DrawersSchema(BaseModel):

    config: List[int] = []


# =====================================================
# MATERIALS
# =====================================================

class MaterialsSchema(BaseModel):

    facade: Optional[str] = None

    inside: Optional[str] = None


# =====================================================
# FITTINGS
# =====================================================

class FittingsSchema(BaseModel):

    slide_type: Optional[str] = None

    bottom_type: Optional[str] = None


# =====================================================
# PROJECT INPUT
# =====================================================

class ProjectInputSchema(BaseModel):

    dimensions: DimensionsSchema

    sections: SectionsSchema

    drawers: DrawersSchema

    materials: MaterialsSchema

    fittings: FittingsSchema