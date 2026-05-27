# =====================================================
# GEOMETRY MODEL
# Геометрія деталей
# =====================================================

from dataclasses import dataclass, field
import uuid

# =====================================================
# PART GEOMETRY
# Геометрія деталі
# =====================================================

@dataclass
class PartGeometry:

    # =============================================
    # BASIC
    # =============================================

    name: str

    width: float

    height: float

    thickness: float

    qty: int = 1

    id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    # =============================================
    # MATERIAL
    # =============================================

    material: str = "DSP"

    grain_direction: str = "vertical"

    # =============================================
    # ROTATION
    # =============================================

    allow_rotate: bool = True

    rotated: bool = False

    # =============================================
    # POSITION
    # =============================================

    x: float = 0

    y: float = 0

    z: float = 0

    # =============================================
    # EXTRA
    # =============================================

    metadata: dict = field(
        default_factory=dict
    )

    # =============================================
    # TO_DICT
    # =============================================

    def to_dict(self):

        return {
            "id": self.id,

            "name": self.name,

            "width": self.width,

            "height": self.height,

            "thickness": self.thickness,

            "qty": self.qty,

            "material": self.material,

            "grain_direction": self.grain_direction,

            "allow_rotate": self.allow_rotate,

            "rotated": self.rotated,

            "x": self.x,

            "y": self.y,

            "z": self.z,

            "metadata": self.metadata
        }