from __future__ import annotations

ALLOWED_MOUNTING_NODE_FASTENING_TYPES = (
    "confirmat", "minifix", "rafix", "screw", "dowel", "other",
)


def validate_mounting_node_fastening_type(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in ALLOWED_MOUNTING_NODE_FASTENING_TYPES:
        raise ValueError("fastening_type must be one of: " + ", ".join(ALLOWED_MOUNTING_NODE_FASTENING_TYPES))
    return value
