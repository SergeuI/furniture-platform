from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.canonical_edge import (
    CanonicalEdgeModel,
    EdgeSupplierOfferModel,
    EdgeSupplierOfferPriceModel,
    MaterialEdgeRelationModel,
)
from database.models.material_taxonomy import MaterialManufacturerModel
from sqlalchemy import func, text


def _normalize_lookup_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip().casefold()


class EdgeFoundationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_manufacturer_by_name(self, manufacturer_name: str | None) -> MaterialManufacturerModel | None:
        normalized_name = _normalize_lookup_text(manufacturer_name)
        if not normalized_name:
            return None
        return (
            self.session.query(MaterialManufacturerModel)
            .filter(func.lower(MaterialManufacturerModel.normalized_name) == normalized_name)
            .one_or_none()
        )

    def get_supplier_id_by_code(self, supplier_code: str | None) -> int | None:
        normalized_code = _normalize_lookup_text(supplier_code)
        if not normalized_code:
            return None
        row = self.session.execute(
            text("SELECT id FROM suppliers WHERE lower(code) = :code"),
            {"code": normalized_code},
        ).fetchone()
        return int(row[0]) if row else None

    def get_edge_by_id(self, edge_id: int) -> CanonicalEdgeModel | None:
        return self.session.get(CanonicalEdgeModel, edge_id)

    def get_edge_by_identity(
        self,
        *,
        manufacturer_id: int,
        manufacturer_article: str,
        material_type: str,
        width_mm: float,
        thickness_mm: float,
    ) -> CanonicalEdgeModel | None:
        return (
            self.session.query(CanonicalEdgeModel)
            .filter(CanonicalEdgeModel.manufacturer_id == int(manufacturer_id))
            .filter(CanonicalEdgeModel.manufacturer_article == str(manufacturer_article))
            .filter(CanonicalEdgeModel.material_type == str(material_type))
            .filter(CanonicalEdgeModel.width_mm == float(width_mm))
            .filter(CanonicalEdgeModel.thickness_mm == float(thickness_mm))
            .one_or_none()
        )

    def list_edges(
        self,
        include_inactive: bool = True,
        manufacturer_id: int | None = None,
    ) -> list[CanonicalEdgeModel]:
        query = self.session.query(CanonicalEdgeModel)
        if not include_inactive:
            query = query.filter(CanonicalEdgeModel.is_active.is_(True))
        if manufacturer_id is not None:
            query = query.filter(CanonicalEdgeModel.manufacturer_id == manufacturer_id)
        return query.order_by(
            CanonicalEdgeModel.name.asc(),
            CanonicalEdgeModel.id.asc(),
        ).all()

    def create_edge(self, **data: Any) -> CanonicalEdgeModel | None:
        edge = CanonicalEdgeModel(**data)
        nested = self.session.begin_nested()
        try:
            self.session.add(edge)
            self.session.flush()
        except IntegrityError:
            nested.rollback()
            return None
        else:
            nested.commit()
        self.session.refresh(edge)
        return edge

    def update_edge(self, edge: CanonicalEdgeModel, **data: Any) -> CanonicalEdgeModel:
        for key, value in data.items():
            setattr(edge, key, value)
        self.session.flush()
        self.session.refresh(edge)
        return edge

    def upsert_edge(self, *, identity: dict[str, Any], data: dict[str, Any]) -> tuple[CanonicalEdgeModel, bool]:
        edge = self.get_edge_by_identity(**identity)
        created = False
        if edge is None:
            edge = CanonicalEdgeModel(**identity, **data)
            self.session.add(edge)
            self.session.flush()
            created = True
            self.session.refresh(edge)
            return edge, created

        update_data: dict[str, Any] = {}
        for key, value in data.items():
            if key == "is_active":
                if bool(value) and not bool(getattr(edge, key)):
                    update_data[key] = True
                continue
            if value is None:
                continue
            current = getattr(edge, key)
            if current in (None, ""):
                update_data[key] = value

        if update_data:
            self.update_edge(edge, **update_data)
        else:
            self.session.flush()
            self.session.refresh(edge)
        return edge, created

    def get_relation_by_id(self, relation_id: int) -> MaterialEdgeRelationModel | None:
        return self.session.get(MaterialEdgeRelationModel, relation_id)

    def get_relation_by_identity(
        self,
        *,
        material_id: int,
        edge_id: int,
        relation_type: str,
        source_supplier_id: int | None = None,
    ) -> MaterialEdgeRelationModel | None:
        query = (
            self.session.query(MaterialEdgeRelationModel)
            .filter(MaterialEdgeRelationModel.material_id == material_id)
            .filter(MaterialEdgeRelationModel.edge_id == edge_id)
            .filter(MaterialEdgeRelationModel.relation_type == relation_type)
        )
        if source_supplier_id is None:
            query = query.filter(MaterialEdgeRelationModel.source_supplier_id.is_(None))
        else:
            query = query.filter(MaterialEdgeRelationModel.source_supplier_id == source_supplier_id)
        return query.one_or_none()

    def list_relations_by_material(
        self,
        material_id: int,
    ) -> list[MaterialEdgeRelationModel]:
        return (
            self.session.query(MaterialEdgeRelationModel)
            .filter(MaterialEdgeRelationModel.material_id == material_id)
            .order_by(
                MaterialEdgeRelationModel.relation_type.asc(),
                MaterialEdgeRelationModel.id.asc(),
            )
            .all()
        )

    def list_materials_by_edge(
        self,
        edge_id: int,
    ) -> list[MaterialEdgeRelationModel]:
        return (
            self.session.query(MaterialEdgeRelationModel)
            .filter(MaterialEdgeRelationModel.edge_id == edge_id)
            .order_by(
                MaterialEdgeRelationModel.material_id.asc(),
                MaterialEdgeRelationModel.id.asc(),
            )
            .all()
        )

    def create_relation(self, **data: Any) -> MaterialEdgeRelationModel | None:
        existing = self.get_relation_by_identity(
            material_id=int(data["material_id"]),
            edge_id=int(data["edge_id"]),
            relation_type=str(data.get("relation_type") or "recommended"),
            source_supplier_id=(
                int(data["source_supplier_id"])
                if data.get("source_supplier_id") is not None
                else None
            ),
        )
        if existing is not None:
            return None

        relation = MaterialEdgeRelationModel(**data)
        nested = self.session.begin_nested()
        try:
            self.session.add(relation)
            self.session.flush()
        except IntegrityError:
            nested.rollback()
            return None
        else:
            nested.commit()
        self.session.refresh(relation)
        return relation

    def get_offer_by_id(self, offer_id: int) -> EdgeSupplierOfferModel | None:
        return self.session.get(EdgeSupplierOfferModel, offer_id)

    def get_offer_by_identity(
        self,
        *,
        edge_id: int,
        supplier_id: int,
        external_product_id: str | None = None,
    ) -> EdgeSupplierOfferModel | None:
        query = (
            self.session.query(EdgeSupplierOfferModel)
            .filter(EdgeSupplierOfferModel.edge_id == edge_id)
            .filter(EdgeSupplierOfferModel.supplier_id == supplier_id)
        )
        if external_product_id is None:
            query = query.filter(EdgeSupplierOfferModel.external_product_id.is_(None))
        else:
            query = query.filter(EdgeSupplierOfferModel.external_product_id == external_product_id)
        return query.one_or_none()

    def list_offers_by_edge(
        self,
        edge_id: int,
        include_inactive: bool = True,
    ) -> list[EdgeSupplierOfferModel]:
        query = (
            self.session.query(EdgeSupplierOfferModel)
            .filter(EdgeSupplierOfferModel.edge_id == edge_id)
        )
        if not include_inactive:
            query = query.filter(EdgeSupplierOfferModel.is_active.is_(True))
        return query.order_by(
            EdgeSupplierOfferModel.priority.asc(),
            EdgeSupplierOfferModel.id.asc(),
        ).all()

    def create_offer(self, **data: Any) -> EdgeSupplierOfferModel | None:
        offer = EdgeSupplierOfferModel(**data)
        nested = self.session.begin_nested()
        try:
            self.session.add(offer)
            self.session.flush()
        except IntegrityError:
            nested.rollback()
            return None
        else:
            nested.commit()
        self.session.refresh(offer)
        return offer

    def upsert_offer(self, *, edge_id: int, supplier_id: int, **data: Any) -> EdgeSupplierOfferModel:
        external_product_id = data.get("external_product_id")
        offer = self.get_offer_by_identity(
            edge_id=edge_id,
            supplier_id=supplier_id,
            external_product_id=external_product_id,
        )
        if offer is None:
            offer = EdgeSupplierOfferModel(
                edge_id=edge_id,
                supplier_id=supplier_id,
                **data,
            )
            self.session.add(offer)
        else:
            for key, value in data.items():
                setattr(offer, key, value)
        self.session.flush()
        self.session.refresh(offer)
        return offer

    def list_offer_prices(self, offer_id: int) -> list[EdgeSupplierOfferPriceModel]:
        return (
            self.session.query(EdgeSupplierOfferPriceModel)
            .filter(EdgeSupplierOfferPriceModel.offer_id == offer_id)
            .order_by(
                EdgeSupplierOfferPriceModel.city.asc(),
                EdgeSupplierOfferPriceModel.id.asc(),
            )
            .all()
        )

    def get_offer_price_by_identity(
        self,
        *,
        offer_id: int,
        city: str,
    ) -> EdgeSupplierOfferPriceModel | None:
        normalized_city = str(city or "").strip()
        if not normalized_city:
            return None
        return (
            self.session.query(EdgeSupplierOfferPriceModel)
            .filter(EdgeSupplierOfferPriceModel.offer_id == offer_id)
            .filter(EdgeSupplierOfferPriceModel.city == normalized_city)
            .one_or_none()
        )

    def upsert_offer_price(
        self,
        *,
        offer_id: int,
        city: str,
        price: float | None = None,
        currency: str | None = None,
        availability: str | None = None,
        checked_at=None,
    ) -> EdgeSupplierOfferPriceModel:
        normalized_city = str(city or "").strip()
        if not normalized_city:
            raise ValueError("city is required")

        row = (
            self.session.query(EdgeSupplierOfferPriceModel)
            .filter(EdgeSupplierOfferPriceModel.offer_id == offer_id)
            .filter(EdgeSupplierOfferPriceModel.city == normalized_city)
            .one_or_none()
        )

        if row is None:
            row = EdgeSupplierOfferPriceModel(
                offer_id=offer_id,
                city=normalized_city,
                price=price,
                currency=currency,
                availability=availability,
                checked_at=checked_at,
            )
            self.session.add(row)
        else:
            row.price = price
            row.currency = currency
            row.availability = availability
            row.checked_at = checked_at

        self.session.flush()
        self.session.refresh(row)
        return row
