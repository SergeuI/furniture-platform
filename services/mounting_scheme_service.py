from __future__ import annotations

import re
from typing import Any, Mapping, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from database.models.mounting_node import MountingNodeModel
from database.models.mounting_scheme import MountingSchemeModel
from database.repositories.mounting_scheme_repository import MountingSchemeRepository
from database.session import SessionLocal


class MountingSchemeService:
    _ALLOWED_DISTRIBUTION_MODES = {
        "equal",
        "fixed_spacing",
        "centered",
    }

    def __init__(
        self,
        session: Optional[Session] = None,
        repository: Optional[MountingSchemeRepository] = None,
    ) -> None:
        if repository is not None and session is None:
            session = getattr(repository, "session", None)

        self.session = session or SessionLocal()
        self._owns_session = session is None and repository is None
        self.repository = repository or MountingSchemeRepository(self.session)

    def close(self) -> None:
        if self._owns_session and self.session is not None:
            self.session.close()

    def __enter__(self) -> "MountingSchemeService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def _merge_payload(data: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = dict(data or {})
        payload.update(kwargs)
        return payload

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _require_text(value: Any, field_name: str) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            raise ValueError(f"{field_name} is required")
        return text

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
    def _normalize_int(value: Any, field_name: str) -> int:
        if value is None or value == "":
            raise ValueError(f"{field_name} is required")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be an integer") from exc

    @staticmethod
    def _optional_positive_int(value: Any, field_name: str, *, allow_zero: bool = False) -> int | None:
        if value is None or value == "":
            return None
        try:
            numeric_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be an integer") from exc
        if allow_zero:
            if numeric_value < 0:
                raise ValueError(f"{field_name} cannot be negative")
        elif numeric_value <= 0:
            raise ValueError(f"{field_name} must be greater than 0")
        return numeric_value

    @staticmethod
    def _slugify(text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug or "scheme"

    def _generate_code(self, name: str) -> str:
        slug = self._slugify(name)[:48]
        return f"mounting-scheme-{slug}-{uuid4().hex[:8]}"

    def _normalize_distribution_mode(self, value: Any) -> str:
        mode = self._optional_text(value) or "equal"
        mode = mode.lower()
        if mode not in self._ALLOWED_DISTRIBUTION_MODES:
            allowed = ", ".join(sorted(self._ALLOWED_DISTRIBUTION_MODES))
            raise ValueError(f"distribution_mode must be one of: {allowed}")
        return mode

    def _resolve_nodes(self, nodes_payload: Any) -> list[dict[str, Any]]:
        raw_nodes = list(nodes_payload or [])
        if not raw_nodes:
            raise ValueError("nodes must contain at least one mounting node")

        normalized_nodes: list[dict[str, Any]] = []
        for raw_node in raw_nodes:
            if not isinstance(raw_node, Mapping):
                raise ValueError("nodes must be objects")

            node_id = self._normalize_int(raw_node.get("node_id"), "node_id")
            mounted_node = self.repository.get_mounting_node_by_id(node_id)
            if mounted_node is None:
                raise ValueError(f"Mounting node with id={node_id} does not exist")

            group_key = self._require_text(raw_node.get("group_key"), "group_key")
            quantity_per_group = self._normalize_int(raw_node.get("quantity_per_group", 1), "quantity_per_group")
            if quantity_per_group <= 0:
                raise ValueError("quantity_per_group must be greater than 0")

            normalized_nodes.append(
                {
                    "node_id": node_id,
                    "group_key": group_key,
                    "quantity_per_group": quantity_per_group,
                    "role_code": self._optional_text(raw_node.get("role_code")),
                    "order_index": int(raw_node.get("order_index", 0) or 0),
                    "is_required": self._normalize_bool(raw_node.get("is_required"), True),
                }
            )

        return sorted(
            normalized_nodes,
            key=lambda item: (
                int(item.get("order_index", 0) or 0),
                int(item.get("node_id", 0) or 0),
            ),
        )

    def _resolve_placement_rules(
        self,
        placement_rules_payload: Any,
        *,
        allowed_group_keys: set[str],
    ) -> list[dict[str, Any]]:
        raw_rules = list(placement_rules_payload or [])
        normalized_rules: list[dict[str, Any]] = []

        for raw_rule in raw_rules:
            if not isinstance(raw_rule, Mapping):
                raise ValueError("placement_rules must be objects")

            group_key = self._require_text(raw_rule.get("group_key"), "group_key")
            if group_key not in allowed_group_keys:
                raise ValueError(f"placement rule group_key={group_key} must exist among scheme nodes")

            min_group_count = self._normalize_int(raw_rule.get("min_group_count", 1), "min_group_count")
            if min_group_count <= 0:
                raise ValueError("min_group_count must be greater than 0")

            max_group_count = self._optional_positive_int(raw_rule.get("max_group_count"), "max_group_count")
            fixed_group_count = self._optional_positive_int(raw_rule.get("fixed_group_count"), "fixed_group_count")
            start_offset_mm = self._optional_positive_int(raw_rule.get("start_offset_mm"), "start_offset_mm", allow_zero=True)
            end_offset_mm = self._optional_positive_int(raw_rule.get("end_offset_mm"), "end_offset_mm", allow_zero=True)
            max_spacing_mm = self._optional_positive_int(raw_rule.get("max_spacing_mm"), "max_spacing_mm")
            fixed_spacing_mm = self._optional_positive_int(raw_rule.get("fixed_spacing_mm"), "fixed_spacing_mm")
            distribution_mode = self._normalize_distribution_mode(raw_rule.get("distribution_mode"))

            if max_group_count is not None and max_group_count < min_group_count:
                raise ValueError("max_group_count must be greater than or equal to min_group_count")

            if fixed_group_count is not None:
                if min_group_count != fixed_group_count:
                    raise ValueError("fixed_group_count must match min_group_count")
                if max_group_count is not None and max_group_count != fixed_group_count:
                    raise ValueError("fixed_group_count must match max_group_count")

            normalized_rules.append(
                {
                    "group_key": group_key,
                    "distribution_mode": distribution_mode,
                    "min_group_count": min_group_count,
                    "max_group_count": max_group_count,
                    "fixed_group_count": fixed_group_count,
                    "start_offset_mm": start_offset_mm,
                    "end_offset_mm": end_offset_mm,
                    "max_spacing_mm": max_spacing_mm,
                    "fixed_spacing_mm": fixed_spacing_mm,
                }
            )

        return sorted(
            normalized_rules,
            key=lambda item: (
                item["group_key"],
                item["distribution_mode"],
            ),
        )

    @staticmethod
    def _serialize_node_link(link) -> dict[str, Any]:
        node = getattr(link, "node", None)
        return {
            "id": link.id,
            "scheme_id": link.scheme_id,
            "node_id": link.node_id,
            "node_code": getattr(node, "code", None),
            "node_name": getattr(node, "name", None),
            "group_key": getattr(link, "group_key", None),
            "quantity_per_group": int(getattr(link, "quantity_per_group", 0) or 0),
            "role_code": getattr(link, "role_code", None),
            "order_index": int(getattr(link, "order_index", 0) or 0),
            "is_required": bool(getattr(link, "is_required", True)),
        }

    @staticmethod
    def _serialize_placement_rule(rule) -> dict[str, Any]:
        return {
            "id": rule.id,
            "scheme_id": rule.scheme_id,
            "group_key": rule.group_key,
            "distribution_mode": rule.distribution_mode,
            "min_group_count": int(getattr(rule, "min_group_count", 0) or 0),
            "max_group_count": getattr(rule, "max_group_count", None),
            "fixed_group_count": getattr(rule, "fixed_group_count", None),
            "start_offset_mm": getattr(rule, "start_offset_mm", None),
            "end_offset_mm": getattr(rule, "end_offset_mm", None),
            "max_spacing_mm": getattr(rule, "max_spacing_mm", None),
            "fixed_spacing_mm": getattr(rule, "fixed_spacing_mm", None),
        }

    def _serialize_scheme(
        self,
        scheme: MountingSchemeModel,
        *,
        include_nested: bool = True,
    ) -> dict[str, Any]:
        nodes = list(getattr(scheme, "nodes", []) or [])
        placement_rules = list(getattr(scheme, "placement_rules", []) or [])
        payload = {
            "id": scheme.id,
            "code": scheme.code,
            "name": scheme.name,
            "description": scheme.description,
            "is_active": bool(getattr(scheme, "is_active", True)),
            "created_at": getattr(scheme, "created_at", None),
            "updated_at": getattr(scheme, "updated_at", None),
            "nodes_count": len(nodes),
            "placement_rules_count": len(placement_rules),
        }

        if include_nested:
            payload["nodes"] = [self._serialize_node_link(node) for node in nodes]
            payload["placement_rules"] = [self._serialize_placement_rule(rule) for rule in placement_rules]

        return payload

    def list_mounting_schemes(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        schemes = self.repository.list_schemes(include_inactive=include_inactive)
        return [self._serialize_scheme(scheme, include_nested=False) for scheme in schemes]

    def get_mounting_scheme(self, scheme_id: int) -> dict[str, Any] | None:
        scheme = self.repository.get_scheme_by_id(self._normalize_int(scheme_id, "scheme_id"))
        if scheme is None:
            return None
        return self._serialize_scheme(scheme, include_nested=True)

    def create_mounting_scheme(
        self,
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = self._merge_payload(data, **kwargs)
        return self._create_mounting_scheme(payload)

    def _create_mounting_scheme(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        name = self._require_text(payload.get("name"), "name")
        code = self._optional_text(payload.get("code")) or self._generate_code(name)
        description = self._optional_text(payload.get("description"))
        is_active = self._normalize_bool(payload.get("is_active"), True)

        if self.repository.get_scheme_by_code(code):
            raise ValueError(f"Mounting scheme with code={code} already exists")

        nodes = self._resolve_nodes(payload.get("nodes"))
        nodes_group_keys = {node["group_key"] for node in nodes}
        placement_rules = self._resolve_placement_rules(
            payload.get("placement_rules"),
            allowed_group_keys=nodes_group_keys,
        )

        self.session.rollback()
        with self.session.begin():
            scheme = self.repository.create_scheme(
                code=code,
                name=name,
                description=description,
                is_active=is_active,
            )
            self.repository.replace_nodes(scheme, nodes)
            if placement_rules:
                self.repository.replace_placement_rules(scheme, placement_rules)

        refreshed = self.repository.get_scheme_by_id(scheme.id)
        return self._serialize_scheme(refreshed or scheme, include_nested=True)

    def update_mounting_scheme(
        self,
        scheme_id: int,
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        payload = self._merge_payload(data, **kwargs)
        return self._update_mounting_scheme(scheme_id, payload)

    def _update_mounting_scheme(self, scheme_id: int, payload: Mapping[str, Any]) -> dict[str, Any] | None:
        scheme_id = self._normalize_int(scheme_id, "scheme_id")
        scheme = self.repository.get_scheme_by_id(scheme_id)
        if scheme is None:
            return None

        update_fields: dict[str, Any] = {}

        if "code" in payload:
            code = self._optional_text(payload.get("code"))
            if not code:
                code = self._generate_code(self._require_text(payload.get("name", scheme.name), "name"))
            existing = self.repository.get_scheme_by_code(code, exclude_scheme_id=scheme.id)
            if existing is not None:
                raise ValueError(f"Mounting scheme with code={code} already exists")
            update_fields["code"] = code

        if "name" in payload:
            update_fields["name"] = self._require_text(payload.get("name"), "name")

        if "description" in payload:
            update_fields["description"] = self._optional_text(payload.get("description"))

        if "is_active" in payload:
            update_fields["is_active"] = self._normalize_bool(payload.get("is_active"), True)

        nodes_payload = payload.get("nodes")
        placement_rules_payload = payload.get("placement_rules")

        if nodes_payload is not None:
            nodes = self._resolve_nodes(nodes_payload)
        else:
            nodes = [
                {
                    "node_id": link.node_id,
                    "group_key": link.group_key,
                    "quantity_per_group": link.quantity_per_group,
                    "role_code": link.role_code,
                    "order_index": link.order_index,
                    "is_required": link.is_required,
                }
                for link in list(getattr(scheme, "nodes", []) or [])
            ]

        nodes_group_keys = {node["group_key"] for node in nodes}

        if placement_rules_payload is not None:
            placement_rules = self._resolve_placement_rules(
                placement_rules_payload,
                allowed_group_keys=nodes_group_keys,
            )
        else:
            placement_rules = [
                {
                    "group_key": rule.group_key,
                    "distribution_mode": rule.distribution_mode,
                    "min_group_count": rule.min_group_count,
                    "max_group_count": rule.max_group_count,
                    "fixed_group_count": rule.fixed_group_count,
                    "start_offset_mm": rule.start_offset_mm,
                    "end_offset_mm": rule.end_offset_mm,
                    "max_spacing_mm": rule.max_spacing_mm,
                    "fixed_spacing_mm": rule.fixed_spacing_mm,
                }
                for rule in list(getattr(scheme, "placement_rules", []) or [])
            ]

            missing_rule_groups = [
                rule["group_key"]
                for rule in placement_rules
                if rule["group_key"] not in nodes_group_keys
            ]
            if missing_rule_groups:
                missing_groups = ", ".join(sorted(set(missing_rule_groups)))
                raise ValueError(f"placement rule group_key must exist among scheme nodes: {missing_groups}")

        self.session.rollback()
        with self.session.begin():
            if update_fields:
                scheme = self.repository.update_scheme(scheme, **update_fields)

            if nodes_payload is not None:
                self.repository.replace_nodes(scheme, nodes)

            if placement_rules_payload is not None:
                self.repository.replace_placement_rules(scheme, placement_rules)

        refreshed = self.repository.get_scheme_by_id(scheme.id)
        if refreshed is None:
            return None
        return self._serialize_scheme(refreshed, include_nested=True)
