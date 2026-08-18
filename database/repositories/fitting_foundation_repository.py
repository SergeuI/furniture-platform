from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.fitting import FittingSupplierOfferModel, SupplierModel


class FittingFoundationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_supplier_by_code(self, code: str) -> SupplierModel | None:
        normalized_code = str(code or "").strip()
        if not normalized_code:
            return None
        return (
            self.session.query(SupplierModel)
            .filter(SupplierModel.code == normalized_code)
            .one_or_none()
        )

    def list_suppliers(
        self,
        include_inactive: bool = True,
        current_user_id: str | None = None,
    ) -> list[SupplierModel]:
        query = self.session.query(SupplierModel)
        if not include_inactive:
            query = query.filter(SupplierModel.is_active.is_(True))
        normalized_current_user_id = str(current_user_id or "").strip() or None
        if normalized_current_user_id:
            query = query.filter(
                (
                    SupplierModel.is_system.is_(True)
                )
                | (
                    SupplierModel.owner_user_id == normalized_current_user_id
                )
            )
        else:
            query = query.filter(SupplierModel.is_system.is_(True))
        return query.order_by(
            SupplierModel.name.asc(),
            SupplierModel.code.asc(),
            SupplierModel.id.asc(),
        ).all()

    def create_supplier(self, **data: Any) -> SupplierModel | None:
        supplier = SupplierModel(**data)
        self.session.add(supplier)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            return None
        self.session.refresh(supplier)
        return supplier

    def upsert_supplier(self, code: str, **data: Any) -> SupplierModel:
        normalized_code = str(code or "").strip()
        if not normalized_code:
            raise ValueError("code is required")

        supplier = self.get_supplier_by_code(normalized_code)
        if supplier is None:
            supplier = SupplierModel(code=normalized_code, **data)
            self.session.add(supplier)
        else:
            for key, value in data.items():
                setattr(supplier, key, value)

        self.session.flush()
        self.session.refresh(supplier)
        return supplier

    def get_offer_by_id(self, offer_id: int) -> FittingSupplierOfferModel | None:
        return self.session.get(FittingSupplierOfferModel, offer_id)

    def list_offers_by_fitting(
        self,
        fitting_id: int,
        include_inactive: bool = True,
    ) -> list[FittingSupplierOfferModel]:
        query = (
            self.session.query(FittingSupplierOfferModel)
            .filter(FittingSupplierOfferModel.fitting_id == fitting_id)
        )
        if not include_inactive:
            query = query.filter(FittingSupplierOfferModel.is_active.is_(True))
        return query.order_by(
            FittingSupplierOfferModel.priority.asc(),
            FittingSupplierOfferModel.id.asc(),
        ).all()

    def list_offers_by_supplier(
        self,
        supplier_id: int,
        include_inactive: bool = True,
    ) -> list[FittingSupplierOfferModel]:
        query = (
            self.session.query(FittingSupplierOfferModel)
            .filter(FittingSupplierOfferModel.supplier_id == supplier_id)
        )
        if not include_inactive:
            query = query.filter(FittingSupplierOfferModel.is_active.is_(True))
        return query.order_by(
            FittingSupplierOfferModel.priority.asc(),
            FittingSupplierOfferModel.id.asc(),
        ).all()

    def create_offer(self, **data: Any) -> FittingSupplierOfferModel | None:
        offer = FittingSupplierOfferModel(**data)
        self.session.add(offer)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            return None
        self.session.refresh(offer)
        return offer

    def update_offer(self, offer: FittingSupplierOfferModel, **data: Any) -> FittingSupplierOfferModel:
        for key, value in data.items():
            setattr(offer, key, value)
        self.session.flush()
        self.session.refresh(offer)
        return offer
