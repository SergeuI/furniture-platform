# =====================================================
# MACHINING MODEL
# CNC обробка
# =====================================================

from dataclasses import (
    dataclass,
    field
)


# =====================================================
# TOOL MODEL
# Інструмент
# =====================================================

@dataclass
class ToolModel:

    tool_id: str

    name: str

    diameter: float

    depth: float

    feed: float

    rpm: int

    tool_type: str = "drill"

    metadata: dict = field(
        default_factory=dict
    )

    def to_dict(self):

        return {

            "tool_id": self.tool_id,

            "name": self.name,

            "diameter": self.diameter,

            "depth": self.depth,

            "feed": self.feed,

            "rpm": self.rpm,

            "tool_type": self.tool_type,

            "metadata": self.metadata
        }


# =====================================================
# MACHINE POSITION
# Координати CNC
# =====================================================

@dataclass
class MachinePosition:

    x: float

    y: float

    z: float

    rotation: float = 0

    def to_dict(self):

        return {

            "x": self.x,

            "y": self.y,

            "z": self.z,

            "rotation": self.rotation
        }


# =====================================================
# MACHINING OPERATION
# CNC операція
# =====================================================

@dataclass
class MachiningOperation:

    operation_type: str

    position: dict

    tool: dict

    depth: float

    direction: dict = field(
        default_factory=dict
    )

    metadata: dict = field(
        default_factory=dict
    )

    def to_dict(self):

        return {

            "operation_type": self.operation_type,

            "position": self.position,

            "tool": self.tool,

            "depth": self.depth,

            "direction": self.direction,

            "metadata": self.metadata
        }