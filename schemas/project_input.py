from pydantic import BaseModel
from pydantic import Field

from typing import List
from typing import Optional


# =====================================================
# PROJECT METADATA
# =====================================================

class ProjectMetadataSchema(BaseModel):

    name: Optional[str] = None

    type: Optional[str] = None

    client: Optional[str] = None

    room: Optional[str] = None

    notes: Optional[str] = None


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

    edge_banding: Optional[str] = None

    thickness: Optional[int] = None


# =====================================================
# FITTINGS
# =====================================================

class FittingsSchema(BaseModel):

    slide_type: Optional[str] = None

    bottom_type: Optional[str] = None

    handle_type: Optional[str] = None

    handle_position: Optional[str] = None


# =====================================================
# PROJECT INPUT
# =====================================================

class ProjectInputSchema(BaseModel):

    metadata: ProjectMetadataSchema = Field(
        default_factory=ProjectMetadataSchema
    )

    dimensions: DimensionsSchema

    sections: SectionsSchema

    drawers: DrawersSchema

    materials: MaterialsSchema

    fittings: FittingsSchema


# =====================================================
# PROJECT PART EDGES
# =====================================================

class ProjectPartEdgesUpdateSchema(BaseModel):

    top: Optional[str] = None

    bottom: Optional[str] = None

    left: Optional[str] = None

    right: Optional[str] = None
