# =====================================================
# FACADE MODEL
# Модель фасаду
# =====================================================

from dataclasses import (
    dataclass,
    field
)

import uuid


# =====================================================
# FACADE DRILLING
# Свердління фасаду
# =====================================================

@dataclass
class FacadeDrilling:

    drilling_type: str

    x: float

    y: float

    diameter: float

    depth: float

    metadata: dict = field(
        default_factory=dict
    )

    def to_dict(self):

        return {

            "drilling_type": self.drilling_type,

            "x": self.x,

            "y": self.y,

            "diameter": self.diameter,

            "depth": self.depth,

            "metadata": self.metadata
        }


# =====================================================
# FACADE POSITION
# Позиція фасаду
# =====================================================

@dataclass
class FacadePosition:

    x: float = 0

    y: float = 0

    z: float = 0

    rotation: float = 0

    def to_dict(self):

        return {

            "x": self.x,

            "y": self.y,

            "z": self.z,

            "rotation": self.rotation
        }


# =====================================================
# FACADE MODEL
# Основний DTO фасаду
# =====================================================

@dataclass
class FacadeModel:

    name: str

    width: float

    height: float

    thickness: float

    facade_type: str

    system: str

    qty: int = 1

    id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    drilling: list = field(
        default_factory=list
    )

    position: dict = field(
        default_factory=dict
    )

    metadata: dict = field(
        default_factory=dict
    )

    def to_dict(self):

        return {

            "id": self.id,

            "type": "facade",

            "name": self.name,

            "width": self.width,

            "height": self.height,

            "thickness": self.thickness,

            "facade_type": self.facade_type,

            "system": self.system,

            "qty": self.qty,

            "drilling": self.drilling,

            "position": self.position,

            "metadata": self.metadata
        }