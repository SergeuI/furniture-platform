from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import datetime
from typing import Any

from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

from database.repositories.edge_foundation_repository import EdgeFoundationRepository
from database.session import SessionLocal
from services.viyar_parser import preview_viyar_recommended_edges


class EdgeFoundationPersistenceService:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session or SessionLocal()
        self.repository = EdgeFoundationRepository(self.session)
        self._owns_session = session is None

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def resolve_manufacturer(self, manufacturer_name: str | None):
        return self.repository.get_manufacturer_by_name(manufacturer_name)

    def resolve_supplier_id(self, supplier_code: str | None) -> int | None:
        return self.repository.get_supplier_id_by_code(supplier_code)

    def persist_preview_result(
        self,
        *,
        material_id: int,
        preview_result: dict[str, Any],
        city: str | None = None,
        relation_source_url: str | None = None,
    ) -> dict[str, Any]:
        items = preview_result.get("items") or []
        results: list[dict[str, Any]] = []

        transaction = nullcontext() if self.session.in_transaction() else self.session.begin()
        with transaction:
            for preview_item in items:
                try:
                    with self.session.begin_nested():
                        results.append(
                            self.persist_preview_item(
                                material_id=material_id,
                                preview_item=preview_item,
                                city=city,
                                relation_source_url=relation_source_url,
                            )
                        )
                except Exception as exc:  # pragma: no cover - defensive fallback
                    results.append(
                        {
                            "status": "failed",
                            "reason": str(exc) or "persistence_failed",
                            "preview_item": preview_item,
                        }
                    )

        return {
            "success": True,
            "material_id": int(material_id),
            "city": city,
            "items": results,
            "counts": {
                "items": len(results),
                "persisted": sum(1 for item in results if item.get("status") == "persisted"),
                "reused": sum(1 for item in results if item.get("status") == "reused"),
                "needs_review": sum(1 for item in results if item.get("status") == "needs_review"),
                "failed": sum(1 for item in results if item.get("status") == "failed"),
            },
        }

    def persist_preview_item(
        self,
        *,
        material_id: int,
        preview_item: dict[str, Any],
        city: str | None = None,
        relation_source_url: str | None = None,
    ) -> dict[str, Any]:
        preview_status = str(preview_item.get("status") or "").strip().lower()
        if preview_status == "failed":
            return {
                "status": "failed",
                "reason": preview_item.get("error") or "preview_failed",
                "missing_fields": list(preview_item.get("missing_fields") or []),
                "preview_item": preview_item,
            }
        if preview_status == "needs_review":
            return {
                "status": "needs_review",
                "reason": preview_item.get("error") or preview_item.get("reason") or "needs_review",
                "missing_fields": list(preview_item.get("missing_fields") or []),
                "preview_item": preview_item,
            }

        canonical = preview_item.get("canonical_candidate") or {}
        supplier = preview_item.get("supplier_offer_candidate") or {}

        missing_identity_fields = self._missing_identity_fields(canonical)
        if missing_identity_fields:
            return {
                "status": "needs_review",
                "reason": "missing_identity_fields",
                "missing_fields": missing_identity_fields,
                "preview_item": preview_item,
            }

        manufacturer = self.resolve_manufacturer(canonical.get("manufacturer"))
        if manufacturer is None:
            return {
                "status": "needs_review",
                "reason": "manufacturer_not_found",
                "missing_fields": [],
                "preview_item": preview_item,
            }

        supplier_id = self.resolve_supplier_id(supplier.get("supplier"))
        if supplier_id is None:
            return {
                "status": "needs_review",
                "reason": "supplier_not_found",
                "missing_fields": [],
                "preview_item": preview_item,
            }

        identity = {
            "manufacturer_id": int(manufacturer.id),
            "manufacturer_article": str(canonical.get("manufacturer_article")),
            "material_type": str(canonical.get("material_type")),
            "width_mm": float(canonical.get("width_mm")),
            "thickness_mm": float(canonical.get("thickness_mm")),
        }
        edge_data = {
            "name": str(canonical.get("name")),
            "decor_code": canonical.get("decor_code"),
            "color": canonical.get("color"),
            "finish": canonical.get("finish"),
            "image_url": canonical.get("image_url"),
            "is_active": True,
        }
        edge, edge_created = self.repository.upsert_edge(identity=identity, data=edge_data)

        existing_offer = self.repository.get_offer_by_identity(
            edge_id=int(edge.id),
            supplier_id=int(supplier_id),
            external_product_id=None,
        )
        existing_price = (
            self.repository.get_offer_price_by_identity(
                offer_id=int(existing_offer.id),
                city=city,
            )
            if existing_offer is not None and city is not None
            else None
        )

        source_payload = self._build_source_payload(preview_item=preview_item)
        offer = self.repository.upsert_offer(
            edge_id=int(edge.id),
            supplier_id=int(supplier_id),
            article=supplier.get("article"),
            external_product_id=None,
            source_url=supplier.get("source_url"),
            unit=supplier.get("unit"),
            stock=supplier.get("availability"),
            is_active=True,
            priority=0,
            parsed_at=datetime.utcnow(),
            price_updated_at=datetime.utcnow() if supplier.get("price") is not None else None,
            source_payload_json=source_payload,
        )

        price = None
        if city is not None:
            price = self.repository.upsert_offer_price(
                offer_id=int(offer.id),
                city=city,
                price=supplier.get("price"),
                currency=supplier.get("currency"),
                availability=supplier.get("availability"),
                checked_at=datetime.utcnow(),
            )

        relation = self.repository.create_relation(
            material_id=int(material_id),
            edge_id=int(edge.id),
            relation_type="recommended",
            source_supplier_id=int(supplier_id),
            source_url=relation_source_url
            or (preview_item.get("discovered_card") or {}).get("source_url")
            or supplier.get("source_url"),
        )

        return {
            "status": (
                "persisted"
                if edge_created or existing_offer is None or relation is not None or (city is not None and existing_price is None)
                else "reused"
            ),
            "reason": None,
            "material_id": int(material_id),
            "manufacturer_id": int(manufacturer.id),
            "edge_id": int(edge.id),
            "edge_created": edge_created,
            "offer_id": int(offer.id),
            "offer_created": existing_offer is None,
            "relation_id": int(relation.id) if relation is not None else None,
            "relation_created": relation is not None,
            "price_id": int(price.id) if price is not None else None,
            "price_created": existing_price is None if city is not None else False,
            "preview_item": preview_item,
        }

    @staticmethod
    def _missing_identity_fields(canonical: dict[str, Any]) -> list[str]:
        required_fields = (
            "manufacturer",
            "manufacturer_article",
            "material_type",
            "width_mm",
            "thickness_mm",
        )
        missing = []
        for field in required_fields:
            value = canonical.get(field)
            if value in (None, ""):
                missing.append(field)
        return missing

    @staticmethod
    def _build_source_payload(*, preview_item: dict[str, Any]) -> str | None:
        payload = {
            "discovered_card": preview_item.get("discovered_card"),
            "canonical_candidate": preview_item.get("canonical_candidate"),
            "supplier_offer_candidate": preview_item.get("supplier_offer_candidate"),
            "raw_characteristics": preview_item.get("raw_characteristics"),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


async def _fetch_viyar_recommended_edges_preview_live(
    *,
    material_source_url: str,
    selected_city: str | None = None,
    cookie_override: str | None = None,
) -> dict[str, Any]:
    normalized_source_url = str(material_source_url or "").strip()
    if not normalized_source_url:
        return {
            "success": False,
            "error": "material_source_url is required",
            "material_url": None,
            "items": [],
        }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="uk-UA",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
        )

        cookies = []
        if selected_city:
            cookies.append(
                {
                    "name": "filial",
                    "value": str(selected_city).strip().upper(),
                    "domain": ".viyar.ua",
                    "path": "/",
                }
            )

        for chunk in str(cookie_override or "").split(";"):
            part = chunk.strip()
            if not part or "=" not in part:
                continue
            name, value = part.split("=", 1)
            cookies.append(
                {
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".viyar.ua",
                    "path": "/",
                }
            )

        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()
        try:
            return await preview_viyar_recommended_edges(normalized_source_url, page)
        finally:
            await context.close()
            await browser.close()


async def persist_viyar_recommended_edges_for_material_import(
    *,
    material_id: int,
    material_source_url: str,
    selected_city: str | None = None,
    cookie_override: str | None = None,
    preview_runner=None,
    relation_source_url: str | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    normalized_source_url = str(material_source_url or "").strip()
    if not normalized_source_url:
        return {
            "success": False,
            "error": "material_source_url is required",
            "preview": None,
            "persistence": None,
            "summary": {
                "discovered": 0,
                "persisted": 0,
                "needs_review": 0,
                "failed": 0,
            },
        }

    preview_runner = preview_runner or _fetch_viyar_recommended_edges_preview_live

    try:
        preview_result = await preview_runner(
            material_source_url=normalized_source_url,
            selected_city=selected_city,
            cookie_override=cookie_override,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc) or "Unable to preview recommended edges",
            "preview": None,
            "persistence": None,
            "summary": {
                "discovered": 0,
                "persisted": 0,
                "needs_review": 0,
                "failed": 1,
            },
        }

    service = EdgeFoundationPersistenceService(session=session)
    try:
        persistence_result = service.persist_preview_result(
            material_id=material_id,
            preview_result=preview_result,
            city=selected_city,
            relation_source_url=relation_source_url or normalized_source_url,
        )
    finally:
        service.close()

    counts = persistence_result.get("counts") or {}
    review_items = []
    for item in persistence_result.get("items") or []:
        if item.get("status") != "needs_review":
            continue
        preview_item = item.get("preview_item") or {}
        discovered_card = preview_item.get("discovered_card") or {}
        supplier = preview_item.get("supplier_offer_candidate") or {}
        review_items.append(
            {
                "article": discovered_card.get("article") or supplier.get("article"),
                "source_url": discovered_card.get("source_url") or supplier.get("source_url"),
                "reason": item.get("reason") or preview_item.get("reason") or "needs_review",
                "missing_fields": list(item.get("missing_fields") or preview_item.get("missing_fields") or []),
            }
        )
    summary = {
        "discovered": int(preview_result.get("recommended_edges_count") or 0),
        "persisted": int(counts.get("persisted") or 0),
        "needs_review": int(counts.get("needs_review") or 0),
        "failed": int(counts.get("failed") or 0),
    }
    return {
        "success": True,
        "material_source_url": normalized_source_url,
        "preview": preview_result,
        "persistence": persistence_result,
        "summary": summary,
        "review_items": review_items,
    }
