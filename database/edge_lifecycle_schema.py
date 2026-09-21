"""Additive schema support for canonical edge orphan cleanup."""

from __future__ import annotations


def ensure_edge_lifecycle_schema(connection) -> None:
    execute = getattr(connection, "exec_driver_sql", connection.execute)
    has_column = any(
        row[1] == "cleanup_policy"
        for row in execute("PRAGMA table_info(canonical_edges)").fetchall()
    )
    if not has_column:
        execute(
            "ALTER TABLE canonical_edges ADD COLUMN cleanup_policy "
            "TEXT NOT NULL DEFAULT 'protected'"
        )
    execute(
        "UPDATE canonical_edges SET cleanup_policy = 'protected' "
        "WHERE cleanup_policy IS NULL OR trim(cleanup_policy) = ''"
    )
