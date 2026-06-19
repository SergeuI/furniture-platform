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

    facade_edge_banding: Optional[str] = None

    inside_edge_banding: Optional[str] = None

    facade_thickness: Optional[int] = None

    inside_thickness: Optional[int] = None

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


class ProjectScanUploadSchema(BaseModel):

    filename: str = Field(
        min_length=1,
        max_length=255
    )

    content_base64: str = Field(
        min_length=1
    )


class ProjectScanConfirmSchema(BaseModel):

    confirmed_project_id: Optional[str] = None


# =====================================================
# PROJECT PART EDGES
# =====================================================

class ProjectPartEdgesUpdateSchema(BaseModel):

    top: Optional[str] = None

    bottom: Optional[str] = None

    left: Optional[str] = None

    right: Optional[str] = None


class ProjectPartHoleUpdateSchema(BaseModel):

    number: int

    side: str = "front"

    origin: str = "left_bottom"

    x: float

    y: float

    z: float = 0

    diameter: float

    depth: float

    type: str = "manual"


class ProjectPartGrooveUpdateSchema(BaseModel):

    number: int

    side: str = "front"

    origin: str = "left_bottom"

    x: float

    y: float

    depth: float

    width: float

    length: float

    type: str = "manual"


class ProjectPartQuarterUpdateSchema(BaseModel):

    number: int

    side: str = "bottom"

    origin: str = "left_bottom"

    x: float = 0

    y: float = 0

    depth: float

    width: float

    length: float

    radius: float = 0

    type: str = "manual"


class ProjectPartMachiningUpdateSchema(BaseModel):

    holes: List[ProjectPartHoleUpdateSchema] = Field(
        default_factory=list
    )

    grooves: List[ProjectPartGrooveUpdateSchema] = Field(
        default_factory=list
    )

    quarters: List[ProjectPartQuarterUpdateSchema] = Field(
        default_factory=list
    )
