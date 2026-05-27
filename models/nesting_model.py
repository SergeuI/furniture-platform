# =====================================================
# NESTING MODEL
# Розкладка листа
# =====================================================

from dataclasses import (
    dataclass,
    field
)


# =====================================================
# SHEET MODEL
# Лист матеріалу
# =====================================================

@dataclass
class SheetModel:

    sheet_id: int

    width: float

    height: float

    material: str = "DSP"

    thickness: float = 18

    metadata: dict = field(
        default_factory=dict
    )

    def to_dict(self):

        return {

            "sheet_id": self.sheet_id,

            "width": self.width,

            "height": self.height,

            "material": self.material,

            "thickness": self.thickness,

            "metadata": self.metadata
        }


# =====================================================
# FREE RECTANGLE
# Вільна область
# =====================================================

@dataclass
class FreeRectangle:

    x: float

    y: float

    width: float

    height: float

    def to_dict(self):

        return {

            "x": self.x,

            "y": self.y,

            "width": self.width,

            "height": self.height
        }


# =====================================================
# SHEET POSITION
# Позиція деталі
# =====================================================

@dataclass
class SheetPosition:

    sheet_id: int

    x: float

    y: float

    rotated: bool = False

    def to_dict(self):

        return {

            "sheet_id": self.sheet_id,

            "x": self.x,

            "y": self.y,

            "rotated": self.rotated
        }


# =====================================================
# CUT LINE
# Лінія різу
# =====================================================

@dataclass
class CutLine:

    start_x: float

    start_y: float

    end_x: float

    end_y: float

    direction: str

    cut_type: str = "panel"

    metadata: dict = field(
        default_factory=dict
    )

    def to_dict(self):

        return {

            "start": {

                "x": self.start_x,

                "y": self.start_y
            },

            "end": {

                "x": self.end_x,

                "y": self.end_y
            },

            "direction": self.direction,

            "cut_type": self.cut_type,

            "metadata": self.metadata
        }