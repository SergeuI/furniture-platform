from __future__ import annotations

from typing import Any, Dict, Mapping, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from database.models.fitting import FittingHoleTemplateModel, FittingModel
from database.repositories.fitting_holes_repository import FittingHolesRepository
from database.session import SessionLocal


class FittingHolesService:
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
        repository: Optional[FittingHolesRepository] = None,
    ) -> None:
        if repository is not None and session is None:
            session = getattr(repository, "session", None)

        self.session = session or SessionLocal()
        self._owns_session = session is None and repository is None
        self.repository = repository or FittingHolesRepository(self.session)

    def close(self) -> None:
        if self._owns_session and self.session is not None:
            self.session.close()

    def __enter__(self) -> "FittingHolesService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -------------------------
    # Helpers
    # -------------------------
    @staticmethod
    def _merge_payload(
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = dict(data or {})
        payload.update(kwargs)
        return payload

    @staticmethod
    def _require_int(value: Any, field_name: str) -> int:
        if value is None or value == "":
            raise ValueError(f"{field_name} is required")

        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be an integer") from exc

    @staticmethod
    def _require_positive_float(value: Any, field_name: str) -> float:
        if value is None or value == "":
            raise ValueError(f"{field_name} is required")

        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be a number") from exc

        if numeric_value <= 0:
            raise ValueError(f"{field_name} must be greater than 0")

        return numeric_value

    @staticmethod
    def _optional_non_negative_float(value: Any, field_name: str) -> Optional[float]:
        if value is None or value == "":
            return None

        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be a number") from exc

        if numeric_value < 0:
            raise ValueError(f"{field_name} cannot be negative")

        return numeric_value

    @staticmethod
    def _require_text(value: Any, field_name: str) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            raise ValueError(f"{field_name} is required")
        return text

    @staticmethod
    def _text_or_default(value: Any, default: str) -> str:
        text = "" if value is None else str(value).strip()
        return text or default

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

    @classmethod
    def _normalize_mounting_variant_key(cls, value: Any) -> str:
        key = "" if value is None else str(value).strip()
        if key in cls._ALLOWED_MOUNTING_VARIANT_KEYS:
            return key
        return "surface_mount"

    def _ensure_fitting_exists(self, fitting_id: int) -> FittingModel:
        fitting = self.session.get(FittingModel, fitting_id)
        if fitting is None:
            raise ValueError(f"Fitting with id={fitting_id} does not exist")
        return fitting

    def get_fitting(self, fitting_id: int):
        fitting_id = self._require_int(fitting_id, "fitting_id")
        return self.session.get(FittingModel, fitting_id)

    def _ensure_template_exists(self, template_id: int) -> FittingHoleTemplateModel:
        template = self.session.get(FittingHoleTemplateModel, template_id)
        if template is None:
            raise ValueError(f"Template with id={template_id} does not exist")
        return template

    # -------------------------
    # Templates
    # -------------------------
    def create_template(
        self,
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ):
        payload = self._merge_payload(data, **kwargs)

        fitting_id = self._require_int(payload.get("fitting_id"), "fitting_id")
        self._ensure_fitting_exists(fitting_id)

        payload["fitting_id"] = fitting_id
        payload["name"] = self._require_text(payload.get("name"), "name")
        bundle_name = "" if payload.get("bundle_name") is None else str(payload.get("bundle_name")).strip()
        bundle_key = "" if payload.get("bundle_key") is None else str(payload.get("bundle_key")).strip()
        if bundle_name and not bundle_key:
            bundle_key = uuid4().hex
        payload["bundle_name"] = bundle_name or None
        payload["bundle_key"] = bundle_key or None
        payload["bundle_order_index"] = self._require_int(
            payload.get("bundle_order_index", 0),
            "bundle_order_index",
        )
        payload["template_type"] = self._text_or_default(
            payload.get("template_type"),
            "manual",
        )
        payload["coordinate_system"] = self._text_or_default(
            payload.get("coordinate_system"),
            "2d",
        )
        payload["mounting_variant_key"] = self._normalize_mounting_variant_key(
            payload.get("mounting_variant_key"),
        )
        payload["is_active"] = self._normalize_bool(
            payload.get("is_active"),
            True,
        )
        payload.setdefault("is_default", False)

        return self.repository.create_template(**payload)

    def create_bundle(
        self,
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ):
        payload = self._merge_payload(data, **kwargs)

        bundle_name = self._require_text(
            payload.get("bundle_name"),
            "bundle_name",
        )
        category_key = self._text_or_default(
            payload.get("category_key") or payload.get("category"),
            "",
        )
        bundle_key = self._text_or_default(
            payload.get("bundle_key"),
            "",
        ) or uuid4().hex
        mounting_variant_key = self._normalize_mounting_variant_key(
            payload.get("mounting_variant_key"),
        )

        fitting_ids_raw = payload.get("fitting_ids") or []
        if not isinstance(fitting_ids_raw, (list, tuple, set)):
            raise ValueError("fitting_ids must be a list")

        fitting_ids: list[int] = []
        seen_fitting_ids: set[int] = set()
        fittings: list[FittingModel] = []

        for item in fitting_ids_raw:
            fitting_id = self._require_int(item, "fitting_id")
            if fitting_id in seen_fitting_ids:
                continue

            fitting = self._ensure_fitting_exists(fitting_id)
            fitting_category = self._text_or_default(
                getattr(fitting, "fitting_type", None)
                or getattr(fitting, "fitting_group", None)
                or "",
                "",
            )
            if category_key and fitting_category and fitting_category != category_key:
                raise ValueError(
                    f"Fitting with id={fitting_id} does not belong to category={category_key}"
                )

            seen_fitting_ids.add(fitting_id)
            fitting_ids.append(fitting_id)
            fittings.append(fitting)

        if not fitting_ids:
            raise ValueError("fitting_ids is required")

        templates_payload: list[dict[str, Any]] = []
        for index, fitting in enumerate(fittings):
            template_name = self._text_or_default(
                getattr(fitting, "name", None)
                or getattr(fitting, "article", None)
                or getattr(fitting, "code", None)
                or bundle_name,
                bundle_name,
            )
            templates_payload.append(
                {
                    "fitting_id": fitting.id,
                    "name": template_name,
                    "bundle_key": bundle_key,
                    "bundle_name": bundle_name,
                    "bundle_order_index": index,
                    "template_type": "bundle",
                    "coordinate_system": "2d",
                    "mounting_variant_key": mounting_variant_key,
                    "is_default": False,
                    "is_active": True,
                }
            )

        created_templates = self.repository.create_templates(templates_payload)
        category_code = ""
        if fittings:
            category_code = self._text_or_default(
                getattr(fittings[0], "fitting_type", None)
                or getattr(fittings[0], "fitting_group", None)
                or category_key,
                "",
            )

        return {
            "bundle_key": bundle_key,
            "bundle_name": bundle_name,
            "category_code": category_code or None,
            "templates": created_templates,
        }

    def get_template(self, template_id: int):
        template_id = self._require_int(template_id, "template_id")
        return self.repository.get_template_by_id(template_id)

    def list_templates_for_fitting(self, fitting_id: int):
        fitting_id = self._require_int(fitting_id, "fitting_id")
        return self.repository.list_templates_by_fitting(fitting_id)

    def list_templates_for_bundle(self, bundle_key: str):
        bundle_key = self._require_text(bundle_key, "bundle_key")
        return self.repository.list_templates_by_bundle_key(bundle_key)

    def list_bundles(self):
        return self.repository.list_bundles()

    def update_bundle_mounting_variant(
        self,
        bundle_key: str,
        mounting_variant_key: Any,
    ):
        bundle_key = self._require_text(bundle_key, "bundle_key")
        normalized_mounting_variant_key = self._normalize_mounting_variant_key(
            mounting_variant_key,
        )

        templates = self.repository.update_templates_by_bundle_key(
            bundle_key,
            mounting_variant_key=normalized_mounting_variant_key,
        )

        if not templates:
            raise ValueError(f"Bundle with key={bundle_key} does not exist")

        first_template = templates[0]
        category_code = self._text_or_default(
            getattr(first_template.fitting, "fitting_type", None)
            or getattr(first_template.fitting, "fitting_group", None)
            or "",
            "",
        )

        return {
            "bundle_key": bundle_key,
            "bundle_name": first_template.bundle_name,
            "category_code": category_code or None,
            "mounting_variant_key": normalized_mounting_variant_key,
            "templates": templates,
        }

    def update_template(
        self,
        template_id: int,
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ):
        template_id = self._require_int(template_id, "template_id")
        self._ensure_template_exists(template_id)

        payload = self._merge_payload(data, **kwargs)

        if "fitting_id" in payload:
            fitting_id = self._require_int(payload.get("fitting_id"), "fitting_id")
            self._ensure_fitting_exists(fitting_id)
            payload["fitting_id"] = fitting_id

        if "name" in payload:
            payload["name"] = self._require_text(payload.get("name"), "name")

        if "bundle_name" in payload:
            bundle_name = "" if payload.get("bundle_name") is None else str(payload.get("bundle_name")).strip()
            payload["bundle_name"] = bundle_name or None

        if "bundle_key" in payload:
            bundle_key = "" if payload.get("bundle_key") is None else str(payload.get("bundle_key")).strip()
            payload["bundle_key"] = bundle_key or None

        if "bundle_order_index" in payload:
            payload["bundle_order_index"] = self._require_int(
                payload.get("bundle_order_index"),
                "bundle_order_index",
            )

        if "template_type" in payload and payload.get("template_type") is not None:
            payload["template_type"] = self._require_text(
                payload.get("template_type"),
                "template_type",
            )

        if "coordinate_system" in payload and payload.get("coordinate_system") is not None:
            payload["coordinate_system"] = self._require_text(
                payload.get("coordinate_system"),
                "coordinate_system",
            )

        if "mounting_variant_key" in payload:
            payload["mounting_variant_key"] = self._normalize_mounting_variant_key(
                payload.get("mounting_variant_key"),
            )

        if "is_active" in payload:
            payload["is_active"] = self._normalize_bool(
                payload.get("is_active"),
                True,
            )

        if "is_default" in payload:
            payload["is_default"] = self._normalize_bool(
                payload.get("is_default"),
                False,
            )

        return self.repository.update_template(template_id, **payload)

    def deactivate_template(self, template_id: int):
        template_id = self._require_int(template_id, "template_id")
        self._ensure_template_exists(template_id)
        return self.repository.deactivate_template(template_id)

    # -------------------------
    # Hole points
    # -------------------------
    def add_hole_point(
        self,
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ):
        payload = self._merge_payload(data, **kwargs)

        template_id = self._require_int(payload.get("template_id"), "template_id")
        self._ensure_template_exists(template_id)
        payload["template_id"] = template_id

        payload["diameter_mm"] = self._require_positive_float(
            payload.get("diameter_mm"),
            "diameter_mm",
        )
        payload["depth_mm"] = self._optional_non_negative_float(
            payload.get("depth_mm"),
            "depth_mm",
        )

        quantity_value = payload.get("quantity", 1)
        if quantity_value is None:
            quantity_value = 1
        quantity = self._require_int(quantity_value, "quantity")
        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")
        payload["quantity"] = quantity

        payload["operation"] = self._text_or_default(
            payload.get("operation"),
            "drill",
        )
        payload["order_index"] = self._require_int(
            payload.get("order_index", 0),
            "order_index",
        )

        return self.repository.create_hole_point(**payload)

    def update_hole_point(
        self,
        hole_point_id: int,
        data: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ):
        hole_point_id = self._require_int(hole_point_id, "hole_point_id")
        existing = self.repository.get_hole_point_by_id(hole_point_id)
        if existing is None:
            raise ValueError(f"Hole point with id={hole_point_id} does not exist")

        payload = self._merge_payload(data, **kwargs)

        if "template_id" in payload:
            template_id = self._require_int(payload.get("template_id"), "template_id")
            self._ensure_template_exists(template_id)
            payload["template_id"] = template_id

        if "diameter_mm" in payload:
            payload["diameter_mm"] = self._require_positive_float(
                payload.get("diameter_mm"),
                "diameter_mm",
            )

        if "depth_mm" in payload:
            payload["depth_mm"] = self._optional_non_negative_float(
                payload.get("depth_mm"),
                "depth_mm",
            )

        if "quantity" in payload:
            quantity = self._require_int(payload.get("quantity"), "quantity")
            if quantity <= 0:
                raise ValueError("quantity must be greater than 0")
            payload["quantity"] = quantity

        if "operation" in payload and payload.get("operation") is not None:
            payload["operation"] = self._require_text(payload.get("operation"), "operation")

        if "order_index" in payload:
            payload["order_index"] = self._require_int(
                payload.get("order_index"),
                "order_index",
            )

        return self.repository.update_hole_point(hole_point_id, **payload)

    def list_hole_points(self, template_id: int):
        template_id = self._require_int(template_id, "template_id")
        return self.repository.list_hole_points_by_template(template_id)

    def delete_hole_point(self, hole_point_id: int):
        hole_point_id = self._require_int(hole_point_id, "hole_point_id")
        existing = self.repository.get_hole_point_by_id(hole_point_id)
        if existing is None:
            raise ValueError(f"Hole point with id={hole_point_id} does not exist")
        return self.repository.delete_hole_point(hole_point_id)


__all__ = ["FittingHolesService"]
