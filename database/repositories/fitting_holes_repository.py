from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

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

    def get_template_by_id(
        self,
        template_id: int,
    ) -> Optional[FittingHoleTemplateModel]:
        return self.session.get(FittingHoleTemplateModel, template_id)

    def list_templates_by_fitting(
        self,
        fitting_id: int,
    ) -> list[FittingHoleTemplateModel]:
        return (
            self.session.query(FittingHoleTemplateModel)
            .filter(FittingHoleTemplateModel.fitting_id == fitting_id)
            .order_by(
                FittingHoleTemplateModel.is_default.desc(),
                FittingHoleTemplateModel.is_active.desc(),
                FittingHoleTemplateModel.id.asc(),
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