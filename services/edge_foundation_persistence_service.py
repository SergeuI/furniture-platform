from __future__ import annotations

import asyncio
import json
import logging
import re
import tempfile
from contextlib import nullcontext
from datetime import datetime
from typing import Any

from playwright.async_api import async_playwright
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.repositories.edge_foundation_repository import (
    EdgeFoundationRepository,
    normalize_supplier_article,
)
from database.models.fitting import SupplierModel  # noqa: F401 - register suppliers FK table
from database.models.material import MaterialModel
from database.models.canonical_edge import CanonicalEdgeModel
from database.session import SessionLocal
from database.deletion_protection import (
    canonical_edge_identity_key,
    is_auto_recreate_suppressed,
)
from services.viyar_parser import (
    _is_viyar_rejected_image,
    preview_viyar_edge_product,
    preview_viyar_recommended_edges,
)
from services.material_manufacturer_rules import MISSING_MANUFACTURER_NAME


logger = logging.getLogger(__name__)


class EdgeFoundationPersistenceService:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session or SessionLocal()
        self.repository = EdgeFoundationRepository(self.session)
        self._owns_session = session is None
        self._last_validation_diagnostics: dict[str, Any] = {}

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def resolve_manufacturer(self, manufacturer_name: str | None):
        if str(manufacturer_name or "").strip() == MISSING_MANUFACTURER_NAME:
            return self.repository.get_missing_manufacturer()
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
        atomic: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if atomic:
            return self._persist_preview_result_atomic(
                material_id=material_id,
                preview_result=preview_result,
                city=city,
                relation_source_url=relation_source_url,
                request_id=request_id,
            )

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

    def _persist_preview_result_atomic(
        self,
        *,
        material_id: int,
        preview_result: dict[str, Any],
        city: str | None,
        relation_source_url: str | None,
        request_id: str | None,
    ) -> dict[str, Any]:
        if self.session.in_transaction():
            return self._atomic_failure(
                "atomic persistence requires a clean session transaction"
            )

        items = list(preview_result.get("items") or [])
        self._last_validation_diagnostics = {}
        items, normalization_error = self._normalize_duplicate_candidates(
            material_id=material_id, items=items, request_id=request_id,
        )
        if normalization_error:
            self.session.rollback()
            return self._atomic_failure(
                normalization_error,
                diagnostic_snapshot_path=self._last_validation_diagnostics.get("snapshot_path"),
            )
        validation_error = self._validate_atomic_batch(
            material_id=material_id,
            items=items,
            city=city,
            request_id=request_id,
        )
        if validation_error:
            self.session.rollback()
            return self._atomic_failure(
                validation_error,
                diagnostic_snapshot_path=self._last_validation_diagnostics.get("snapshot_path"),
            )

        # Read validation starts a SQLAlchemy read transaction. End it before
        # opening the single write transaction used by strict mode.
        self.session.rollback()
        results: list[dict[str, Any]] = []
        diagnostic_context: dict[str, Any] = {
            "failed_index": None,
            "failed_supplier_article": None,
            "failed_manufacturer_article": None,
            "failed_phase": "unknown",
        }
        try:
            with self.session.begin():
                for index, preview_item in enumerate(items, start=1):
                    canonical = preview_item.get("canonical_candidate") or {}
                    supplier = preview_item.get("supplier_offer_candidate") or {}
                    diagnostic_context = {
                        "failed_index": index,
                        "failed_supplier_article": supplier.get("article"),
                        "failed_manufacturer_article": canonical.get("manufacturer_article"),
                        "failed_phase": "unknown",
                    }
                    results.append(
                        self.persist_preview_item(
                            material_id=material_id,
                            preview_item=preview_item,
                            city=city,
                            relation_source_url=relation_source_url,
                            diagnostic_context=diagnostic_context,
                        )
                    )
                    if results[-1].get("status") not in {"persisted", "reused"}:
                        raise ValueError(results[-1].get("reason") or "atomic item failed")
                diagnostic_context["failed_phase"] = "transaction_commit"
        except Exception as exc:
            self.session.rollback()
            logger.exception(
                "atomic edge persistence failed at item=%s article=%s phase=%s",
                diagnostic_context.get("failed_index"),
                diagnostic_context.get("failed_supplier_article"),
                diagnostic_context.get("failed_phase"),
            )
            return self._atomic_failure(
                str(exc) or "atomic persistence failed",
                exception_type=type(exc).__name__,
                **diagnostic_context,
            )

        return {
            "success": True,
            "status": "batch_persisted",
            "material_id": int(material_id),
            "city": city,
            "items": results,
            "rollback_performed": False,
            "counts": {
                "items": len(results),
                "persisted": sum(1 for item in results if item.get("status") == "persisted"),
                "reused": sum(1 for item in results if item.get("status") == "reused"),
                "needs_review": 0,
                "failed": 0,
            },
        }

    def _normalize_duplicate_candidates(
        self, *, material_id: int, items: list[dict[str, Any]], request_id: str | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        groups: dict[tuple[Any, ...], list[tuple[int, dict[str, Any]]]] = {}
        for index, item in enumerate(items, start=1):
            canonical = item.get("canonical_candidate") or {}
            manufacturer = self.resolve_manufacturer(canonical.get("manufacturer"))
            try:
                identity = (
                    int(manufacturer.id) if manufacturer is not None else str(canonical.get("manufacturer")),
                    str(canonical.get("manufacturer_article")),
                    str(canonical.get("material_type")),
                    str(canonical.get("technology_code") or "") or None,
                    float(canonical.get("width_mm")),
                    float(canonical.get("thickness_mm")),
                )
            except (TypeError, ValueError):
                continue
            groups.setdefault(identity, []).append((index, item))

        normalized: list[dict[str, Any]] = []
        for identity, group in groups.items():
            if len(group) == 1:
                normalized.append(group[0][1])
                continue
            first_item = group[0][1]
            first_canonical = first_item.get("canonical_candidate") or {}
            for _, item in group[1:]:
                canonical = item.get("canonical_candidate") or {}
                differences = [
                    field for field in ("decor_code", "color", "finish")
                    if canonical.get(field) != first_canonical.get(field)
                ]
                if differences:
                    conflict = {
                        "first_candidate_index": group[0][0],
                        "first_supplier_article": (first_item.get("supplier_offer_candidate") or {}).get("article"),
                        "conflicting_candidate_index": group[1][0],
                        "conflicting_supplier_article": (item.get("supplier_offer_candidate") or {}).get("article"),
                        "canonical_identity_key": {
                            "manufacturer_id": identity[0], "manufacturer_article": identity[1],
                            "material_type": identity[2], "technology_code": identity[3],
                            "width_mm": identity[4], "thickness_mm": identity[5],
                        },
                        "manufacturer": first_canonical.get("manufacturer"),
                        "manufacturer_article": first_canonical.get("manufacturer_article"),
                        "width": first_canonical.get("width_mm"),
                        "thickness": first_canonical.get("thickness_mm"),
                        "incompatible_fields": differences,
                        "reason": "duplicate_canonical_identity_conflict",
                    }
                    self._last_validation_diagnostics = {
                        "conflict": conflict,
                        "snapshot_path": self._write_validation_failure_snapshot(
                            material_id=material_id, request_id=request_id, items=items,
                            validation_error="duplicate_canonical_identity_conflict", conflict=conflict,
                            candidate_contexts=[],
                        ),
                    }
                    return items, "duplicate_canonical_identity_conflict"
            for _, item in group:
                supplier = dict(item.get("supplier_offer_candidate") or {})
                if not supplier.get("external_product_id"):
                    supplier["_persistence_external_product_id"] = str(supplier.get("article") or "").strip()
                normalized_item = dict(item)
                normalized_item["_normalized_duplicate"] = True
                normalized_item["supplier_offer_candidate"] = supplier
                normalized.append(normalized_item)
            logger.info(
                "[EDGE_CANONICAL_IDENTITY_NORMALIZED] request_id=%s material_id=%s canonical_identity_key=%s primary_supplier_article=%s duplicate_supplier_articles=%s group_size=%s reason=duplicate_recommendation_normalized",
                request_id or "unknown", material_id, json.dumps({
                    "manufacturer_id": identity[0], "manufacturer_article": identity[1],
                    "material_type": identity[2], "technology_code": identity[3],
                    "width_mm": identity[4], "thickness_mm": identity[5],
                }, ensure_ascii=False, sort_keys=True),
                (first_item.get("supplier_offer_candidate") or {}).get("article"),
                json.dumps([((item.get("supplier_offer_candidate") or {}).get("article")) for _, item in group[1:]], ensure_ascii=False),
                len(group),
            )
        return normalized, None

    def _validate_atomic_batch(
        self,
        *,
        material_id: int,
        items: list[dict[str, Any]],
        city: str | None,
        request_id: str | None = None,
    ) -> str | None:
        material_exists = self.session.execute(
            select(MaterialModel.id).where(MaterialModel.id == int(material_id))
        ).first()
        if material_exists is None:
            return f"material_not_found:{material_id}"

        seen_identities: set[tuple[Any, ...]] = set()
        seen_identity_contexts: dict[tuple[Any, ...], dict[str, Any]] = {}
        seen_offers: dict[tuple[Any, ...], str] = {}
        for index, item in enumerate(items, start=1):
            if str(item.get("status") or "").strip().lower() != "parsed":
                return f"item_{index}:preview_not_parsed"

            canonical = item.get("canonical_candidate") or {}
            supplier = item.get("supplier_offer_candidate") or {}
            missing = self._missing_identity_fields(canonical)
            if missing:
                return f"item_{index}:missing_identity_fields:{','.join(missing)}"

            manufacturer = self.resolve_manufacturer(canonical.get("manufacturer"))
            if manufacturer is None:
                return f"item_{index}:manufacturer_not_found:{canonical.get('manufacturer')}"

            supplier_id = self.resolve_supplier_id(supplier.get("supplier"))
            if supplier_id is None:
                return f"item_{index}:supplier_not_found:{supplier.get('supplier')}"

            supplier_article = str(supplier.get("article") or "").strip()
            source_url = str(supplier.get("source_url") or "").strip()
            if not supplier_article:
                return f"item_{index}:supplier_article_missing"
            if not re.match(r"^https?://", source_url, re.IGNORECASE):
                return f"item_{index}:source_url_invalid"
            if not str(supplier.get("unit") or "").strip():
                return f"item_{index}:unit_missing"
            if not str(supplier.get("currency") or "").strip():
                return f"item_{index}:currency_missing"
            image_url = str(canonical.get("image_url") or "").strip()
            if image_url and _is_viyar_rejected_image(image_url):
                return f"item_{index}:invalid_image"
            try:
                if float(supplier.get("price")) < 0:
                    return f"item_{index}:price_invalid"
            except (TypeError, ValueError):
                return f"item_{index}:price_invalid"

            identity = (
                int(manufacturer.id),
                str(canonical.get("manufacturer_article")),
                str(canonical.get("material_type")),
                str(canonical.get("technology_code") or "") or None,
                float(canonical.get("width_mm")),
                float(canonical.get("thickness_mm")),
            )
            identity_key = {
                "manufacturer_id": identity[0],
                "manufacturer_article": identity[1],
                "material_type": identity[2],
                "technology_code": identity[3],
                "width_mm": identity[4],
                "thickness_mm": identity[5],
            }
            candidate_context = {
                "candidate_index": index,
                "supplier_article": supplier_article,
                "manufacturer": canonical.get("manufacturer"),
                "manufacturer_article": canonical.get("manufacturer_article"),
                "type": canonical.get("material_type"),
                "technology_code": canonical.get("technology_code"),
                "width": canonical.get("width_mm"),
                "thickness": canonical.get("thickness_mm"),
                "canonical_identity_key": identity_key,
                "manufacturer_id": identity[0],
            }
            logger.info(
                "[EDGE_CANONICAL_IDENTITY] request_id=%s material_id=%s candidate_index=%s supplier_article=%s manufacturer=%s manufacturer_article=%s type=%s technology_code=%s width=%s thickness=%s canonical_identity_key=%s",
                request_id or "unknown",
                material_id,
                index,
                supplier_article,
                canonical.get("manufacturer"),
                canonical.get("manufacturer_article"),
                canonical.get("material_type"),
                canonical.get("technology_code"),
                canonical.get("width_mm"),
                canonical.get("thickness_mm"),
                json.dumps(identity_key, ensure_ascii=False, sort_keys=True),
            )
            if identity in seen_identities:
                first = seen_identity_contexts[identity]
                conflict = {
                    "first_candidate_index": first["candidate_index"],
                    "first_supplier_article": first["supplier_article"],
                    "conflicting_candidate_index": index,
                    "conflicting_supplier_article": supplier_article,
                    "canonical_identity_key": identity_key,
                    "manufacturer": canonical.get("manufacturer"),
                    "manufacturer_article": canonical.get("manufacturer_article"),
                    "width": canonical.get("width_mm"),
                    "thickness": canonical.get("thickness_mm"),
                    "reason": "duplicate_canonical_identity",
                }
                logger.error(
                    "[EDGE_CANONICAL_IDENTITY_DUPLICATE] request_id=%s material_id=%s first_candidate_index=%s first_supplier_article=%s conflicting_candidate_index=%s conflicting_supplier_article=%s canonical_identity_key=%s manufacturer=%s manufacturer_article=%s width=%s thickness=%s reason=duplicate_canonical_identity",
                    request_id or "unknown",
                    material_id,
                    conflict["first_candidate_index"],
                    conflict["first_supplier_article"],
                    conflict["conflicting_candidate_index"],
                    conflict["conflicting_supplier_article"],
                    json.dumps(identity_key, ensure_ascii=False, sort_keys=True),
                    conflict["manufacturer"],
                    conflict["manufacturer_article"],
                    conflict["width"],
                    conflict["thickness"],
                )
                if item.get("_normalized_duplicate"):
                    continue
                if item.get("_normalized_duplicate"):
                    continue
                self._last_validation_diagnostics = {
                    "conflict": conflict,
                    "snapshot_path": self._write_validation_failure_snapshot(
                        material_id=material_id,
                        request_id=request_id,
                        items=items,
                        validation_error=f"item_{index}:duplicate_canonical_identity",
                        conflict=conflict,
                        candidate_contexts=[
                            *seen_identity_contexts.values(),
                            {**candidate_context, "canonical_identity_key": identity_key},
                        ],
                    ),
                }
                return f"item_{index}:duplicate_canonical_identity"
            seen_identities.add(identity)
            seen_identity_contexts[identity] = candidate_context

            edge = self.repository.get_edge_by_identity(
                manufacturer_id=identity[0],
                manufacturer_article=identity[1],
                material_type=identity[2],
                technology_code=identity[3],
                width_mm=identity[4],
                thickness_mm=identity[5],
            )
            if edge is None:
                conflicting_edge = (
                    self.session.query(CanonicalEdgeModel)
                    .filter(CanonicalEdgeModel.manufacturer_id == identity[0])
                    .filter(CanonicalEdgeModel.manufacturer_article == identity[1])
                    .first()
                )
                if conflicting_edge is not None:
                    return f"item_{index}:canonical_identity_conflict"
                edge_id = None
            else:
                edge_id = int(edge.id)

            external_product_id = supplier.get("_persistence_external_product_id") or supplier.get("external_product_id")
            external_product_id = str(external_product_id).strip() if external_product_id is not None else None
            external_product_id = external_product_id or None
            article_key = (edge_id or identity, int(supplier_id), normalize_supplier_article(supplier_article))
            previous_article = seen_offers.get(article_key)
            if previous_article is not None:
                return f"item_{index}:duplicate_offer_identity"
            seen_offers[article_key] = supplier_article

            article_offers = self.repository.list_offers_by_supplier_article(
                supplier_id=int(supplier_id),
                supplier_article=supplier_article,
            )
            other_edge_offers = [
                offer for offer in article_offers
                if edge is None or int(offer.edge_id) != int(edge.id)
            ]
            if other_edge_offers:
                return f"item_{index}:supplier_offer_cross_edge_conflict"
            if len(article_offers) > 1:
                return f"item_{index}:supplier_offer_conflict"
            if article_offers:
                existing_offer = article_offers[0]
                existing_external = str(existing_offer.external_product_id or "").strip() or None
                if (
                    external_product_id is not None
                    and existing_external is not None
                    and existing_external != external_product_id
                ):
                    return f"item_{index}:supplier_offer_conflict"
            if edge is not None and external_product_id is not None:
                existing_offer = self.repository.get_offer_by_identity(
                    edge_id=int(edge.id),
                    supplier_id=int(supplier_id),
                    external_product_id=external_product_id,
                )
                if existing_offer is not None and normalize_supplier_article(existing_offer.article) != supplier_article:
                    return f"item_{index}:supplier_offer_conflict"

        return None

    def preflight_preview_result(
        self,
        *,
        material_id: int,
        preview_result: dict[str, Any],
        city: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve parsed candidates without writing; isolate local conflicts."""
        items = [dict(item) for item in list(preview_result.get("items") or [])]
        identity_groups: dict[tuple[Any, ...], list[tuple[int, dict[str, Any]]]] = {}
        identities: dict[int, tuple[Any, ...]] = {}

        for index, item in enumerate(items):
            if str(item.get("status") or "").strip().lower() != "parsed":
                continue
            canonical = item.get("canonical_candidate") or {}
            manufacturer = self.resolve_manufacturer(canonical.get("manufacturer"))
            try:
                identity = (
                    int(manufacturer.id) if manufacturer is not None else str(canonical.get("manufacturer")),
                    str(canonical.get("manufacturer_article")),
                    str(canonical.get("material_type")),
                    str(canonical.get("technology_code") or "") or None,
                    float(canonical.get("width_mm")),
                    float(canonical.get("thickness_mm")),
                )
            except (TypeError, ValueError):
                continue
            identities[index] = identity
            identity_groups.setdefault(identity, []).append((index, item))

        local_conflict_indexes: set[int] = set()
        for identity, group in identity_groups.items():
            if len(group) < 2:
                continue
            first_index, first_item = group[0]
            first_canonical = first_item.get("canonical_candidate") or {}
            for index, item in group[1:]:
                canonical = item.get("canonical_candidate") or {}
                differences = [
                    field for field in ("decor_code", "color", "finish")
                    if canonical.get(field) != first_canonical.get(field)
                ]
                if not differences:
                    continue
                local_conflict_indexes.update({first_index, index})
                item["status"] = "needs_review"
                item["reason"] = "duplicate_canonical_identity_conflict"
                item["error"] = "duplicate_canonical_identity_conflict"
                item["preflight_conflict"] = {
                    "first_candidate_index": first_index + 1,
                    "first_supplier_article": (first_item.get("supplier_offer_candidate") or {}).get("article"),
                    "conflicting_candidate_index": index + 1,
                    "conflicting_supplier_article": (item.get("supplier_offer_candidate") or {}).get("article"),
                    "incompatible_fields": differences,
                    "canonical_identity_key": {
                        "manufacturer_id": identity[0],
                        "manufacturer_article": identity[1],
                        "material_type": identity[2],
                        "technology_code": identity[3],
                        "width_mm": identity[4],
                        "thickness_mm": identity[5],
                    },
                    "reason": "duplicate_canonical_identity_conflict",
                }
                first_item["status"] = "needs_review"
                first_item["reason"] = "duplicate_canonical_identity_conflict"
                first_item["error"] = "duplicate_canonical_identity_conflict"
                first_item["preflight_conflict"] = item["preflight_conflict"]

        fatal_reason = None
        for index, item in enumerate(items):
            if index in local_conflict_indexes or str(item.get("status") or "").strip().lower() != "parsed":
                continue
            error = self._validate_atomic_batch(
                material_id=material_id,
                items=[item],
                city=city,
                request_id=request_id,
            )
            if not error:
                continue
            if error.startswith("material_not_found:"):
                fatal_reason = error
                break
            reason = error.split(":", 1)[1] if ":" in error else error
            item["status"] = "needs_review"
            item["reason"] = reason
            item["error"] = reason
            item["preflight_reason"] = reason

        if fatal_reason:
            return {
                "success": False,
                "reason": fatal_reason,
                "items": items,
                "ready_items": [],
                "normalized_duplicates": 0,
            }

        ready_items = [
            item for item in items
            if str(item.get("status") or "").strip().lower() == "parsed"
        ]
        return {
            "success": True,
            "reason": None,
            "items": items,
            "ready_items": ready_items,
            "normalized_duplicates": sum(1 for item in ready_items if item.get("_normalized_duplicate")),
        }

    @staticmethod
    def _atomic_failure(
        reason: str,
        *,
        exception_type: str | None = None,
        failed_index: int | None = None,
        failed_supplier_article: str | None = None,
        failed_manufacturer_article: str | None = None,
        failed_phase: str = "unknown",
        diagnostic_snapshot_path: str | None = None,
    ) -> dict[str, Any]:
        return {
            "success": False,
            "status": "batch_failed",
            "reason": reason,
            "exception_type": exception_type,
            "failed_index": failed_index,
            "failed_supplier_article": failed_supplier_article,
            "failed_manufacturer_article": failed_manufacturer_article,
            "failed_phase": failed_phase,
            "rollback_performed": True,
            "persisted_count": 0,
            "diagnostic_snapshot_path": diagnostic_snapshot_path,
            "items": [],
            "counts": {
                "items": 0,
                "persisted": 0,
                "reused": 0,
                "needs_review": 0,
                "failed": 1,
            },
        }

    @staticmethod
    def _write_validation_failure_snapshot(
        *,
        material_id: int,
        request_id: str | None,
        items: list[dict[str, Any]],
        validation_error: str,
        conflict: dict[str, Any] | None,
        candidate_contexts: list[dict[str, Any]],
    ) -> str | None:
        safe_request_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(request_id or "unknown"))
        path = f"{tempfile.gettempdir()}\\edge-preview-failure-{safe_request_id}.json"
        payload = {
            "material_id": int(material_id),
            "request_id": request_id or "unknown",
            "candidates": candidate_contexts,
            "validation": {"error": validation_error, "conflict": conflict},
        }
        try:
            with open(path, "w", encoding="utf-8") as snapshot:
                json.dump(payload, snapshot, ensure_ascii=False, indent=2, sort_keys=True)
            return path
        except OSError:
            logger.exception("unable to write atomic validation diagnostic snapshot")
            return None

    def persist_preview_item(
        self,
        *,
        material_id: int | None,
        preview_item: dict[str, Any],
        city: str | None = None,
        relation_source_url: str | None = None,
        create_relation: bool = True,
        diagnostic_context: dict[str, Any] | None = None,
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
            "technology_code": canonical.get("technology_code"),
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
            "cleanup_policy": "delete_when_orphan",
        }
        if is_auto_recreate_suppressed(
            self.session,
            "canonical_edge",
            canonical_edge_identity_key(identity),
        ):
            return {
                "status": "needs_review",
                "reason": "canonical_edge_deletion_suppressed",
                "missing_fields": [],
                "preview_item": preview_item,
            }
        if diagnostic_context is not None:
            diagnostic_context["failed_phase"] = "canonical_edge"
        edge, edge_created = self.repository.upsert_edge(identity=identity, data=edge_data)

        existing_offer = self.repository.get_offer_by_identity(
            edge_id=int(edge.id),
            supplier_id=int(supplier_id),
            external_product_id=supplier.get("_persistence_external_product_id") or supplier.get("external_product_id"),
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
        if diagnostic_context is not None:
            diagnostic_context["failed_phase"] = "supplier_offer"
        offer = self.repository.upsert_offer(
            edge_id=int(edge.id),
            supplier_id=int(supplier_id),
            article=supplier.get("article"),
            external_product_id=supplier.get("_persistence_external_product_id") or supplier.get("external_product_id"),
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
            if diagnostic_context is not None:
                diagnostic_context["failed_phase"] = "price"
            price = self.repository.upsert_offer_price(
                offer_id=int(offer.id),
                city=city,
                price=supplier.get("price"),
                currency=supplier.get("currency"),
                availability=supplier.get("availability"),
                checked_at=datetime.utcnow(),
            )

        relation = None
        if create_relation and material_id is not None:
            if diagnostic_context is not None:
                diagnostic_context["failed_phase"] = "relation"
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
            "material_id": int(material_id) if material_id is not None else None,
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

    def persist_preview_result_for_catalog(
        self,
        *,
        preview_result: dict[str, Any],
        city: str | None = None,
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
                                material_id=None,
                                preview_item=preview_item,
                                city=city,
                                relation_source_url=None,
                                create_relation=False,
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


def _summarize_viyar_preview_items(preview_result: dict[str, Any]) -> dict[str, int]:
    items = list(preview_result.get("items") or [])
    discovered_total = int(preview_result.get("recommended_edges_count") or len(items))
    summary = {
        "total": discovered_total,
        "result_count": len(items),
        "parsed": 0,
        "needs_review": 0,
        "failed": 0,
    }
    for item in items:
        status = str(item.get("status") or "").strip().lower()
        if status == "parsed":
            summary["parsed"] += 1
        elif status == "needs_review":
            summary["needs_review"] += 1
        elif status == "failed":
            summary["failed"] += 1
    return summary


def _preview_result_invariant(preview_result: dict[str, Any], summary: dict[str, int]) -> bool:
    return (
        summary["total"] == summary["result_count"]
        and summary["total"] == summary["parsed"] + summary["failed"] + summary["needs_review"]
    )


def _build_viyar_preview_review_items(preview_result: dict[str, Any]) -> list[dict[str, Any]]:
    review_items: list[dict[str, Any]] = []
    for item in list(preview_result.get("items") or []):
        if str(item.get("status") or "").strip().lower() != "needs_review":
            continue
        discovered_card = item.get("discovered_card") or {}
        supplier = item.get("supplier_offer_candidate") or {}
        review_items.append(
            {
                "article": discovered_card.get("article") or supplier.get("article"),
                "source_url": discovered_card.get("source_url") or supplier.get("source_url"),
                "reason": item.get("reason") or "needs_review",
                "missing_fields": list(item.get("missing_fields") or []),
            }
        )
    return review_items


async def _fetch_viyar_recommended_edges_preview_live(
    *,
    material_source_url: str,
    selected_city: str | None = None,
    cookie_override: str | None = None,
    progress_callback=None,
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
            return await preview_viyar_recommended_edges(
                normalized_source_url,
                page,
                progress_callback=progress_callback,
            )
        finally:
            await context.close()
            await browser.close()


async def _fetch_viyar_edge_product_preview_live(
    *,
    product_url: str,
    selected_city: str | None = None,
    cookie_override: str | None = None,
) -> dict[str, Any]:
    normalized_product_url = str(product_url or "").strip()
    if not normalized_product_url:
        return {
            "success": False,
            "error": "product_url is required",
            "source_url": None,
            "items": [],
            "preview_count": 0,
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
            return await preview_viyar_edge_product(normalized_product_url, page)
        finally:
            await context.close()
            await browser.close()


async def preview_viyar_edge_product_for_catalog(
    *,
    product_url: str,
    selected_city: str | None = None,
    cookie_override: str | None = None,
) -> dict[str, Any]:
    return await _fetch_viyar_edge_product_preview_live(
        product_url=product_url,
        selected_city=selected_city,
        cookie_override=cookie_override,
    )


async def preview_viyar_recommended_edges_for_catalog(
    *,
    source_url: str,
    selected_city: str | None = None,
    cookie_override: str | None = None,
) -> dict[str, Any]:
    return await _fetch_viyar_recommended_edges_preview_live(
        material_source_url=source_url,
        selected_city=selected_city,
        cookie_override=cookie_override,
    )


async def persist_viyar_recommended_edges_for_material_import(
    *,
    material_id: int,
    material_source_url: str,
    selected_city: str | None = None,
    cookie_override: str | None = None,
    preview_runner=None,
    relation_source_url: str | None = None,
    session: Session | None = None,
    progress_callback=None,
    request_id: str | None = None,
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
        preview_kwargs = {
            "material_source_url": normalized_source_url,
            "selected_city": selected_city,
            "cookie_override": cookie_override,
        }
        if progress_callback is not None:
            preview_kwargs["progress_callback"] = progress_callback
        preview_result = await preview_runner(**preview_kwargs)
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc) or "Unable to preview recommended edges",
            "preview": None,
            "persistence": None,
            "summary": {
                "total": 0,
                "parsed": 0,
                "discovered": 0,
                "persisted": 0,
                "needs_review": 0,
                "failed": 1,
                "status": "preview_incomplete",
                "reason": "preview_incomplete",
            },
            "review_items": [],
        }

    preview_counts = _summarize_viyar_preview_items(preview_result)
    discovery = preview_result.get("discovery") or {}
    logger.info(
        "[MATERIAL_EDGE_DISCOVERY] request_id=%s material_id=%s discovery_source=%s api_candidate_count=%s dom_candidate_count=%s final_candidate_count=%s api_reason=%s api_status=%s api_recommendation_status=%s",
        request_id or "unknown",
        material_id,
        discovery.get("source") or "none",
        int(discovery.get("api_candidate_count") or 0),
        int(discovery.get("dom_candidate_count") or 0),
        int(discovery.get("final_candidate_count") or preview_counts["total"]),
        discovery.get("api_reason") or "",
        discovery.get("api_status") or "",
        discovery.get("api_recommendation_status") or "",
    )
    review_items = _build_viyar_preview_review_items(preview_result)
    invariant_valid = _preview_result_invariant(preview_result, preview_counts)
    if not invariant_valid:
        items = list(preview_result.get("items") or [])
        missing_indexes = [
            index for index, item in enumerate(items)
            if str(item.get("status") or "").strip().lower()
            not in {"parsed", "failed", "needs_review"}
        ]
        logger.error(
            "[MATERIAL_EDGE_PREVIEW_RESULT_INCOMPLETE] material_id=%s total=%s result_count=%s parsed=%s failed=%s needs_review=%s missing_indexes=%s missing_articles=%s",
            material_id,
            preview_counts["total"],
            preview_counts["result_count"],
            preview_counts["parsed"],
            preview_counts["failed"],
            preview_counts["needs_review"],
            missing_indexes,
            [
                (item.get("discovered_card") or {}).get("article")
                for index, item in enumerate(items)
                if index in missing_indexes
            ],
        )
    preview_incomplete = (
        not bool(preview_result.get("success"))
        or not invariant_valid
        or preview_counts["total"] == 0
    )

    if preview_incomplete:
        return {
            "success": False,
            "error": "preview_result_incomplete" if not invariant_valid else "preview_incomplete",
            "material_source_url": normalized_source_url,
            "preview": preview_result,
            "persistence": None,
            "summary": {
                **preview_counts,
                "discovered": preview_counts["total"],
                "persisted": 0,
                "status": "preview_incomplete",
                "reason": "preview_result_incomplete" if not invariant_valid else "preview_incomplete",
            },
            "review_items": review_items,
        }

    service = EdgeFoundationPersistenceService(session=session)
    try:
        preflight = service.preflight_preview_result(
            material_id=material_id,
            preview_result=preview_result,
            city=selected_city,
            request_id=request_id,
        )
        if not isinstance(preflight, dict):
            # Keep compatibility with injected persistence doubles; production
            # services always return the structured preflight contract.
            preflight = {
                "success": True,
                "reason": None,
                "items": list(preview_result.get("items") or []),
                "ready_items": list(preview_result.get("items") or []),
                "normalized_duplicates": 0,
            }
    except Exception as exc:
        service.close()
        return {
            "success": False,
            "error": str(exc) or "canonical_preflight_failed",
            "material_source_url": normalized_source_url,
            "preview": preview_result,
            "persistence": None,
            "summary": {
                **preview_counts,
                "discovered": preview_counts["total"],
                "persisted": 0,
                "status": "failed",
                "reason": "canonical_preflight_failed",
            },
            "review_items": review_items,
        }

    if not preflight["success"]:
        service.close()
        return {
            "success": False,
            "error": preflight["reason"],
            "material_source_url": normalized_source_url,
            "preview": preview_result,
            "persistence": None,
            "summary": {
                **preview_counts,
                "discovered": preview_counts["total"],
                "persisted": 0,
                "status": "failed",
                "reason": preflight["reason"],
            },
            "review_items": review_items,
        }

    # Preflight is read-only, but SQLAlchemy keeps its read transaction open.
    # End it before strict atomic persistence starts its write transaction.
    service.session.rollback()

    preview_result = dict(preview_result)
    preview_result["items"] = preflight["items"]
    preview_counts = _summarize_viyar_preview_items(preview_result)
    review_items = _build_viyar_preview_review_items(preview_result)
    valid_items = [
        item for item in list(preview_result.get("items") or [])
        if str(item.get("status") or "").strip().lower() == "parsed"
    ]
    if not valid_items:
        service.close()
        return {
            "success": True,
            "error": None,
            "material_source_url": normalized_source_url,
            "preview": preview_result,
            "persistence": None,
            "summary": {
                **preview_counts,
                "discovered": preview_counts["total"],
                "persisted": 0,
                "status": "no_valid_recommended_edges",
                "reason": "no_valid_recommended_edges",
            },
            "review_items": review_items,
        }

    persistence_preview = dict(preview_result)
    persistence_preview["items"] = valid_items
    persistence_preview["preview_count"] = len(valid_items)
    persistence_preview["candidate_results_count"] = len(valid_items)

    if progress_callback is not None:
        preflight_event = {
            "phase": "canonical_preflight",
            "count": len(valid_items),
            "total": preview_counts["total"],
            "failed": preview_counts["failed"],
            "needs_review": preview_counts["needs_review"],
        }
        callback_result = progress_callback(preflight_event)
        if asyncio.iscoroutine(callback_result):
            await callback_result

        persisting_event = {
            "phase": "persisting",
            "count": len(valid_items),
            "total": preview_counts["total"],
        }
        callback_result = progress_callback(persisting_event)
        if asyncio.iscoroutine(callback_result):
            await callback_result

    logger.info(
        "[MATERIAL_EDGE_PERSISTENCE_STARTED] request_id=%s material_id=%s input_count=%s preview_total=%s parsed=%s failed=%s needs_review=%s",
        request_id or "unknown",
        material_id,
        len(valid_items),
        preview_counts["total"],
        preview_counts["parsed"],
        preview_counts["failed"],
        preview_counts["needs_review"],
    )
    try:
        persistence_result = service.persist_preview_result(
            material_id=material_id,
            preview_result=persistence_preview,
            city=selected_city,
            relation_source_url=relation_source_url or normalized_source_url,
            atomic=True,
            request_id=request_id,
        )
    finally:
        service.close()

    counts = persistence_result.get("counts") or {}
    persistence_success = bool(persistence_result.get("success"))
    has_preview_warnings = preview_counts["failed"] > 0 or preview_counts["needs_review"] > 0
    summary = {
        "total": preview_counts["total"],
        "result_count": preview_counts["result_count"],
        "parsed": preview_counts["parsed"],
        "discovered": preview_counts["total"],
        "persisted": int(counts.get("persisted") or 0),
        "needs_review": preview_counts["needs_review"],
        "failed": preview_counts["failed"],
        "status": (
            "completed_with_warnings"
            if persistence_success and has_preview_warnings
            else "completed"
            if persistence_success
            else "failed"
        ),
        "reason": persistence_result.get("reason"),
    }
    return {
        "success": persistence_success,
        "error": persistence_result.get("reason") if not persistence_success else None,
        "material_source_url": normalized_source_url,
        "preview": preview_result,
        "persistence": persistence_result,
        "summary": summary,
        "review_items": review_items,
    }
