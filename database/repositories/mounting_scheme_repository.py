from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session, selectinload

from database.models.mounting_node import MountingNodeModel
from database.models.mounting_scheme import (
    MountingSchemeModel,
    MountingSchemeNodeModel,
    MountingSchemePlacementRuleModel,
)


class MountingSchemeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _scheme_query(self):
        return (
            self.session.query(MountingSchemeModel)
            .options(selectinload(MountingSchemeModel.nodes).selectinload(MountingSchemeNodeModel.node))
            .options(selectinload(MountingSchemeModel.placement_rules))
        )

    def list_schemes(self, include_inactive: bool = False) -> list[MountingSchemeModel]:
        query = self._scheme_query()
        if not include_inactive:
            query = query.filter(MountingSchemeModel.is_active.is_(True))
        return query.order_by(
            MountingSchemeModel.name.asc(),
            MountingSchemeModel.code.asc(),
            MountingSchemeModel.id.asc(),
        ).all()

    def get_scheme_by_id(self, scheme_id: int) -> Optional[MountingSchemeModel]:
        return self._scheme_query().filter(MountingSchemeModel.id == scheme_id).one_or_none()

    def get_scheme_by_code(self, code: str, exclude_scheme_id: int | None = None) -> Optional[MountingSchemeModel]:
        query = self._scheme_query().filter(MountingSchemeModel.code == code)
        if exclude_scheme_id is not None:
            query = query.filter(MountingSchemeModel.id != exclude_scheme_id)
        return query.one_or_none()

    def create_scheme(self, **data: Any) -> MountingSchemeModel:
        scheme = MountingSchemeModel(**data)
        self.session.add(scheme)
        self.session.flush()
        self.session.refresh(scheme)
        return scheme

    def update_scheme(self, scheme: MountingSchemeModel, **data: Any) -> MountingSchemeModel:
        for key, value in data.items():
            setattr(scheme, key, value)
        self.session.flush()
        self.session.refresh(scheme)
        return scheme

    def replace_nodes(self, scheme: MountingSchemeModel, nodes: list[dict[str, Any]]) -> list[MountingSchemeNodeModel]:
        scheme.nodes.clear()
        self.session.flush()

        created_nodes = [
            MountingSchemeNodeModel(
                scheme=scheme,
                **node,
            )
            for node in nodes
        ]
        self.session.add_all(created_nodes)
        self.session.flush()
        return created_nodes

    def replace_placement_rules(
        self,
        scheme: MountingSchemeModel,
        placement_rules: list[dict[str, Any]],
    ) -> list[MountingSchemePlacementRuleModel]:
        scheme.placement_rules.clear()
        self.session.flush()

        created_rules = [
            MountingSchemePlacementRuleModel(
                scheme=scheme,
                **placement_rule,
            )
            for placement_rule in placement_rules
        ]
        self.session.add_all(created_rules)
        self.session.flush()
        return created_rules

    def get_mounting_node_by_id(self, node_id: int) -> Optional[MountingNodeModel]:
        return self.session.get(MountingNodeModel, node_id)


__all__ = ["MountingSchemeRepository"]
