from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from database.models.hole_library import HoleLibraryServiceMappingModel, HoleLibraryTypeModel
from database.models.service_catalog_item import ServiceCatalogItemModel
from database.models.service_drilling_rule import ServiceDrillingRuleModel
from database.session import SessionLocal
from database.deletion_protection import is_auto_recreate_suppressed


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _generated_hole_code(payload: dict[str, Any]) -> str:
    operation = _normalize_text(payload.get("operation_type")).upper() or "HOLE"
    surface = _normalize_text(payload.get("surface_type")).upper() or "SURFACE"
    diameter = payload.get("diameter_mm")
    diameter_token = "NA"
    if diameter not in (None, ""):
        try:
            diameter_token = f"D{float(diameter):g}".replace(".", "_")
        except (TypeError, ValueError):
            diameter_token = "D_CUSTOM"
    return f"CUSTOM_{operation}_{surface}_{diameter_token}"


def _build_seed_entries() -> list[dict[str, Any]]:
    def base_entry(
        *,
        code: str,
        name: str,
        operation_type: str,
        surface_type: str,
        diameter_mm: float | None,
        depth_mode: str,
        mapping_external_code: str,
        mapping_article: str,
        notes: str,
        fixed_depth_mm: float | None = None,
        min_depth_mm: float | None = None,
        max_depth_mm: float | None = None,
        material_depth_offset_mm: float | None = None,
        is_countersink: bool = False,
    ) -> dict[str, Any]:
        seed = {
            "code": code,
            "name": name,
            "operation_type": operation_type,
            "surface_type": surface_type,
            "diameter_mm": diameter_mm,
            "depth_mode": depth_mode,
            "fixed_depth_mm": fixed_depth_mm,
            "min_depth_mm": min_depth_mm,
            "max_depth_mm": max_depth_mm,
            "material_depth_offset_mm": material_depth_offset_mm,
            "is_countersink": is_countersink,
            "notes": notes,
            "mapping": {
                "supplier_code": "VIYAR",
                "service_external_code": mapping_external_code,
                "service_article": mapping_article,
            },
        }
        return seed

    seeds: list[dict[str, Any]] = []
    for diameter in (5, 6, 8, 10, 12, 15, 18, 20, 35):
        seeds.append(
            base_entry(
                code=f"PLANE_BLIND_D{diameter}",
                name=f"Глухий отвір Ø{diameter}",
                operation_type="blind",
                surface_type="plane",
                diameter_mm=float(diameter),
                depth_mode="material_relative",
                material_depth_offset_mm=3.0,
                mapping_external_code="viyar-service-drilling-main-00011",
                mapping_article="00011",
                notes="Standard blind plane drilling for sheet materials.",
            )
        )

    for diameter in (4, 5, 7, 8, 10):
        seeds.append(
            base_entry(
                code=f"PLANE_THROUGH_D{diameter}",
                name=f"Наскрізний отвір Ø{diameter}",
                operation_type="through",
                surface_type="plane",
                diameter_mm=float(diameter),
                depth_mode="through",
                mapping_external_code="viyar-service-drilling-main-00011",
                mapping_article="00011",
                notes="Standard through plane drilling.",
            )
        )

    for diameter in (4.5, 5, 6, 8, 10, 11, 12, 13, 14):
        seeds.append(
            base_entry(
                code="EDGE_D4_5" if diameter == 4.5 else f"EDGE_D{int(diameter)}",
                name=f"Торцевий отвір Ø{diameter:g}",
                operation_type="edge",
                surface_type="edge",
                diameter_mm=float(diameter),
                depth_mode="range",
                min_depth_mm=1.0,
                max_depth_mm=34.0,
                mapping_external_code="viyar-service-drilling-main-00011",
                mapping_article="00011",
                notes="Standard edge drilling.",
            )
        )

    for diameter in (10, 12, 14):
        seeds.append(
            base_entry(
                code=f"EDGE_DEEP_D{diameter}",
                name=f"Глибокий торцевий Ø{diameter}",
                operation_type="deep_edge",
                surface_type="edge",
                diameter_mm=float(diameter),
                depth_mode="range",
                min_depth_mm=34.1,
                max_depth_mm=70.0,
                mapping_external_code="viyar-service-drilling-main-98175",
                mapping_article="98175",
                notes="Deep edge drilling.",
            )
        )

    seeds.append(
        base_entry(
            code="CONFIRMAT_D7_CS",
            name="Конфірмат Ø7 з зенкуванням",
            operation_type="countersink",
            surface_type="plane",
            diameter_mm=7.0,
            depth_mode="through",
            mapping_external_code="viyar-service-drilling-main-00011",
            mapping_article="00011",
            notes="Special countersunk confirmat drilling.",
            is_countersink=True,
        )
    )
    seeds.append(
        base_entry(
            code="HINGE_CUP_D35",
            name="Чашка завіси Ø35",
            operation_type="hinge_cup",
            surface_type="plane",
            diameter_mm=35.0,
            depth_mode="fixed",
            fixed_depth_mm=12.0,
            mapping_external_code="viyar-service-drilling-main-51203",
            mapping_article="51203",
            notes="Dedicated hinge cup drilling type.",
        )
    )
    return seeds


HOLE_LIBRARY_SEED = _build_seed_entries()


def _serialize_service_item(item) -> dict[str, Any] | None:
    if not item:
        return None
    return {
        "id": item.id,
        "source": item.source,
        "external_code": item.external_code,
        "article": item.article,
        "name": item.name,
        "is_active": bool(item.is_active),
    }


def _serialize_service_rule(rule) -> dict[str, Any] | None:
    if not rule:
        return None
    return {
        "id": rule.id,
        "rule_name": rule.rule_name,
        "operation_type": rule.operation_type,
        "hole_type": rule.hole_type,
        "allowed_diameters": list(rule.allowed_diameters or []),
        "allowed_depths": list(rule.allowed_depths or []),
        "is_active": bool(rule.is_active),
    }


def _serialize_mapping(mapping) -> dict[str, Any]:
    return {
        "id": mapping.id,
        "hole_type_id": mapping.hole_type_id,
        "supplier_code": mapping.supplier_code,
        "service_external_code": mapping.service_external_code,
        "service_article": mapping.service_article,
        "service_catalog_item_id": mapping.service_catalog_item_id,
        "service_drilling_rule_id": mapping.service_drilling_rule_id,
        "mapping_status": mapping.mapping_status,
        "notes": mapping.notes,
        "is_active": bool(mapping.is_active),
        "created_at": mapping.created_at,
        "updated_at": mapping.updated_at,
        "service_catalog_item": _serialize_service_item(getattr(mapping, "service_catalog_item", None)),
        "service_drilling_rule": _serialize_service_rule(getattr(mapping, "service_drilling_rule", None)),
    }


def _serialize_hole_type(hole_type) -> dict[str, Any]:
    mappings = sorted(
        list(getattr(hole_type, "service_mappings", []) or []),
        key=lambda mapping: (str(getattr(mapping, "supplier_code", "") or ""), int(getattr(mapping, "id", 0) or 0)),
    )
    primary_mapping = next((mapping for mapping in mappings if bool(getattr(mapping, "is_active", True))), None)
    return {
        "id": hole_type.id,
        "code": hole_type.code,
        "name": hole_type.name,
        "owner_user_id": getattr(hole_type, "owner_user_id", None),
        "is_system": bool(getattr(hole_type, "is_system", True)),
        "operation_type": hole_type.operation_type,
        "surface_type": hole_type.surface_type,
        "diameter_mm": hole_type.diameter_mm,
        "depth_mode": hole_type.depth_mode,
        "fixed_depth_mm": hole_type.fixed_depth_mm,
        "min_depth_mm": hole_type.min_depth_mm,
        "max_depth_mm": hole_type.max_depth_mm,
        "material_depth_offset_mm": hole_type.material_depth_offset_mm,
        "is_countersink": bool(hole_type.is_countersink),
        "notes": hole_type.notes,
        "is_active": bool(hole_type.is_active),
        "created_at": hole_type.created_at,
        "updated_at": hole_type.updated_at,
        "primary_mapping": _serialize_mapping(primary_mapping) if primary_mapping else None,
        "mappings": [_serialize_mapping(mapping) for mapping in mappings],
    }


class HoleLibraryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _service_item_query(self):
        return (
            self.session.query(ServiceCatalogItemModel)
            .filter(ServiceCatalogItemModel.source == "viyar")
            .filter(ServiceCatalogItemModel.item_type == "service")
            .filter(ServiceCatalogItemModel.is_active.is_(True))
        )

    def _resolve_service_item(self, *, service_external_code: str | None = None, service_article: str | None = None):
        query = self._service_item_query()
        normalized_external_code = _normalize_text(service_external_code)
        normalized_article = _normalize_text(service_article)
        if normalized_external_code:
            query = query.filter(ServiceCatalogItemModel.external_code == normalized_external_code)
        elif normalized_article:
            query = query.filter(ServiceCatalogItemModel.article == normalized_article)
        else:
            return None
        return query.one_or_none()

    def _resolve_service_rule(self, service_catalog_item_id: str | None):
        if not service_catalog_item_id:
            return None
        return (
            self.session.query(ServiceDrillingRuleModel)
            .filter(ServiceDrillingRuleModel.service_catalog_item_id == service_catalog_item_id)
            .filter(ServiceDrillingRuleModel.is_active.is_(True))
            .order_by(ServiceDrillingRuleModel.id.asc())
            .one_or_none()
        )

    def list_hole_types(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        query = self.session.query(HoleLibraryTypeModel)
        if not include_inactive:
            query = query.filter(HoleLibraryTypeModel.is_active.is_(True))
        hole_types = query.order_by(HoleLibraryTypeModel.code.asc(), HoleLibraryTypeModel.id.asc()).all()
        return [_serialize_hole_type(hole_type) for hole_type in hole_types]

    def get_hole_type(self, hole_type_id: int) -> dict[str, Any] | None:
        hole_type = self.session.get(HoleLibraryTypeModel, int(hole_type_id))
        return _serialize_hole_type(hole_type) if hole_type else None

    def get_hole_type_model(self, hole_type_id: int) -> HoleLibraryTypeModel | None:
        return self.session.get(HoleLibraryTypeModel, int(hole_type_id))

    def get_hole_type_by_code(self, code: str) -> HoleLibraryTypeModel | None:
        normalized_code = _normalize_text(code)
        if not normalized_code:
            return None
        return (
            self.session.query(HoleLibraryTypeModel)
            .filter(HoleLibraryTypeModel.code == normalized_code)
            .one_or_none()
        )

    def upsert_hole_type(self, payload: dict[str, Any]) -> tuple[HoleLibraryTypeModel, bool]:
        code = _normalize_text(payload.get("code"))
        if not code:
            code = _generated_hole_code(payload)
            suffix = 1
            base_code = code
            while self.get_hole_type_by_code(code) is not None:
                suffix += 1
                code = f"{base_code}_{suffix}"

        hole_type = self.get_hole_type_by_code(code)
        created = False
        if hole_type is None:
            hole_type = HoleLibraryTypeModel(code=code)
            self.session.add(hole_type)
            created = True

        if "owner_user_id" in payload:
            owner_user_id = _normalize_text(payload.get("owner_user_id"))
            hole_type.owner_user_id = owner_user_id or None
            hole_type.is_system = not bool(owner_user_id)
        elif created and "is_system" not in payload:
            hole_type.is_system = True

        for field in ("name", "operation_type", "surface_type", "depth_mode", "notes"):
            if field in payload and payload.get(field) not in (None, ""):
                setattr(hole_type, field, _normalize_text(payload.get(field)))

        if "owner_user_id" in payload:
            owner_user_id = _normalize_text(payload.get("owner_user_id"))
            hole_type.owner_user_id = owner_user_id or None
            if owner_user_id:
                hole_type.is_system = False
        if "is_system" in payload:
            hole_type.is_system = bool(payload.get("is_system"))
            if hole_type.is_system:
                hole_type.owner_user_id = None

        for field in ("diameter_mm", "fixed_depth_mm", "min_depth_mm", "max_depth_mm", "material_depth_offset_mm"):
            if field in payload and payload.get(field) not in (None, ""):
                setattr(hole_type, field, float(payload.get(field)))

        if "is_countersink" in payload:
            hole_type.is_countersink = bool(payload.get("is_countersink"))
        if "is_active" in payload:
            hole_type.is_active = bool(payload.get("is_active"))

        self.session.flush()
        self.session.refresh(hole_type)
        return hole_type, created

    def update_hole_type(self, hole_type_id: int, payload: dict[str, Any]) -> HoleLibraryTypeModel | None:
        hole_type = self.get_hole_type_model(hole_type_id)
        if hole_type is None:
            return None

        for field in ("code", "name", "operation_type", "surface_type", "depth_mode", "notes"):
            if field in payload and payload.get(field) not in (None, ""):
                setattr(hole_type, field, _normalize_text(payload.get(field)))

        for field in ("diameter_mm", "fixed_depth_mm", "min_depth_mm", "max_depth_mm", "material_depth_offset_mm"):
            if field in payload:
                value = payload.get(field)
                setattr(hole_type, field, None if value in (None, "") else float(value))

        if "is_countersink" in payload:
            hole_type.is_countersink = bool(payload.get("is_countersink"))
        if "is_active" in payload:
            hole_type.is_active = bool(payload.get("is_active"))

        self.session.flush()
        self.session.refresh(hole_type)
        return hole_type

    def _find_mapping(self, *, hole_type_id: int, supplier_code: str, service_external_code: str) -> HoleLibraryServiceMappingModel | None:
        return (
            self.session.query(HoleLibraryServiceMappingModel)
            .filter(HoleLibraryServiceMappingModel.hole_type_id == int(hole_type_id))
            .filter(HoleLibraryServiceMappingModel.supplier_code == _normalize_text(supplier_code))
            .filter(HoleLibraryServiceMappingModel.service_external_code == _normalize_text(service_external_code))
            .one_or_none()
        )

    def upsert_service_mapping(self, hole_type_id: int, payload: dict[str, Any]) -> tuple[HoleLibraryServiceMappingModel, bool]:
        supplier_code = _normalize_text(payload.get("supplier_code"))
        service_external_code = _normalize_text(payload.get("service_external_code"))
        if not supplier_code:
            raise ValueError("supplier_code is required")
        if not service_external_code:
            raise ValueError("service_external_code is required")

        mapping = self._find_mapping(
            hole_type_id=hole_type_id,
            supplier_code=supplier_code,
            service_external_code=service_external_code,
        )
        created = False
        if mapping is None:
            mapping = HoleLibraryServiceMappingModel(
                hole_type_id=int(hole_type_id),
                supplier_code=supplier_code,
                service_external_code=service_external_code,
            )
            self.session.add(mapping)
            created = True

        if "service_article" in payload:
            mapping.service_article = _normalize_text(payload.get("service_article")) or None
        if "notes" in payload:
            mapping.notes = _normalize_text(payload.get("notes")) or None
        if "is_active" in payload:
            mapping.is_active = bool(payload.get("is_active"))

        service_item = self._resolve_service_item(
            service_external_code=mapping.service_external_code,
            service_article=mapping.service_article,
        )
        mapping.service_catalog_item_id = service_item.id if service_item else None
        service_rule = self._resolve_service_rule(mapping.service_catalog_item_id)
        mapping.service_drilling_rule_id = service_rule.id if service_rule else None
        mapping.mapping_status = "resolved" if service_item else "missing_service"
        if service_item and not service_rule:
            mapping.mapping_status = "service_only"

        self.session.flush()
        self.session.refresh(mapping)
        return mapping, created

    def update_service_mapping(self, mapping_id: int, payload: dict[str, Any]) -> HoleLibraryServiceMappingModel | None:
        mapping = self.session.get(HoleLibraryServiceMappingModel, int(mapping_id))
        if mapping is None:
            return None

        if "supplier_code" in payload and payload.get("supplier_code") not in (None, ""):
            mapping.supplier_code = _normalize_text(payload.get("supplier_code"))
        if "service_external_code" in payload and payload.get("service_external_code") not in (None, ""):
            mapping.service_external_code = _normalize_text(payload.get("service_external_code"))
        if "service_article" in payload:
            mapping.service_article = _normalize_text(payload.get("service_article")) or None
        if "notes" in payload:
            mapping.notes = _normalize_text(payload.get("notes")) or None
        if "is_active" in payload:
            mapping.is_active = bool(payload.get("is_active"))

        service_item = self._resolve_service_item(
            service_external_code=mapping.service_external_code,
            service_article=mapping.service_article,
        )
        mapping.service_catalog_item_id = service_item.id if service_item else None
        service_rule = self._resolve_service_rule(mapping.service_catalog_item_id)
        mapping.service_drilling_rule_id = service_rule.id if service_rule else None
        mapping.mapping_status = "resolved" if service_item else "missing_service"
        if service_item and not service_rule:
            mapping.mapping_status = "service_only"

        self.session.flush()
        self.session.refresh(mapping)
        return mapping

    def delete_hole_type(self, hole_type_id: int) -> HoleLibraryTypeModel | None:
        hole_type = self.get_hole_type_model(hole_type_id)
        if hole_type is None:
            return None
        hole_type.is_active = False
        self.session.flush()
        self.session.refresh(hole_type)
        return hole_type


def _upsert_seed_hole(repository: HoleLibraryRepository, seed: dict[str, Any]) -> None:
    code = _normalize_text(seed.get("code"))
    if is_auto_recreate_suppressed(repository.session, "hole_library_type", code):
        return

    hole_type, _ = repository.upsert_hole_type(seed)
    mapping = seed.get("mapping")
    if mapping:
        mapping_key = ":".join(
            (
                code,
                _normalize_text(mapping.get("supplier_code")),
                _normalize_text(mapping.get("service_external_code")),
            )
        )
        if is_auto_recreate_suppressed(repository.session, "hole_library_mapping", mapping_key):
            return
        repository.upsert_service_mapping(hole_type.id, mapping)


def seed_default_hole_library() -> None:
    db = SessionLocal()
    try:
        repository = HoleLibraryRepository(db)
        for seed in HOLE_LIBRARY_SEED:
            _upsert_seed_hole(repository, seed)
        db.commit()
    finally:
        db.close()
