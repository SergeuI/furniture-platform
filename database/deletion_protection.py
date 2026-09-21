from __future__ import annotations

import json

from sqlalchemy.exc import OperationalError

AUTO_DELETION_ACTIONS = (
    "admin.entity_deleted",
    "admin.entity_deactivated",
    "catalog.material_deleted",
    "catalog.edge_deleted",
)


def canonical_edge_identity_key(edge_or_identity) -> str:
    values = {
        "manufacturer_id": getattr(edge_or_identity, "manufacturer_id", None),
        "manufacturer_article": getattr(edge_or_identity, "manufacturer_article", None),
        "material_type": getattr(edge_or_identity, "material_type", None),
        "technology_code": getattr(edge_or_identity, "technology_code", None),
        "width_mm": getattr(edge_or_identity, "width_mm", None),
        "thickness_mm": getattr(edge_or_identity, "thickness_mm", None),
    }
    if isinstance(edge_or_identity, dict):
        values = {key: edge_or_identity.get(key) for key in values}
    return json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def is_auto_recreate_suppressed(db, entity_type: str, entity_key: str) -> bool:
    normalized_type = str(entity_type or "").strip()
    normalized_key = str(entity_key or "").strip()
    if not normalized_type or not normalized_key:
        return False

    if hasattr(db, "query"):
        from database.models.audit_log import AuditLogModel

        try:
            return (
                db.query(AuditLogModel.id)
                .filter(AuditLogModel.action.in_(AUTO_DELETION_ACTIONS))
                .filter(AuditLogModel.entity_type == normalized_type)
                .filter(AuditLogModel.entity_id == normalized_key)
                .first()
                is not None
            )
        except OperationalError as exc:
            if "no such table" not in str(exc).lower():
                raise
            return False

    placeholders = ", ".join("?" for _ in AUTO_DELETION_ACTIONS)
    statement = """
        SELECT 1
        FROM audit_logs
        WHERE action IN ({placeholders})
          AND entity_type = ?
          AND entity_id = ?
        LIMIT 1
    """.format(placeholders=placeholders)
    parameters = (*AUTO_DELETION_ACTIONS, normalized_type, normalized_key)

    if hasattr(db, "exec_driver_sql"):
        audit_logs_exists = db.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'audit_logs'"
        ).first()
        if audit_logs_exists is None:
            return False
        return db.exec_driver_sql(statement, parameters).first() is not None

    audit_logs_exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'audit_logs'"
    ).fetchone()
    if audit_logs_exists is None:
        return False

    return db.execute(statement, parameters).fetchone() is not None


def is_auto_recreate_suppressed_for_entity(entity_type: str, entity_key: str) -> bool:
    from database.session import SessionLocal

    db = SessionLocal()
    try:
        return is_auto_recreate_suppressed(db, entity_type, entity_key)
    finally:
        db.close()
