from datetime import datetime
import re
import uuid
from datetime import timedelta

from sqlalchemy import and_, func

from database.session import (
    SessionLocal,
)

from database.models.service_catalog_item import (
    ServiceCatalogItemModel,
)
from database.models.user_service_catalog_price import (
    UserServiceCatalogPriceModel,
)
from database.models.user import (
    UserModel,
)

from services.viyar_service_catalog_service import (
    build_viyar_service_catalog_records,
    backfill_viyar_service_descriptions,
    fetch_viyar_service_price_updates,
    _is_blocked_viyar_service_name,
    _extract_viyar_service_category,
)


def _normalize_viyar_article(value: str | None) -> str | None:

    normalized = (value or "").strip()

    if not normalized:
        return None

    if re.fullmatch(r"\d{4,}", normalized):
        return normalized

    return None


def _serialize_service_catalog_item(
    item,
    user_price=None,
) -> dict:

    effective_price = (
        user_price.base_price
        if user_price and user_price.base_price is not None
        else item.base_price
    )
    effective_currency = (
        user_price.currency
        if user_price and user_price.currency
        else item.currency
    )

    return {
        "id": item.id,
        "source": item.source,
        "external_code": item.external_code,
        "parent_external_code": item.parent_external_code,
        "owner_user_id": item.owner_user_id,
        "name": item.name,
        "slug": item.slug,
        "item_type": item.item_type,
        "folder_path": item.folder_path,
        "description": item.description,
        "full_description": item.full_description,
        "article": item.article,
        "unit": item.unit,
        "base_price": item.base_price,
        "currency": item.currency,
        "source_url": item.source_url,
        "rules_source_url": item.rules_source_url,
        "rules_parsed_at": item.rules_parsed_at,
        "rules_parse_status": item.rules_parse_status,
        "is_calculable": item.is_calculable,
        "sort_order": item.sort_order,
        "is_active": item.is_active,
        "last_synced_at": item.last_synced_at,
        "price_sync_status": item.price_sync_status,
        "price_source_label": item.price_source_label,
        "effective_price": effective_price,
        "effective_currency": effective_currency,
        "user_price": user_price.base_price if user_price else None,
        "user_currency": user_price.currency if user_price else None,
        "user_last_synced_at": user_price.last_synced_at if user_price else None,
        "user_price_sync_status": user_price.price_sync_status if user_price else None,
        "user_price_source_label": user_price.price_source_label if user_price else None,
    }


def seed_default_viyar_service_catalog():

    sync_viyar_service_catalog(
        use_remote=False,
        deactivate_missing=False,
    )


def get_viyar_service_description_audit(
    include_inactive: bool = False,
) -> dict[str, int]:

    db = SessionLocal()

    try:

        query = db.query(ServiceCatalogItemModel).filter(
            ServiceCatalogItemModel.source == "viyar",
            ServiceCatalogItemModel.item_type == "service",
        )

        if not include_inactive:
            query = query.filter(ServiceCatalogItemModel.is_active.is_(True))

        items = query.order_by(
            ServiceCatalogItemModel.folder_path.asc(),
            ServiceCatalogItemModel.sort_order.asc(),
            ServiceCatalogItemModel.name.asc(),
        ).all()

        def build_bucket() -> dict[str, int]:
            return {
                "total_services": 0,
                "with_source_url": 0,
                "with_short_description": 0,
                "with_only_short_description": 0,
                "with_full_description": 0,
                "with_description_marker": 0,
                "no_full_description": 0,
                "without_full_description": 0,
                "without_description_marker": 0,
                "needs_review": 0,
                "failed_downloads": 0,
            }

        audit = build_bucket()
        audit["categories"] = {
            "drilling": build_bucket(),
            "edgebanding": build_bucket(),
            "cutting": build_bucket(),
            "milling": build_bucket(),
            "other": build_bucket(),
        }

        for item in items:
            category = _extract_viyar_service_category(item.folder_path)
            bucket = audit["categories"][category]
            has_source_url = bool((item.source_url or "").strip())
            has_short_description = bool((item.description or "").strip())
            has_full_description = bool((item.full_description or "").strip())
            has_description_marker = "опис:" in (item.full_description or "").lower()
            status = (item.rules_parse_status or "").strip().lower()

            for current_bucket in (audit, bucket):
                current_bucket["total_services"] += 1
                if has_source_url:
                    current_bucket["with_source_url"] += 1
                if has_short_description:
                    current_bucket["with_short_description"] += 1
                if has_short_description and not has_full_description:
                    current_bucket["with_only_short_description"] += 1
                if has_full_description:
                    current_bucket["with_full_description"] += 1
                if has_description_marker:
                    current_bucket["with_description_marker"] += 1
                if status == "failed":
                    current_bucket["failed_downloads"] += 1
                if status == "needs_review":
                    current_bucket["needs_review"] += 1
                elif status == "no_full_description" or (not has_full_description and not status):
                    current_bucket["no_full_description"] += 1
                if has_full_description and not has_description_marker:
                    current_bucket["without_description_marker"] += 1
                current_bucket["without_full_description"] = current_bucket["no_full_description"]

        return audit

    finally:

        db.close()


def sync_viyar_service_catalog(
    use_remote: bool = True,
    cookie_override: str | None = None,
    deactivate_missing: bool = False,
) -> dict:

    records, audit = build_viyar_service_catalog_records(
        use_remote=use_remote,
        cookie_override=cookie_override,
    )

    db = SessionLocal()

    try:

        existing_items = (
            db.query(ServiceCatalogItemModel)
            .filter(ServiceCatalogItemModel.source == "viyar")
            .all()
        )

        existing_by_code = {
            item.external_code: item
            for item in existing_items
        }
        existing_active_service_count = sum(
            1
            for item in existing_items
            if item.item_type == "service" and item.is_active
        )

        imported_codes: set[str] = set()
        imported_service_count = sum(
            1
            for record in records
            if record["item_type"] == "service"
        )
        imported_service_articles = sum(
            1
            for record in records
            if record["item_type"] == "service" and record.get("article")
        )
        fallback_only_import = (
            imported_service_count > 0
            and imported_service_count <= 12
            and imported_service_articles == 0
            and existing_active_service_count > imported_service_count
        )
        deactivated_suspicious_count = 0

        for record in records:

            item = existing_by_code.get(record["external_code"])

            if not item:
                item = ServiceCatalogItemModel(
                    source=record["source"],
                    external_code=record["external_code"],
                )
                db.add(item)

            item.parent_external_code = record["parent_external_code"]
            item.name = record["name"]
            item.slug = record["slug"]
            item.item_type = record["item_type"]
            item.folder_path = record["folder_path"]
            item.description = record["description"] or item.description
            next_article = _normalize_viyar_article(record.get("article"))
            current_article = _normalize_viyar_article(item.article)

            if record["item_type"] == "service":
                item.article = next_article or current_article
            else:
                item.article = None
            item.unit = record["unit"] or item.unit
            item.base_price = (
                record["base_price"]
                if record["base_price"] is not None
                else item.base_price
            )
            item.currency = (
                record["currency"]
                if record["base_price"] is not None
                else (item.currency or record["currency"])
            )
            item.source_url = record["source_url"] or item.source_url
            item.is_calculable = record["is_calculable"]
            item.sort_order = record["sort_order"]
            item.is_active = record["is_active"]

            imported_codes.add(record["external_code"])

        for item in existing_items:
            if item.item_type != "service" or not item.is_active:
                continue

            if not _is_blocked_viyar_service_name(item.name):
                continue

            item.is_active = False
            deactivated_suspicious_count += 1

        if deactivate_missing and not fallback_only_import:
            for item in existing_items:
                if item.external_code not in imported_codes:
                    item.is_active = False

        db.commit()

        description_backfill_audit = {}

        if use_remote:
            description_backfill_audit = backfill_viyar_service_descriptions(
                use_remote=use_remote,
                cookie_override=cookie_override,
            )

        description_audit = get_viyar_service_description_audit(
            include_inactive=False,
        )

        return {
            "import_audit": {
                **audit,
                "deactivated_suspicious_count": deactivated_suspicious_count,
            },
            "description_backfill_audit": description_backfill_audit,
            "drilling_description_audit": description_backfill_audit,
            "description_audit": description_audit,
            "items": list_service_catalog_tree(
                source="viyar",
                include_inactive=False,
            ),
            "fallback_only_import": fallback_only_import,
            "deactivated_missing": bool(deactivate_missing and not fallback_only_import),
            "folder_count": sum(
                1
                for record in records
                if record["item_type"] == "folder"
                and record["parent_external_code"] is not None
            ),
            "imported_count": len(records),
            "service_count": sum(
                1
                for record in records
                if record["item_type"] == "service"
            ),
            "deactivated_suspicious_count": deactivated_suspicious_count,
        }

    finally:

        db.close()


def list_service_catalog_items(
    source: str = "viyar",
    include_inactive: bool = False,
    user_id: str | None = None,
    owner_user_id: str | None = None,
) -> list[dict]:

    db = SessionLocal()

    try:

        query = db.query(ServiceCatalogItemModel).filter(
            ServiceCatalogItemModel.source == source,
        )

        if source == "manual":
            query = query.filter(
                ServiceCatalogItemModel.owner_user_id == owner_user_id,
            )

        if not include_inactive:
            query = query.filter(
                ServiceCatalogItemModel.is_active.is_(True),
            )

        items = (
            query.order_by(
                ServiceCatalogItemModel.folder_path.asc(),
                ServiceCatalogItemModel.sort_order.asc(),
                ServiceCatalogItemModel.name.asc(),
            )
            .all()
        )

        user_prices_by_item_id = {}

        if user_id:
            user_prices = (
                db.query(UserServiceCatalogPriceModel)
                .filter(UserServiceCatalogPriceModel.user_id == user_id)
                .all()
            )
            user_prices_by_item_id = {
                price.service_catalog_item_id: price
                for price in user_prices
            }

        return [
            _serialize_service_catalog_item(
                item,
                user_price=user_prices_by_item_id.get(item.id),
            )
            for item in items
        ]

    finally:

        db.close()


def list_service_catalog_tree(
    source: str = "viyar",
    include_inactive: bool = False,
    user_id: str | None = None,
    owner_user_id: str | None = None,
) -> list[dict]:

    items = list_service_catalog_items(
        source=source,
        include_inactive=include_inactive,
        user_id=user_id,
        owner_user_id=owner_user_id,
    )

    nodes = {
        item["external_code"]: {
            **item,
            "children": [],
        }
        for item in items
    }

    roots: list[dict] = []

    for item in items:

        node = nodes[item["external_code"]]
        parent_code = item["parent_external_code"]

        if parent_code and parent_code in nodes:
            nodes[parent_code]["children"].append(node)
        else:
            roots.append(node)

    def _sort_nodes(node: dict):
        node["children"].sort(
            key=lambda child: (
                child["sort_order"],
                child["name"],
            )
        )
        for child in node["children"]:
            _sort_nodes(child)

    for root in roots:
        _sort_nodes(root)

    roots.sort(
        key=lambda item: (
            item["sort_order"],
            item["name"],
        )
    )

    return roots


def list_calculable_service_catalog_items(
    source: str | None = None,
    user_id: str | None = None,
    owner_user_id: str | None = None,
) -> list[dict]:

    db = SessionLocal()

    try:

        query = db.query(ServiceCatalogItemModel).filter(
            ServiceCatalogItemModel.item_type == "service",
            ServiceCatalogItemModel.is_active.is_(True),
            ServiceCatalogItemModel.is_calculable.is_(True),
        )

        if source:
            query = query.filter(
                ServiceCatalogItemModel.source == source,
            )

        if source == "manual":
            query = query.filter(
                ServiceCatalogItemModel.owner_user_id == owner_user_id,
            )

        items = (
            query.order_by(
                ServiceCatalogItemModel.folder_path.asc(),
                ServiceCatalogItemModel.sort_order.asc(),
                ServiceCatalogItemModel.name.asc(),
            )
            .all()
        )

        user_prices_by_item_id = {}

        if user_id:
            user_prices = (
                db.query(UserServiceCatalogPriceModel)
                .filter(UserServiceCatalogPriceModel.user_id == user_id)
                .all()
            )
            user_prices_by_item_id = {
                price.service_catalog_item_id: price
                for price in user_prices
            }

        return [
            _serialize_service_catalog_item(
                item,
                user_price=user_prices_by_item_id.get(item.id),
            )
            for item in items
        ]

    finally:

        db.close()


def update_service_catalog_item(
    item_id: str,
    unit: str | None,
    base_price: float | None,
    is_calculable: bool,
    is_active: bool,
) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(ServiceCatalogItemModel)
            .filter(ServiceCatalogItemModel.id == item_id)
            .first()
        )

        if not item:
            return None

        if item.item_type != "service":
            return None

        item.unit = unit.strip() if isinstance(unit, str) and unit.strip() else None
        item.base_price = base_price
        item.is_calculable = is_calculable
        item.is_active = is_active

        db.commit()
        db.refresh(item)

        return _serialize_service_catalog_item(item)

    finally:

        db.close()


def create_manual_service_catalog_item(
    user_id: str,
    name: str,
    article: str | None,
    description: str | None,
    unit: str | None,
    base_price: float | None,
    is_calculable: bool,
    is_active: bool,
) -> dict:

    db = SessionLocal()

    try:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Manual service name is required")
        article_value = article.strip() if isinstance(article, str) and article.strip() else None
        description_value = (
            description.strip()
            if isinstance(description, str) and description.strip()
            else None
        )
        unit_value = unit.strip() if isinstance(unit, str) and unit.strip() else None
        slug_base = re.sub(r"[^a-z0-9]+", "-", normalized_name.lower()).strip("-") or "service"
        external_code = f"manual-{uuid.uuid4().hex}"
        next_sort_order = (
            db.query(ServiceCatalogItemModel)
            .filter(ServiceCatalogItemModel.source == "manual")
            .filter(ServiceCatalogItemModel.owner_user_id == user_id)
            .count()
        )

        item = ServiceCatalogItemModel(
            source="manual",
            external_code=external_code,
            parent_external_code=None,
            owner_user_id=user_id,
            name=normalized_name,
            slug=f"{slug_base}-{external_code[-6:]}",
            item_type="service",
            folder_path="manual-services",
            description=description_value,
            article=article_value,
            unit=unit_value,
            base_price=base_price,
            currency="UAH" if base_price is not None else None,
            source_url=None,
            is_calculable=is_calculable,
            sort_order=next_sort_order,
            is_active=is_active,
            price_sync_status="manual",
            price_source_label="manual",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        return _serialize_service_catalog_item(item)
    finally:
        db.close()


def update_manual_service_catalog_item(
    user_id: str,
    item_id: str,
    name: str,
    article: str | None,
    description: str | None,
    unit: str | None,
    base_price: float | None,
    is_calculable: bool,
    is_active: bool,
) -> dict | None:

    db = SessionLocal()

    try:
        item = (
            db.query(ServiceCatalogItemModel)
            .filter(ServiceCatalogItemModel.id == item_id)
            .filter(ServiceCatalogItemModel.source == "manual")
            .filter(ServiceCatalogItemModel.owner_user_id == user_id)
            .first()
        )

        if not item:
            return None

        normalized_name = name.strip()
        if not normalized_name:
            return None

        item.name = normalized_name
        item.article = article.strip() if isinstance(article, str) and article.strip() else None
        item.description = (
            description.strip()
            if isinstance(description, str) and description.strip()
            else None
        )
        item.unit = unit.strip() if isinstance(unit, str) and unit.strip() else None
        item.base_price = base_price
        item.currency = "UAH" if base_price is not None else None
        item.is_calculable = is_calculable
        item.is_active = is_active
        item.price_sync_status = "manual"
        item.price_source_label = "manual"

        db.commit()
        db.refresh(item)

        return _serialize_service_catalog_item(item)
    finally:
        db.close()


def sync_viyar_service_prices(
    user_id: str,
    cookie_override: str | None = None,
    use_remote: bool = True,
) -> dict:

    db = SessionLocal()

    try:

        service_items = (
            db.query(ServiceCatalogItemModel)
            .filter(ServiceCatalogItemModel.source == "viyar")
            .filter(ServiceCatalogItemModel.item_type == "service")
            .all()
        )

        serialized_items = [
            _serialize_service_catalog_item(item)
            for item in service_items
        ]

        result = fetch_viyar_service_price_updates(
            serialized_items,
            use_remote=use_remote,
            cookie_override=cookie_override,
        )

        priced_count = 0
        skipped_count = 0
        now = datetime.utcnow()

        updates_by_code = {
            item["external_code"]: item
            for item in result["updates"]
        }
        user_prices = (
            db.query(UserServiceCatalogPriceModel)
            .filter(UserServiceCatalogPriceModel.user_id == user_id)
            .all()
        )
        user_price_by_item_id = {
            price.service_catalog_item_id: price
            for price in user_prices
        }

        for item in service_items:
            update = updates_by_code.get(item.external_code)
            price_row = user_price_by_item_id.get(item.id)

            if not price_row:
                price_row = UserServiceCatalogPriceModel(
                    user_id=user_id,
                    service_catalog_item_id=item.id,
                )
                db.add(price_row)
                user_price_by_item_id[item.id] = price_row

            if not update:
                price_row.last_synced_at = now
                price_row.price_sync_status = "skipped"
                price_row.price_source_label = None
                skipped_count += 1
                continue

            price_row.last_synced_at = now
            price_row.price_sync_status = update["status"]
            price_row.price_source_label = update.get("price_source_label")

            if update["status"] == "priced":
                price_row.base_price = update["base_price"]
                price_row.currency = update.get("currency") or item.currency or "UAH"
                if update.get("article"):
                    item.article = update["article"]
                priced_count += 1
            else:
                price_row.base_price = None
                price_row.currency = None
                if update.get("article"):
                    item.article = update["article"]
                skipped_count += 1

        db.commit()

        return {
            "auth_required": result["auth_required"],
            "items": list_service_catalog_tree(
                source="viyar",
                include_inactive=False,
                user_id=user_id,
            ),
            "priced_count": priced_count,
            "skipped_count": skipped_count,
            "source": result.get("source", "viyar"),
        }

    finally:

        db.close()


def list_users_needing_viyar_service_price_sync(
    stale_hours: int = 24,
    limit: int = 10,
) -> list[dict]:

    db = SessionLocal()

    try:

        cutoff = datetime.utcnow() - timedelta(hours=max(1, stale_hours))
        rows = (
            db.query(
                UserModel.id,
                UserModel.email,
                UserModel.viyar_email,
                UserModel.viyar_password_secret,
                UserModel.viyar_cookie,
                func.max(UserServiceCatalogPriceModel.last_synced_at).label("last_synced_at"),
            )
            .outerjoin(
                UserServiceCatalogPriceModel,
                UserServiceCatalogPriceModel.user_id == UserModel.id,
            )
            .filter(UserModel.is_active.is_(True))
            .filter(
                (UserModel.viyar_cookie.isnot(None))
                | and_(
                    UserModel.viyar_email.isnot(None),
                    UserModel.viyar_password_secret.isnot(None),
                )
            )
            .group_by(
                UserModel.id,
                UserModel.email,
                UserModel.viyar_email,
                UserModel.viyar_password_secret,
                UserModel.viyar_cookie,
            )
            .having(
                (func.max(UserServiceCatalogPriceModel.last_synced_at).is_(None))
                | (func.max(UserServiceCatalogPriceModel.last_synced_at) <= cutoff)
            )
            .order_by(func.max(UserServiceCatalogPriceModel.last_synced_at).asc().nullsfirst(), UserModel.email.asc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": row.id,
                "email": row.email,
                "viyar_email": row.viyar_email,
                "viyar_password_secret": row.viyar_password_secret,
                "viyar_cookie": row.viyar_cookie,
                "last_synced_at": row.last_synced_at,
            }
            for row in rows
        ]

    finally:

        db.close()
