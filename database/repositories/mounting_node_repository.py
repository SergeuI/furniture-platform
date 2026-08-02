from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from database.models.fitting import FittingHolePointModel, FittingHoleTemplateModel, FittingModel
from database.models.mounting_node import (
    MountingNodeItemModel,
    MountingNodeModel,
    MountingNodeTemplateModel,
)


class MountingNodeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _node_query(self):
        return (
            self.session.query(MountingNodeModel)
            .options(selectinload(MountingNodeModel.items).selectinload(MountingNodeItemModel.fitting))
            .options(
                selectinload(MountingNodeModel.templates)
                .selectinload(MountingNodeTemplateModel.template)
                .selectinload(FittingHoleTemplateModel.fitting)
            )
            .options(
                selectinload(MountingNodeModel.templates)
                .selectinload(MountingNodeTemplateModel.template)
                .selectinload(FittingHoleTemplateModel.points)
            )
        )

    def get_node_by_id(self, node_id: int) -> Optional[MountingNodeModel]:
        return (
            self._node_query()
            .filter(MountingNodeModel.id == node_id)
            .one_or_none()
        )

    def get_node_by_code(self, code: str, exclude_node_id: int | None = None) -> Optional[MountingNodeModel]:
        query = self._node_query().filter(MountingNodeModel.code == code)
        if exclude_node_id is not None:
            query = query.filter(MountingNodeModel.id != exclude_node_id)
        return query.one_or_none()

    def list_nodes(
        self,
        include_inactive: bool = False,
        fitting_id: int | None = None,
        mounting_variant_key: str | None = None,
        viewer_user_id: str | None = None,
        viewer_role: str | None = None,
    ) -> list[MountingNodeModel]:
        query = self._node_query()

        if not include_inactive:
            query = query.filter(MountingNodeModel.is_active.is_(True))

        is_admin = str(viewer_role or "").strip().lower() == "admin"
        normalized_viewer_id = str(viewer_user_id or "").strip()
        if not is_admin:
            if normalized_viewer_id:
                query = query.filter(
                    or_(
                        MountingNodeModel.owner_user_id.is_(None),
                        MountingNodeModel.owner_user_id == normalized_viewer_id,
                    ),
                )
            else:
                query = query.filter(MountingNodeModel.owner_user_id.is_(None))

        if fitting_id is not None:
            query = query.filter(
                MountingNodeModel.items.any(
                    MountingNodeItemModel.fitting_id == fitting_id,
                ),
            )

        if mounting_variant_key:
            query = query.filter(
                MountingNodeModel.templates.any(
                    MountingNodeTemplateModel.template.has(
                        FittingHoleTemplateModel.mounting_variant_key == mounting_variant_key,
                    ),
                ),
            )

        return query.order_by(
            MountingNodeModel.name.asc(),
            MountingNodeModel.code.asc(),
            MountingNodeModel.id.asc(),
        ).all()

    def create_node(self, **data: Any) -> MountingNodeModel:
        node = MountingNodeModel(**data)
        self.session.add(node)
        self.session.flush()
        self.session.refresh(node)
        return node

    def update_node(self, node: MountingNodeModel, **data: Any) -> MountingNodeModel:
        for key, value in data.items():
            setattr(node, key, value)
        self.session.flush()
        self.session.refresh(node)
        return node

    def replace_items(
        self,
        node: MountingNodeModel,
        items: list[dict[str, Any]],
    ) -> list[MountingNodeItemModel]:
        node.items.clear()
        self.session.flush()

        created_items = [
            MountingNodeItemModel(
                node=node,
                **item,
            )
            for item in items
        ]
        self.session.add_all(created_items)
        self.session.flush()
        return created_items

    def replace_templates(
        self,
        node: MountingNodeModel,
        templates: list[dict[str, Any]],
    ) -> list[MountingNodeTemplateModel]:
        node.templates.clear()
        self.session.flush()

        created_templates = [
            MountingNodeTemplateModel(
                node=node,
                **template,
            )
            for template in templates
        ]
        self.session.add_all(created_templates)
        self.session.flush()
        return created_templates

    def get_template_by_id(self, template_id: int) -> Optional[FittingHoleTemplateModel]:
        return (
            self.session.query(FittingHoleTemplateModel)
            .options(selectinload(FittingHoleTemplateModel.fitting))
            .options(selectinload(FittingHoleTemplateModel.points))
            .filter(FittingHoleTemplateModel.id == template_id)
            .one_or_none()
        )

    def get_fitting_by_id(self, fitting_id: int) -> Optional[FittingModel]:
        return self.session.get(FittingModel, fitting_id)

    def count_template_links(self, template_id: int) -> int:
        return (
            self.session.query(MountingNodeTemplateModel)
            .filter(MountingNodeTemplateModel.template_id == template_id)
            .count()
        )

    def template_link_owner_node_id(self, template_id: int) -> int | None:
        row = (
            self.session.query(MountingNodeTemplateModel.node_id)
            .filter(MountingNodeTemplateModel.template_id == template_id)
            .one_or_none()
        )
        if row is None:
            return None
        return int(row[0])


__all__ = ["MountingNodeRepository"]
