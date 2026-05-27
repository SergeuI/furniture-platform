import logging


# =====================================================
# MACHINING SEQUENCE ENGINE
# CNC послідовність обробки
# =====================================================


# =====================================================
# SORT BY TOOL
# Групування по інструменту
# =====================================================

def sort_by_tool(

    operations
):

    logging.debug(

        f"TOOL SORT OPERATIONS: {len(operations)}"
    )

    return sorted(

        operations,

        key=lambda op: (

            op.get(
                "operation_type",
                ""
            ),

            op.get(
                "tool",
                {}
            ).get(
                "tool_id",
                ""
            ),

            op.get(
                "position",
                {}
            ).get(
                "x",
                0
            ),

            op.get(
                "position",
                {}
            ).get(
                "y",
                0
            )
        )
    )


# =====================================================
# SORT BY POSITION
# Оптимізація переміщення
# =====================================================

def sort_by_position(

    operations
):

    return sorted(

        operations,

        key=lambda op: (

            op.get(
                "operation_type",
                ""
            ),

            op.get(
                "tool",
                {}
            ).get(
                "tool_id",
                ""
            ),

            op.get(
                "position",
                {}
            ).get(
                "x",
                0
            ),

            op.get(
                "position",
                {}
            ).get(
                "y",
                0
            )
        )
    )


# =====================================================
# BUILD MACHINING SEQUENCE
# Побудова CNC послідовності
# =====================================================

def build_machining_sequence(

    operations
):

    # =============================================
    # TOOL GROUPING
    # =============================================

    operations = sort_by_tool(
        operations
    )

    # =============================================
    # POSITION SORT
    # =============================================

    operations = sort_by_position(
        operations
    )

    sequence = []

    sequence_number = 1

    for operation in operations:

        sequence.append({

            **operation,

            "sequence": sequence_number
        })

        sequence_number += 1

    return sequence