from __future__ import annotations

import re
from typing import Any, Mapping, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from database.models.fitting import (
    FittingHolePointModel,
    FittingHoleTemplateModel,
)
from database.models.mounting_node import MountingNodeModel
from database.repositories.mounting_node_repository import MountingNodeRepository
from database.session import SessionLocal
from database.models.service_drilling_rule import ServiceDrillingRuleModel


class MountingNodePermissionError(PermissionError):
    pass


class MountingNodeService:
    _ALLOWED_MOUNTING_VARIANT_KEYS = {
        "surface_mount",
        "angled_two_planes",
        "face_to_edge",
        "edge_to_edge",
        "drawer_slides",
    }

    def __init__(
        self,
        session: Optional[Session] = None,
        repository: Optional[MountingNodeRepository] = None,
    ) -> None:
        if repository is not None and session is None:
            session = getattr(repository, "session", None)

        self.session = session or SessionLocal()
        self._owns_session = session is None and repository is None
        self.repository = repository or MountingNodeRepository(self.session)

    def close(self) -> None:
        if self._owns_session and self.session is not None:
            self.session.close()

    def __enter__(self) -> "MountingNodeService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def _merge_payload(
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = dict(data or {})
        payload.update(kwargs)
        return payload

    @staticmethod
    def _require_int(value: Any, field_name: str) -> int:
        if value in (None, ""):
            raise ValueError(f"{field_name} is required")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be an integer") from exc

    @staticmethod
    def _require_text(value: Any, field_name: str) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            raise ValueError(f"{field_name} is required")
        return text

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _text_or_default(value: Any, default: str) -> str:
        text = "" if value is None else str(value).strip()
        return text or default

    @staticmethod
    def _require_positive_float(value: Any, field_name: str) -> float:
        if value in (None, ""):
            raise ValueError(f"{field_name} is required")
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be a number") from exc
        if numeric_value <= 0:
            raise ValueError(f"{field_name} must be greater than 0")
        return numeric_value

    @staticmethod
    def _optional_non_negative_float(value: Any, field_name: str) -> float | None:
        if value in (None, ""):
            return None
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be a number") from exc
        if numeric_value < 0:
            raise ValueError(f"{field_name} cannot be negative")
        return numeric_value

    @classmethod
    def _normalize_mounting_variant_key(cls, value: Any) -> str:
        key = "" if value is None else str(value).strip()
        if key in cls._ALLOWED_MOUNTING_VARIANT_KEYS:
            return key
        return "surface_mount"

    @staticmethod
    def _normalize_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)

    @staticmethod
    def _slugify(text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug or "node"

    def _generate_code(self, name: str) -> str:
        slug = self._slugify(name)[:48]
        return f"mounting-node-{slug}-{uuid4().hex[:8]}"

    def _ensure_fitting_exists(self, fitting_id: int) -> None:
        fitting = self.repository.get_fitting_by_id(fitting_id)
        if fitting is None:
            raise ValueError(f"Fitting with id={fitting_id} does not exist")

    def _ensure_template_exists(self, template_id: int) -> FittingHoleTemplateModel:
        template = self.repository.get_template_by_id(template_id)
        if template is None:
            raise ValueError(f"Template with id={template_id} does not exist")
        return template

    def _ensure_service_drilling_rule_exists(self, rule_id: int) -> ServiceDrillingRuleModel:
        rule = self.session.get(ServiceDrillingRuleModel, rule_id)
        if rule is None:
            raise ValueError(f"Service drilling rule with id={rule_id} does not exist")
        if not bool(getattr(rule, "is_active", True)):
            raise ValueError(f"Service drilling rule with id={rule_id} is not active")
        return rule

    def _ensure_node_exists(self, node_id: int) -> MountingNodeModel:
        node = self.repository.get_node_by_id(node_id)
        if node is None:
            raise ValueError(f"Mounting node with id={node_id} does not exist")
        return node

    @staticmethod
    def _is_admin_role(viewer_role: Any) -> bool:
        return str(viewer_role or "").strip().lower() == "admin"

    @staticmethod
    def _normalize_viewer_user_id(viewer_user_id: Any) -> str:
        return str(viewer_user_id or "").strip()

    def _resolve_ownership_snapshot(
        self,
        node: MountingNodeModel,
        *,
        viewer_user_id: Any = None,
        viewer_role: Any = None,
    ) -> dict[str, Any]:
        owner_user_id = self._optional_text(getattr(node, "owner_user_id", None))
        normalized_viewer_user_id = self._normalize_viewer_user_id(viewer_user_id)
        is_admin = self._is_admin_role(viewer_role)
        is_system = owner_user_id is None
        is_owner = bool(owner_user_id and normalized_viewer_user_id and owner_user_id == normalized_viewer_user_id)
        can_edit = bool(is_admin or is_owner)
        can_delete = bool(is_admin or is_owner)

        if is_system:
            ownership_type = "system"
        elif is_owner:
            ownership_type = "mine"
        elif is_admin:
            ownership_type = "user"
        else:
            ownership_type = "user"

        return {
            "owner_user_id": owner_user_id,
            "ownership_type": ownership_type,
            "is_system": is_system,
            "is_owner": is_owner,
            "can_edit": can_edit,
            "can_delete": can_delete,
        }

    def _assert_mutation_access(
        self,
        node: MountingNodeModel,
        *,
        viewer_user_id: Any = None,
        viewer_role: Any = None,
    ) -> dict[str, Any] | None:
        access_snapshot = self._resolve_ownership_snapshot(
            node,
            viewer_user_id=viewer_user_id,
            viewer_role=viewer_role,
        )

        normalized_viewer_user_id = self._normalize_viewer_user_id(viewer_user_id)
        if not normalized_viewer_user_id and not self._is_admin_role(viewer_role):
            return access_snapshot

        if self._is_admin_role(viewer_role):
            return access_snapshot

        if access_snapshot["is_system"]:
            raise MountingNodePermissionError("System mounting node access is restricted")

        if not access_snapshot["is_owner"]:
            return None

        return access_snapshot

    def _resolve_create_ownership(
        self,
        payload: Mapping[str, Any],
        *,
        viewer_user_id: Any = None,
        viewer_role: Any = None,
    ) -> tuple[str | None, str | None, str | None]:
        normalized_viewer_user_id = self._normalize_viewer_user_id(viewer_user_id)
        legacy_owner_user_id = self._optional_text(payload.get("owner_user_id"))
        legacy_created_by_user_id = self._optional_text(payload.get("created_by_user_id"))
        legacy_updated_by_user_id = self._optional_text(payload.get("updated_by_user_id"))

        if self._is_admin_role(viewer_role):
            owner_user_id = None
        elif normalized_viewer_user_id:
            owner_user_id = normalized_viewer_user_id
        else:
            owner_user_id = legacy_owner_user_id

        created_by_user_id = normalized_viewer_user_id or legacy_created_by_user_id
        updated_by_user_id = normalized_viewer_user_id or legacy_updated_by_user_id
        return owner_user_id, created_by_user_id, updated_by_user_id

    @staticmethod
    def _serialize_item(item) -> dict[str, Any]:
        fitting = getattr(item, "fitting", None)
        return {
            "id": item.id,
            "node_id": item.node_id,
            "fitting_id": item.fitting_id,
            "fitting_code": getattr(fitting, "code", None),
            "fitting_article": getattr(fitting, "article", None),
            "fitting_name": getattr(fitting, "name", None),
            "fitting_category_code": getattr(fitting, "fitting_type", None)
            or getattr(fitting, "fitting_group", None),
            "quantity": int(item.quantity or 0),
            "role": getattr(item, "role", None),
            "is_required": bool(getattr(item, "is_required", True)),
            "affects_processing": bool(getattr(item, "affects_processing", True)),
            "order_index": int(getattr(item, "order_index", 0) or 0),
        }

    @staticmethod
    def _serialize_point(point) -> dict[str, Any]:
        return {
            "id": point.id,
            "template_id": point.template_id,
            "label": getattr(point, "label", None),
            "x_mm": getattr(point, "x_mm", None),
            "y_mm": getattr(point, "y_mm", None),
            "z_mm": getattr(point, "z_mm", None),
            "target_panel": getattr(point, "target_panel", None),
            "target_surface": getattr(point, "target_surface", None),
            "target_side": getattr(point, "target_side", None),
            "diameter_mm": getattr(point, "diameter_mm", None),
            "service_drilling_rule_id": getattr(point, "service_drilling_rule_id", None),
            "depth_mm": getattr(point, "depth_mm", None),
            "side": getattr(point, "side", None),
            "operation": getattr(point, "operation", None),
            "order_index": int(getattr(point, "order_index", 0) or 0),
            "quantity": int(getattr(point, "quantity", 1) or 1),
            "mirrored": bool(getattr(point, "mirrored", False)),
            "notes": getattr(point, "notes", None),
        }

    def _serialize_template(self, template: FittingHoleTemplateModel) -> dict[str, Any]:
        points = sorted(
            list(getattr(template, "points", []) or []),
            key=lambda point: (
                int(getattr(point, "order_index", 0) or 0),
                int(getattr(point, "id", 0) or 0),
            ),
        )
        return {
            "id": template.id,
            "fitting_id": template.fitting_id,
            "name": getattr(template, "name", None),
            "bundle_key": getattr(template, "bundle_key", None),
            "bundle_name": getattr(template, "bundle_name", None),
            "bundle_order_index": int(getattr(template, "bundle_order_index", 0) or 0),
            "template_type": getattr(template, "template_type", None),
            "side": getattr(template, "side", None),
            "coordinate_system": getattr(template, "coordinate_system", None),
            "mounting_variant_key": getattr(template, "mounting_variant_key", None),
            "is_default": bool(getattr(template, "is_default", False)),
            "notes": getattr(template, "notes", None),
            "is_active": bool(getattr(template, "is_active", True)),
            "points": [self._serialize_point(point) for point in points],
        }

    def _serialize_template_link(self, link) -> dict[str, Any]:
        template = getattr(link, "template", None)
        fitting = getattr(template, "fitting", None)
        return {
            "id": link.id,
            "node_id": link.node_id,
            "template_id": link.template_id,
            "template_name": getattr(template, "name", None),
            "fitting_id": getattr(template, "fitting_id", None),
            "fitting_code": getattr(fitting, "code", None),
            "fitting_article": getattr(fitting, "article", None),
            "mounting_variant_key": getattr(template, "mounting_variant_key", None),
            "is_default": bool(getattr(link, "is_default", False)),
            "order_index": int(getattr(link, "order_index", 0) or 0),
            "points_count": len(getattr(template, "points", []) or []),
            "is_active": bool(getattr(template, "is_active", True)),
            "template": self._serialize_template(template) if template is not None else None,
        }

    def _serialize_node(
        self,
        node: MountingNodeModel,
        *,
        viewer_user_id: Any = None,
        viewer_role: Any = None,
    ) -> dict[str, Any]:
        items = list(getattr(node, "items", []) or [])
        templates = list(getattr(node, "templates", []) or [])
        ownership_snapshot = self._resolve_ownership_snapshot(
            node,
            viewer_user_id=viewer_user_id,
            viewer_role=viewer_role,
        )
        return {
            "id": node.id,
            "code": node.code,
            "name": node.name,
            "description": node.description,
            **ownership_snapshot,
            "is_active": bool(getattr(node, "is_active", True)),
            "created_by_user_id": getattr(node, "created_by_user_id", None),
            "updated_by_user_id": getattr(node, "updated_by_user_id", None),
            "created_at": getattr(node, "created_at", None),
            "updated_at": getattr(node, "updated_at", None),
            "items_count": len(items),
            "templates_count": len(templates),
            "items": [self._serialize_item(item) for item in items],
            "templates": [self._serialize_template_link(link) for link in templates],
        }

    @staticmethod
    def _normalize_search_text(value: Any) -> str:
        return " ".join(str(value or "").split()).strip().lower()

    def _node_matches_search(self, node: MountingNodeModel, search: str) -> bool:
        needle = self._normalize_search_text(search)
        if not needle:
            return True

        serialized = self._serialize_node(node)
        haystack: list[str] = [
            self._normalize_search_text(serialized.get("code")),
            self._normalize_search_text(serialized.get("name")),
            self._normalize_search_text(serialized.get("description")),
        ]

        for item in serialized.get("items", []):
            haystack.extend(
                [
                    self._normalize_search_text(item.get("fitting_code")),
                    self._normalize_search_text(item.get("fitting_article")),
                    self._normalize_search_text(item.get("fitting_name")),
                    self._normalize_search_text(item.get("fitting_category_code")),
                    self._normalize_search_text(item.get("role")),
                ]
            )

        for template in serialized.get("templates", []):
            haystack.extend(
                [
                    self._normalize_search_text(template.get("template_name")),
                    self._normalize_search_text(template.get("fitting_code")),
                    self._normalize_search_text(template.get("fitting_article")),
                    self._normalize_search_text(template.get("mounting_variant_key")),
                ]
            )

        return any(needle in value for value in haystack if value)

    @staticmethod
    def _normalize_item_payload(item: Mapping[str, Any]) -> dict[str, Any]:
        raw_quantity = item.get("quantity", 1)
        quantity = int(1 if raw_quantity is None else raw_quantity)
        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")
        return {
            "fitting_id": int(item["fitting_id"]),
            "quantity": quantity,
            "role": MountingNodeService._optional_text(item.get("role")),
            "is_required": MountingNodeService._normalize_bool(item.get("is_required"), True),
            "affects_processing": MountingNodeService._normalize_bool(item.get("affects_processing"), True),
            "order_index": int(item.get("order_index", 0) or 0),
        }

    @staticmethod
    def _normalize_template_payload(link: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "template_id": int(link["template_id"]) if link.get("template_id") not in (None, "") else None,
            "is_default": MountingNodeService._normalize_bool(link.get("is_default"), False),
            "order_index": int(link.get("order_index", 0) or 0),
            "template": link.get("template"),
        }

    def _normalize_template_payload_details(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        provided_fields = set(payload.keys())
        template_id = payload.get("template_id")
        fitting_id = payload.get("fitting_id")
        return {
            "provided_fields": provided_fields,
            "template_id": None if template_id in (None, "") else int(template_id),
            "fitting_id": None if fitting_id in (None, "") else int(fitting_id),
            "name": self._optional_text(payload.get("name")),
            "bundle_key": self._optional_text(payload.get("bundle_key")),
            "bundle_name": self._optional_text(payload.get("bundle_name")),
            "bundle_order_index": int(payload.get("bundle_order_index", 0) or 0),
            "template_type": self._optional_text(payload.get("template_type")),
            "side": self._optional_text(payload.get("side")),
            "coordinate_system": self._optional_text(payload.get("coordinate_system")),
            "mounting_variant_key": self._normalize_mounting_variant_key(payload.get("mounting_variant_key")),
            "is_default": self._normalize_bool(payload.get("is_default"), False),
            "notes": self._optional_text(payload.get("notes")),
            "is_active": self._normalize_bool(payload.get("is_active"), True),
            "sync_points": self._normalize_bool(payload.get("sync_points"), True),
            "points": list(payload.get("points") or []),
        }

    def _apply_point_payload(
        self,
        template: FittingHoleTemplateModel,
        point_payload: Mapping[str, Any],
    ) -> FittingHolePointModel:
        raw_point_id = point_payload.get("id")
        point_id = None if raw_point_id in (None, "") else int(raw_point_id)
        raw_template_id = point_payload.get("template_id")
        point_template_id = None if raw_template_id in (None, "") else int(raw_template_id)
        if point_template_id is not None and point_template_id != template.id:
            raise ValueError(f"Point with id={point_id or 'new'} does not belong to template_id={point_template_id}")

        if point_id is None:
            diameter_mm = point_payload.get("diameter_mm")
            if diameter_mm in (None, ""):
                raise ValueError("diameter_mm is required")
            point = FittingHolePointModel(
                template=template,
                label=self._optional_text(point_payload.get("label")),
                x_mm=None if point_payload.get("x_mm") in (None, "") else float(point_payload.get("x_mm")),
                y_mm=None if point_payload.get("y_mm") in (None, "") else float(point_payload.get("y_mm")),
                z_mm=None if point_payload.get("z_mm") in (None, "") else float(point_payload.get("z_mm")),
                target_panel=self._optional_text(point_payload.get("target_panel")),
                target_surface=self._optional_text(point_payload.get("target_surface")),
                target_side=self._optional_text(point_payload.get("target_side")),
                diameter_mm=self._require_positive_float(diameter_mm, "diameter_mm"),
                service_drilling_rule_id=None,
                depth_mm=self._optional_non_negative_float(point_payload.get("depth_mm"), "depth_mm"),
                side=self._optional_text(point_payload.get("side")),
                operation=self._optional_text(point_payload.get("operation")) or "drill",
                order_index=int(point_payload.get("order_index", 0) or 0),
                quantity=int(point_payload.get("quantity", 1) or 1),
                mirrored=self._normalize_bool(point_payload.get("mirrored"), False),
                notes=self._optional_text(point_payload.get("notes")),
            )
            if point.quantity <= 0:
                raise ValueError("quantity must be greater than 0")
            service_drilling_rule_id = point_payload.get("service_drilling_rule_id")
            if service_drilling_rule_id not in (None, ""):
                rule_id = int(service_drilling_rule_id)
                self._ensure_service_drilling_rule_exists(rule_id)
                point.service_drilling_rule_id = rule_id
            self.session.add(point)
            self.session.flush()
            return point

        point = self.session.get(FittingHolePointModel, point_id)
        if point is None:
            raise ValueError(f"Point with id={point_id} does not exist")
        if int(point.template_id) != int(template.id):
            raise ValueError(f"Point with id={point_id} does not belong to template_id={template.id}")

        if "label" in point_payload:
            point.label = self._optional_text(point_payload.get("label"))
        if "x_mm" in point_payload:
            point.x_mm = None if point_payload.get("x_mm") in (None, "") else float(point_payload.get("x_mm"))
        if "y_mm" in point_payload:
            point.y_mm = None if point_payload.get("y_mm") in (None, "") else float(point_payload.get("y_mm"))
        if "z_mm" in point_payload:
            point.z_mm = None if point_payload.get("z_mm") in (None, "") else float(point_payload.get("z_mm"))
        if "target_panel" in point_payload:
            point.target_panel = self._optional_text(point_payload.get("target_panel"))
        if "target_surface" in point_payload:
            point.target_surface = self._optional_text(point_payload.get("target_surface"))
        if "target_side" in point_payload:
            point.target_side = self._optional_text(point_payload.get("target_side"))
        if "diameter_mm" in point_payload:
            point.diameter_mm = self._require_positive_float(point_payload.get("diameter_mm"), "diameter_mm")
        if "service_drilling_rule_id" in point_payload:
            service_drilling_rule_id = point_payload.get("service_drilling_rule_id")
            if service_drilling_rule_id in (None, ""):
                point.service_drilling_rule_id = None
            else:
                rule_id = int(service_drilling_rule_id)
                self._ensure_service_drilling_rule_exists(rule_id)
                point.service_drilling_rule_id = rule_id
        if "depth_mm" in point_payload:
            point.depth_mm = self._optional_non_negative_float(point_payload.get("depth_mm"), "depth_mm")
        if "side" in point_payload:
            point.side = self._optional_text(point_payload.get("side"))
        if "operation" in point_payload:
            point.operation = self._optional_text(point_payload.get("operation")) or "drill"
        if "order_index" in point_payload:
            point.order_index = int(point_payload.get("order_index", 0) or 0)
        if "quantity" in point_payload:
            quantity = int(point_payload.get("quantity", 1) or 1)
            if quantity <= 0:
                raise ValueError("quantity must be greater than 0")
            point.quantity = quantity
        if "mirrored" in point_payload:
            point.mirrored = self._normalize_bool(point_payload.get("mirrored"), False)
        if "notes" in point_payload:
            point.notes = self._optional_text(point_payload.get("notes"))

        self.session.flush()
        return point

    def _sync_template_points(
        self,
        template: FittingHoleTemplateModel,
        point_payloads: list[Mapping[str, Any]],
        *,
        sync_points: bool,
    ) -> list[FittingHolePointModel]:
        existing_point_ids = {
            int(point.id)
            for point in list(getattr(template, "points", []) or [])
            if getattr(point, "id", None) is not None
        }
        kept_point_ids: set[int] = set()
        seen_point_ids: set[int] = set()
        processed_points: list[FittingHolePointModel] = []

        for point_payload in point_payloads:
            raw_point_id = point_payload.get("id")
            if raw_point_id not in (None, ""):
                point_id = int(raw_point_id)
                if point_id in seen_point_ids:
                    raise ValueError(f"Duplicate point_id={point_id} in points")
                seen_point_ids.add(point_id)
            point = self._apply_point_payload(template, point_payload)
            processed_points.append(point)
            kept_point_ids.add(int(point.id))

        if sync_points:
            stale_point_ids = existing_point_ids - kept_point_ids
            for point_id in stale_point_ids:
                point = self.session.get(FittingHolePointModel, point_id)
                if point is not None:
                    self.session.delete(point)
            self.session.flush()

        self.session.expire(template, ["points"])
        return processed_points

    def _validate_template_links(
        self,
        node_id: int | None,
        templates: list[dict[str, Any]],
        allowed_fitting_ids: set[int],
    ) -> list[dict[str, Any]]:
        validated_templates: list[dict[str, Any]] = []
        seen_template_ids: set[int] = set()
        default_by_variant: dict[str, int] = {}

        for link in templates:
            template_id = link.get("template_id")
            if template_id is None:
                raise ValueError("template_id is required")
            template_id = int(template_id)
            if template_id in seen_template_ids:
                raise ValueError(f"Duplicate template_id={template_id} in templates")

            template = self._ensure_template_exists(template_id)
            if template.fitting_id not in allowed_fitting_ids:
                raise ValueError(
                    f"Template with id={template_id} does not belong to the selected fittings"
                )

            owner_node_id = self.repository.template_link_owner_node_id(template_id)
            if owner_node_id is not None and owner_node_id != node_id:
                raise ValueError(f"Template with id={template_id} already belongs to another mounting node")

            variant_key = self._optional_text(getattr(template, "mounting_variant_key", None)) or ""
            if self._normalize_bool(link.get("is_default"), False):
                variant_count = default_by_variant.get(variant_key, 0) + 1
                default_by_variant[variant_key] = variant_count
                if variant_count > 1:
                    raise ValueError(
                        f"More than one default template is not allowed for mounting_variant_key={variant_key or 'unknown'}"
                    )

            seen_template_ids.add(template_id)
            validated_templates.append(
                {
                    "template_id": template_id,
                    "is_default": self._normalize_bool(link.get("is_default"), False),
                    "order_index": int(link.get("order_index", 0) or 0),
                }
            )

        return sorted(
            validated_templates,
            key=lambda link: (
                int(link.get("order_index", 0) or 0),
                int(link.get("template_id", 0) or 0),
            ),
        )

    def _create_or_update_template(
        self,
        node_id: int | None,
        template_link: Mapping[str, Any],
        allowed_fitting_ids: set[int],
    ) -> tuple[FittingHoleTemplateModel, dict[str, Any]]:
        normalized_link = self._normalize_template_payload(template_link)
        template_details_payload = template_link.get("template")

        if template_details_payload is None:
            template_id = normalized_link.get("template_id")
            if template_id is None:
                raise ValueError("template_id is required")
            template = self._ensure_template_exists(template_id)
            if template.fitting_id not in allowed_fitting_ids:
                raise ValueError(
                    f"Template with id={template_id} does not belong to the selected fittings"
                )
            owner_node_id = self.repository.template_link_owner_node_id(template_id)
            if owner_node_id is not None and owner_node_id != node_id:
                raise ValueError(f"Template with id={template_id} already belongs to another mounting node")
            return template, normalized_link

        template_details = self._normalize_template_payload_details(template_details_payload)
        effective_template_id = template_details["template_id"] or normalized_link.get("template_id")
        provided_fields = template_details["provided_fields"]
        if (
            template_details["template_id"] is not None
            and normalized_link.get("template_id") is not None
            and int(template_details["template_id"]) != int(normalized_link["template_id"])
        ):
            raise ValueError(
                f"template_id={normalized_link['template_id']} does not match template_id={template_details['template_id']}"
            )
        template: FittingHoleTemplateModel
        if effective_template_id is not None:
            template = self._ensure_template_exists(effective_template_id)
            owner_node_id = self.repository.template_link_owner_node_id(effective_template_id)
            if owner_node_id is not None and owner_node_id != node_id:
                raise ValueError(
                    f"Template with id={effective_template_id} already belongs to another mounting node"
                )
            if template_details["fitting_id"] is not None and int(template.fitting_id) != int(template_details["fitting_id"]):
                raise ValueError(
                    f"Template with id={effective_template_id} does not belong to fitting_id={template_details['fitting_id']}"
                )
            if template.fitting_id not in allowed_fitting_ids:
                raise ValueError(
                    f"Template with id={effective_template_id} does not belong to the selected fittings"
                )
        else:
            if template_details["fitting_id"] is None:
                raise ValueError("fitting_id is required when template_id is not provided")
            if template_details["fitting_id"] not in allowed_fitting_ids:
                raise ValueError(
                    f"Template with fitting_id={template_details['fitting_id']} does not belong to the selected fittings"
                )
            fitting = self.repository.get_fitting_by_id(template_details["fitting_id"])
            if fitting is None:
                raise ValueError(f"Fitting with id={template_details['fitting_id']} does not exist")
            template = FittingHoleTemplateModel(
                fitting_id=template_details["fitting_id"],
            )
            self.session.add(template)
            self.session.flush()
            owner_node_id = self.repository.template_link_owner_node_id(template.id)
            if owner_node_id is not None and owner_node_id != node_id:
                raise ValueError(
                    f"Template with id={template.id} already belongs to another mounting node"
                )
            normalized_link["template_id"] = template.id

        if effective_template_id is None:
            default_name = self._text_or_default(
                getattr(fitting, "name", None)
                or getattr(fitting, "article", None)
                or getattr(fitting, "code", None)
                or "Template",
                "Template",
            )
            template.name = template_details["name"] or default_name
            template.bundle_key = template_details["bundle_key"] or None
            template.bundle_name = template_details["bundle_name"] or None
            template.bundle_order_index = int(template_details["bundle_order_index"] or 0)
            template.template_type = template_details["template_type"] or "manual"
            template.side = template_details["side"] or None
            template.coordinate_system = template_details["coordinate_system"] or "2d"
            template.mounting_variant_key = template_details["mounting_variant_key"]
            template.is_default = template_details["is_default"]
            template.notes = template_details["notes"] or None
            template.is_active = template_details["is_active"]
        else:
            if "name" in provided_fields:
                template.name = template_details["name"]
            if "bundle_key" in provided_fields:
                template.bundle_key = template_details["bundle_key"] or None
            if "bundle_name" in provided_fields:
                template.bundle_name = template_details["bundle_name"] or None
            if "bundle_order_index" in provided_fields:
                template.bundle_order_index = int(template_details["bundle_order_index"] or 0)
            if "template_type" in provided_fields:
                template.template_type = template_details["template_type"] or None
            if "side" in provided_fields:
                template.side = template_details["side"] or None
            if "coordinate_system" in provided_fields:
                template.coordinate_system = template_details["coordinate_system"] or None
            if "mounting_variant_key" in provided_fields:
                template.mounting_variant_key = template_details["mounting_variant_key"]
            if "is_default" in provided_fields:
                template.is_default = template_details["is_default"]
            if "notes" in provided_fields:
                template.notes = template_details["notes"] or None
            if "is_active" in provided_fields:
                template.is_active = template_details["is_active"]

        if template_details_payload is not None and "points" in provided_fields:
            self._sync_template_points(
                template,
                template_details["points"],
                sync_points=template_details["sync_points"],
            )

        self.session.flush()
        return template, normalized_link

    def _resolve_items(self, payload_items: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        if not payload_items:
            raise ValueError("items is required")

        normalized_items: list[dict[str, Any]] = []
        seen_fitting_ids: set[int] = set()
        for item in payload_items:
            normalized = self._normalize_item_payload(item)
            fitting_id = normalized["fitting_id"]
            if fitting_id in seen_fitting_ids:
                raise ValueError(f"Duplicate fitting_id={fitting_id} in items")
            self._ensure_fitting_exists(fitting_id)
            seen_fitting_ids.add(fitting_id)
            normalized_items.append(normalized)

        return sorted(
            normalized_items,
            key=lambda item: (
                int(item.get("order_index", 0) or 0),
                int(item.get("fitting_id", 0) or 0),
            ),
        )

    def _resolve_templates(
        self,
        node_id: int | None,
        templates: list[Mapping[str, Any]],
        allowed_fitting_ids: set[int],
    ) -> list[dict[str, Any]]:
        normalized_templates: list[dict[str, Any]] = []
        seen_template_ids: set[int] = set()
        default_by_variant: dict[str, int] = {}

        for link in templates:
            normalized = self._normalize_template_payload(link)
            template_id = normalized["template_id"]
            if template_id in seen_template_ids:
                raise ValueError(f"Duplicate template_id={template_id} in templates")
            template = self._ensure_template_exists(template_id)
            if template.fitting_id not in allowed_fitting_ids:
                raise ValueError(
                    f"Template with id={template_id} does not belong to the selected fittings"
                )

            owner_node_id = self.repository.template_link_owner_node_id(template_id)
            if owner_node_id is not None and owner_node_id != node_id:
                raise ValueError(f"Template with id={template_id} already belongs to another mounting node")

            variant_key = self._optional_text(getattr(template, "mounting_variant_key", None)) or ""
            if normalized["is_default"]:
                variant_count = default_by_variant.get(variant_key, 0) + 1
                default_by_variant[variant_key] = variant_count
                if variant_count > 1:
                    raise ValueError(
                        f"More than one default template is not allowed for mounting_variant_key={variant_key or 'unknown'}"
                    )

            seen_template_ids.add(template_id)
            normalized_templates.append(normalized)

        return sorted(
            normalized_templates,
            key=lambda link: (
                int(link.get("order_index", 0) or 0),
                int(link.get("template_id", 0) or 0),
            ),
        )

    def list_mounting_nodes(
        self,
        include_inactive: bool = False,
        fitting_id: int | None = None,
        mounting_variant_key: str | None = None,
        search: str | None = None,
        viewer_user_id: Any = None,
        viewer_role: Any = None,
    ) -> list[dict[str, Any]]:
        nodes = self.repository.list_nodes(
            include_inactive=include_inactive,
            fitting_id=fitting_id,
            mounting_variant_key=mounting_variant_key,
            viewer_user_id=self._normalize_viewer_user_id(viewer_user_id),
            viewer_role=viewer_role,
        )
        summaries = [
            {
                key: value
                for key, value in self._serialize_node(
                    node,
                    viewer_user_id=viewer_user_id,
                    viewer_role=viewer_role,
                ).items()
                if key not in {"items", "templates"}
            }
            for node in nodes
        ]

        if search is not None and str(search).strip():
            matched_summaries = []
            for node, summary in zip(nodes, summaries):
                if self._node_matches_search(node, search):
                    matched_summaries.append(summary)
            return matched_summaries

        return summaries

    def get_mounting_node(
        self,
        node_id: int,
        *,
        viewer_user_id: Any = None,
        viewer_role: Any = None,
    ) -> dict[str, Any] | None:
        node_id = self._require_int(node_id, "node_id")
        node = self.repository.get_node_by_id(node_id)
        if node is None:
            return None

        ownership_snapshot = self._resolve_ownership_snapshot(
            node,
            viewer_user_id=viewer_user_id,
            viewer_role=viewer_role,
        )
        if not self._is_admin_role(viewer_role) and ownership_snapshot["owner_user_id"] is not None and not ownership_snapshot["is_owner"]:
            return None

        return self._serialize_node(
            node,
            viewer_user_id=viewer_user_id,
            viewer_role=viewer_role,
        )

    def create_mounting_node(
        self,
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = self._merge_payload(data, **kwargs)
        return self._create_mounting_node(
            payload,
            viewer_user_id=payload.get("viewer_user_id"),
            viewer_role=payload.get("viewer_role"),
        )

    def _create_mounting_node(
        self,
        payload: Mapping[str, Any],
        *,
        viewer_user_id: Any = None,
        viewer_role: Any = None,
    ) -> dict[str, Any]:
        name = self._require_text(payload.get("name"), "name")
        code = self._optional_text(payload.get("code")) or self._generate_code(name)
        description = self._optional_text(payload.get("description"))
        is_active = self._normalize_bool(payload.get("is_active"), True)
        owner_user_id, created_by_user_id, updated_by_user_id = self._resolve_create_ownership(
            payload,
            viewer_user_id=viewer_user_id,
            viewer_role=viewer_role,
        )

        items = self._resolve_items(list(payload.get("items") or []))
        allowed_fitting_ids = {item["fitting_id"] for item in items}
        raw_templates = list(payload.get("templates") or [])

        if self.repository.get_node_by_code(code):
            raise ValueError(f"Mounting node with code={code} already exists")

        self.session.rollback()
        with self.session.begin():
            node = self.repository.create_node(
                code=code,
                name=name,
                description=description,
                is_active=is_active,
                owner_user_id=owner_user_id,
                created_by_user_id=created_by_user_id,
                updated_by_user_id=updated_by_user_id,
            )
            self.repository.replace_items(node, items)
            resolved_templates: list[dict[str, Any]] = []
            for template_link in raw_templates:
                if template_link.get("template") is not None:
                    _, normalized_link = self._create_or_update_template(node.id, template_link, allowed_fitting_ids)
                    resolved_templates.append(normalized_link)
                else:
                    normalized_link = self._normalize_template_payload(template_link)
                    if normalized_link["template_id"] is None:
                        raise ValueError("template_id is required")
                    resolved_templates.append(normalized_link)

            resolved_templates = self._validate_template_links(node.id, resolved_templates, allowed_fitting_ids)
            self.repository.replace_templates(node, resolved_templates)
            self.session.flush()

        refreshed = self.repository.get_node_by_id(node.id)
        return self._serialize_node(
            refreshed or node,
            viewer_user_id=viewer_user_id,
            viewer_role=viewer_role,
        )

    def update_mounting_node(
        self,
        node_id: int,
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        payload = self._merge_payload(data, **kwargs)
        return self._update_mounting_node(
            node_id,
            payload,
            viewer_user_id=payload.get("viewer_user_id"),
            viewer_role=payload.get("viewer_role"),
        )

    def _update_mounting_node(
        self,
        node_id: int,
        payload: Mapping[str, Any],
        *,
        viewer_user_id: Any = None,
        viewer_role: Any = None,
    ) -> dict[str, Any] | None:
        node_id = self._require_int(node_id, "node_id")
        node = self.repository.get_node_by_id(node_id)
        if node is None:
            return None

        access_snapshot = self._assert_mutation_access(
            node,
            viewer_user_id=viewer_user_id,
            viewer_role=viewer_role,
        )
        if access_snapshot is None:
            return None

        update_fields: dict[str, Any] = {}
        normalized_viewer_user_id = self._normalize_viewer_user_id(viewer_user_id)

        if "code" in payload:
            code = self._optional_text(payload.get("code"))
            if not code:
                code = self._generate_code(self._require_text(payload.get("name", node.name), "name"))
            existing = self.repository.get_node_by_code(code, exclude_node_id=node.id)
            if existing is not None:
                raise ValueError(f"Mounting node with code={code} already exists")
            update_fields["code"] = code

        if "name" in payload:
            update_fields["name"] = self._require_text(payload.get("name"), "name")

        if "description" in payload:
            update_fields["description"] = self._optional_text(payload.get("description"))

        if "is_active" in payload:
            update_fields["is_active"] = self._normalize_bool(payload.get("is_active"), True)

        if normalized_viewer_user_id:
            update_fields["updated_by_user_id"] = normalized_viewer_user_id

        items_payload = payload.get("items")
        templates_payload = payload.get("templates")

        if items_payload is not None:
            items = self._resolve_items(list(items_payload))
        else:
            items = [
                {
                    "fitting_id": item.fitting_id,
                    "quantity": item.quantity,
                    "role": item.role,
                    "is_required": item.is_required,
                    "affects_processing": item.affects_processing,
                    "order_index": item.order_index,
                }
                for item in getattr(node, "items", []) or []
            ]

        allowed_fitting_ids = {item["fitting_id"] for item in items}

        self.session.rollback()
        with self.session.begin():
            if update_fields:
                node = self.repository.update_node(node, **update_fields)

            if items_payload is not None:
                self.repository.replace_items(node, items)

            if templates_payload is not None:
                resolved_templates: list[dict[str, Any]] = []
                for template_link in list(templates_payload):
                    if template_link.get("template") is not None:
                        _, normalized_link = self._create_or_update_template(node.id, template_link, allowed_fitting_ids)
                        resolved_templates.append(normalized_link)
                    else:
                        normalized_link = self._normalize_template_payload(template_link)
                        if normalized_link["template_id"] is None:
                            raise ValueError("template_id is required")
                        resolved_templates.append(normalized_link)

                resolved_templates = self._validate_template_links(node.id, resolved_templates, allowed_fitting_ids)
                self.repository.replace_templates(node, resolved_templates)

            self.session.flush()

        refreshed = self.repository.get_node_by_id(node.id)
        if refreshed is None:
            return None
        return self._serialize_node(
            refreshed,
            viewer_user_id=viewer_user_id,
            viewer_role=viewer_role,
        )

    def delete_mounting_node(
        self,
        node_id: int,
        *,
        viewer_user_id: Any = None,
        viewer_role: Any = None,
    ) -> bool | None:
        node_id = self._require_int(node_id, "node_id")
        node = self.repository.get_node_by_id(node_id)
        if node is None:
            return None

        access_snapshot = self._assert_mutation_access(
            node,
            viewer_user_id=viewer_user_id,
            viewer_role=viewer_role,
        )
        if access_snapshot is None:
            return None

        linked_templates = list(getattr(node, "templates", []) or [])

        self.session.rollback()
        with self.session.begin():
            self.session.delete(node)
            self.session.flush()

            for link in linked_templates:
                template = getattr(link, "template", None)
                if template is not None:
                    self.session.delete(template)

            self.session.flush()

        return True


__all__ = [
    "MountingNodePermissionError",
    "MountingNodeService",
]
