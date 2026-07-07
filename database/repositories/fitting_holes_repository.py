from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func

from sqlalchemy.orm import Session, selectinload

from database.models.fitting import (
    FittingHolePointModel,
    FittingHoleTemplateModel,
    FittingModel,
)


class FittingHolesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _commit(self) -> None:
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    # -------------------------
    # Templates
    # -------------------------
    def create_template(self, **data: Any) -> FittingHoleTemplateModel:
        template = FittingHoleTemplateModel(**data)
        self.session.add(template)
        self._commit()
        self.session.refresh(template)
        return template

    def create_templates(
        self,
        templates: list[dict[str, Any]],
    ) -> list[FittingHoleTemplateModel]:
        created_templates = [
            FittingHoleTemplateModel(**template_data)
            for template_data in templates
        ]
        self.session.add_all(created_templates)
        self._commit()
        for template in created_templates:
            self.session.refresh(template)
        return created_templates

    def get_template_by_id(
        self,
        template_id: int,
    ) -> Optional[FittingHoleTemplateModel]:
        return (
            self.session.query(FittingHoleTemplateModel)
            .options(selectinload(FittingHoleTemplateModel.fitting))
            .filter(FittingHoleTemplateModel.id == template_id)
            .one_or_none()
        )

    def list_templates_by_fitting(
        self,
        fitting_id: int,
    ) -> list[FittingHoleTemplateModel]:
        return (
            self.session.query(FittingHoleTemplateModel)
            .options(selectinload(FittingHoleTemplateModel.fitting))
            .filter(FittingHoleTemplateModel.fitting_id == fitting_id)
            .order_by(
                FittingHoleTemplateModel.is_default.desc(),
                FittingHoleTemplateModel.is_active.desc(),
                FittingHoleTemplateModel.bundle_order_index.asc(),
                FittingHoleTemplateModel.id.asc(),
            )
            .all()
        )

    def list_templates_by_bundle_key(
        self,
        bundle_key: str,
    ) -> list[FittingHoleTemplateModel]:
        return (
            self.session.query(FittingHoleTemplateModel)
            .options(selectinload(FittingHoleTemplateModel.fitting))
            .filter(FittingHoleTemplateModel.bundle_key == bundle_key)
            .order_by(
                FittingHoleTemplateModel.bundle_order_index.asc(),
                FittingHoleTemplateModel.fitting_id.asc(),
                FittingHoleTemplateModel.id.asc(),
            )
            .all()
        )

    def list_bundles(
        self,
    ) -> list[tuple[str, str | None, str | None, int, Any, Any]]:
        return (
            self.session.query(
                func.coalesce(
                    FittingHoleTemplateModel.bundle_key,
                    FittingHoleTemplateModel.bundle_name,
                ),
                FittingHoleTemplateModel.bundle_name,
                func.coalesce(
                    FittingModel.fitting_type,
                    FittingModel.fitting_group,
                ),
                func.count(FittingHoleTemplateModel.id),
                func.max(FittingHoleTemplateModel.created_at),
                func.max(FittingHoleTemplateModel.updated_at),
            )
            .outerjoin(FittingModel, FittingModel.id == FittingHoleTemplateModel.fitting_id)
            .filter(
                (FittingHoleTemplateModel.bundle_key.isnot(None))
                | (FittingHoleTemplateModel.bundle_name.isnot(None))
            )
            .filter(
                (FittingHoleTemplateModel.bundle_key != "")
                | (FittingHoleTemplateModel.bundle_name != "")
            )
            .group_by(
                func.coalesce(
                    FittingHoleTemplateModel.bundle_key,
                    FittingHoleTemplateModel.bundle_name,
                ),
                FittingHoleTemplateModel.bundle_name,
                func.coalesce(
                    FittingModel.fitting_type,
                    FittingModel.fitting_group,
                ),
            )
            .order_by(
                FittingHoleTemplateModel.bundle_name.asc(),
                FittingHoleTemplateModel.bundle_key.asc(),
            )
            .all()
        )

    def update_template(
        self,
        template_id: int,
        **data: Any,
    ) -> Optional[FittingHoleTemplateModel]:
        template = self.get_template_by_id(template_id)
        if template is None:
            return None

        for key, value in data.items():
            setattr(template, key, value)

        self._commit()
        self.session.refresh(template)
        return template

    def update_templates_by_bundle_key(
        self,
        bundle_key: str,
        **data: Any,
    ) -> list[FittingHoleTemplateModel]:
        templates = self.list_templates_by_bundle_key(bundle_key)
        if not templates:
            return []

        for template in templates:
            for key, value in data.items():
                setattr(template, key, value)

        self._commit()

        for template in templates:
            self.session.refresh(template)

        return templates

    def delete_templates_by_bundle_key(self, bundle_key: str) -> int:
        templates = self.list_templates_by_bundle_key(bundle_key)
        if not templates:
            return 0

        for template in templates:
            self.session.delete(template)

        self._commit()
        return len(templates)

    def deactivate_template(
        self,
        template_id: int,
    ) -> Optional[FittingHoleTemplateModel]:
        return self.update_template(template_id, is_active=False)

    # -------------------------
    # Hole points
    # -------------------------
    def create_hole_point(self, **data: Any) -> FittingHolePointModel:
        hole_point = FittingHolePointModel(**data)
        self.session.add(hole_point)
        self._commit()
        self.session.refresh(hole_point)
        return hole_point

    def get_hole_point_by_id(
        self,
        hole_point_id: int,
    ) -> Optional[FittingHolePointModel]:
        return self.session.get(FittingHolePointModel, hole_point_id)

    def list_hole_points_by_template(
        self,
        template_id: int,
    ) -> list[FittingHolePointModel]:
        return (
            self.session.query(FittingHolePointModel)
            .filter(FittingHolePointModel.template_id == template_id)
            .order_by(
                FittingHolePointModel.order_index.asc(),
                FittingHolePointModel.id.asc(),
            )
            .all()
        )

    def update_hole_point(
        self,
        hole_point_id: int,
        **data: Any,
    ) -> Optional[FittingHolePointModel]:
        hole_point = self.get_hole_point_by_id(hole_point_id)
        if hole_point is None:
            return None

        for key, value in data.items():
            setattr(hole_point, key, value)

        self._commit()
        self.session.refresh(hole_point)
        return hole_point

    def delete_hole_point(self, hole_point_id: int) -> bool:
        hole_point = self.get_hole_point_by_id(hole_point_id)
        if hole_point is None:
            return False

        self.session.delete(hole_point)
        self._commit()
        return True


__all__ = ["FittingHolesRepository"]
