from __future__ import annotations

import re
from typing import Any, Mapping, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from database.models.fitting import FittingHoleTemplateModel
from database.models.mounting_node import MountingNodeModel
from database.repositories.mounting_node_repository import MountingNodeRepository
from database.session import SessionLocal


class MountingNodeService:
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

    def _ensure_node_exists(self, node_id: int) -> MountingNodeModel:
        node = self.repository.get_node_by_id(node_id)
        if node is None:
            raise ValueError(f"Mounting node with id={node_id} does not exist")
        return node

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
    def _serialize_template_link(link) -> dict[str, Any]:
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
        }

    def _serialize_node(self, node: MountingNodeModel) -> dict[str, Any]:
        items = list(getattr(node, "items", []) or [])
        templates = list(getattr(node, "templates", []) or [])
        return {
            "id": node.id,
            "code": node.code,
            "name": node.name,
            "description": node.description,
            "owner_user_id": getattr(node, "owner_user_id", None),
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
            "template_id": int(link["template_id"]),
            "is_default": MountingNodeService._normalize_bool(link.get("is_default"), False),
            "order_index": int(link.get("order_index", 0) or 0),
        }

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
    ) -> list[dict[str, Any]]:
        nodes = self.repository.list_nodes(
            include_inactive=include_inactive,
            fitting_id=fitting_id,
            mounting_variant_key=mounting_variant_key,
        )
        return [
            {
                key: value
                for key, value in self._serialize_node(node).items()
                if key not in {"items", "templates"}
            }
            for node in nodes
        ]

    def get_mounting_node(self, node_id: int) -> dict[str, Any] | None:
        node_id = self._require_int(node_id, "node_id")
        node = self.repository.get_node_by_id(node_id)
        if node is None:
            return None
        return self._serialize_node(node)

    def create_mounting_node(
        self,
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = self._merge_payload(data, **kwargs)
        name = self._require_text(payload.get("name"), "name")
        code = self._optional_text(payload.get("code")) or self._generate_code(name)
        description = self._optional_text(payload.get("description"))
        is_active = self._normalize_bool(payload.get("is_active"), True)

        items = self._resolve_items(list(payload.get("items") or []))
        allowed_fitting_ids = {item["fitting_id"] for item in items}
        templates = self._resolve_templates(None, list(payload.get("templates") or []), allowed_fitting_ids)

        if self.repository.get_node_by_code(code):
            raise ValueError(f"Mounting node with code={code} already exists")

        self.session.rollback()
        with self.session.begin():
            node = self.repository.create_node(
                code=code,
                name=name,
                description=description,
                is_active=is_active,
                owner_user_id=self._optional_text(payload.get("owner_user_id")),
                created_by_user_id=self._optional_text(payload.get("created_by_user_id")),
                updated_by_user_id=self._optional_text(payload.get("updated_by_user_id")),
            )
            self.repository.replace_items(node, items)
            self.repository.replace_templates(node, templates)
            self.session.flush()

        refreshed = self.repository.get_node_by_id(node.id)
        return self._serialize_node(refreshed or node)

    def update_mounting_node(
        self,
        node_id: int,
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        node_id = self._require_int(node_id, "node_id")
        node = self.repository.get_node_by_id(node_id)
        if node is None:
            return None

        payload = self._merge_payload(data, **kwargs)
        update_fields: dict[str, Any] = {}

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
        if templates_payload is not None:
            templates = self._resolve_templates(node.id, list(templates_payload), allowed_fitting_ids)
        else:
            templates = [
                {
                    "template_id": link.template_id,
                    "is_default": link.is_default,
                    "order_index": link.order_index,
                }
                for link in getattr(node, "templates", []) or []
            ]

        self.session.rollback()
        with self.session.begin():
            if update_fields:
                node = self.repository.update_node(node, **update_fields)

            if items_payload is not None:
                self.repository.replace_items(node, items)

            if templates_payload is not None:
                self.repository.replace_templates(node, templates)

            self.session.flush()

        refreshed = self.repository.get_node_by_id(node.id)
        if refreshed is None:
            return None
        return self._serialize_node(refreshed)


__all__ = ["MountingNodeService"]
