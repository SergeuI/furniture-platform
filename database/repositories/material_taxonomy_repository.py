from __future__ import annotations

import re
import unicodedata

from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError

from database.models.material import MaterialModel
from database.models.material_taxonomy import (
    MaterialCategoryModel,
    MaterialManufacturerAliasModel,
    MaterialManufacturerModel,
)
from database.models.user import UserModel
from database.session import SessionLocal


def _normalize_text(value: str | None) -> str | None:
    normalized = " ".join(str(value or "").split()).strip()
    return normalized or None


def _normalize_identity_text(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None

    normalized = unicodedata.normalize("NFKC", normalized).casefold()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _normalize_code(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None

    normalized = normalized.casefold()
    normalized = re.sub(r"[^a-z0-9а-яіїєґ]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or None


_CATEGORY_CODE_TRANSLITERATION_MAP = str.maketrans({
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "h",
    "ґ": "g",
    "д": "d",
    "е": "e",
    "є": "ie",
    "ж": "zh",
    "з": "z",
    "и": "y",
    "і": "i",
    "ї": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ь": "",
    "ю": "iu",
    "я": "ia",
})


def _slugify_code(value: str | None) -> str | None:
    normalized = _normalize_identity_text(value)
    if not normalized:
        return None

    transliterated = normalized.translate(_CATEGORY_CODE_TRANSLITERATION_MAP)
    transliterated = unicodedata.normalize("NFKD", transliterated)
    transliterated = transliterated.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", transliterated.casefold())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or None


def _generate_unique_category_code(db, name: str, *, excluded_item_id: int | None = None) -> str:
    base_code = _slugify_code(name) or "category"
    candidate = base_code
    suffix = 2

    while True:
        query = db.query(MaterialCategoryModel.id).filter(MaterialCategoryModel.code == candidate)
        if excluded_item_id is not None:
            query = query.filter(MaterialCategoryModel.id != int(excluded_item_id))
        if query.first() is None:
            return candidate
        candidate = f"{base_code}_{suffix}"
        suffix += 1


def _generate_unique_manufacturer_code(db, value: str, *, excluded_item_id: int | None = None) -> str:
    base_code = _normalize_code(value) or _slugify_code(value) or "manufacturer"
    candidate = base_code
    suffix = 2

    while True:
        query = db.query(MaterialManufacturerModel.id).filter(MaterialManufacturerModel.code == candidate)
        if excluded_item_id is not None:
            query = query.filter(MaterialManufacturerModel.id != int(excluded_item_id))
        if query.first() is None:
            return candidate
        candidate = f"{base_code}_{suffix}"
        suffix += 1


def _serialize_category_owner(user: UserModel | None) -> dict | None:
    if not user:
        return None

    login = _normalize_text(user.username)
    display_name = login or _normalize_text(user.email)

    return {
        "id": str(user.id),
        "display_name": display_name,
        "login": login,
        "email": user.email,
    }


def _load_category_owner_profiles(db, owner_user_ids: list[str | None]) -> dict[str, dict]:
    normalized_owner_user_ids = [
        str(owner_user_id).strip()
        for owner_user_id in owner_user_ids
        if str(owner_user_id or "").strip()
    ]

    if not normalized_owner_user_ids:
        return {}

    users = (
        db.query(UserModel)
        .filter(UserModel.id.in_(normalized_owner_user_ids))
        .all()
    )

    return {
        str(user.id): _serialize_category_owner(user)
        for user in users
    }


def _serialize_category(
    item: MaterialCategoryModel,
    owner_profile: dict | None = None,
    *,
    item_count: int = 0,
) -> dict:
    return {
        "id": int(item.id),
        "code": item.code,
        "name": item.name,
        "description": item.description,
        "image_url": item.image_url,
        "owner_user_id": item.owner_user_id,
        "owner_display_name": (owner_profile or {}).get("display_name"),
        "owner_login": (owner_profile or {}).get("login"),
        "owner_email": (owner_profile or {}).get("email"),
        "parent_id": int(item.parent_id) if item.parent_id is not None else None,
        "sort_order": int(item.sort_order or 0),
        "is_active": bool(item.is_active),
        "is_system": bool(item.is_system),
        "item_count": int(item_count or 0),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _serialize_manufacturer(item: MaterialManufacturerModel, owner_profile: dict | None = None) -> dict:
    return {
        "id": int(item.id),
        "name": item.name,
        "normalized_name": item.normalized_name,
        "code": item.code,
        "website_url": item.website_url,
        "logo_url": item.logo_url,
        "owner_user_id": item.owner_user_id,
        "owner_display_name": (owner_profile or {}).get("display_name"),
        "owner_login": (owner_profile or {}).get("login"),
        "owner_email": (owner_profile or {}).get("email"),
        "is_active": bool(item.is_active),
        "is_system": bool(item.is_system),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def list_material_categories(
    *,
    active_only: bool = True,
    viewer_user_id: str | None = None,
    viewer_role: str | None = None,
    include_private_categories: bool = False,
) -> list[dict]:
    db = SessionLocal()
    try:
        query = db.query(MaterialCategoryModel)
        if active_only:
            query = query.filter(MaterialCategoryModel.is_active.is_(True))
        is_admin = str(viewer_role or "").strip().lower() == "admin"
        normalized_viewer_id = str(viewer_user_id or "").strip()
        if include_private_categories:
            if is_admin:
                pass
            elif normalized_viewer_id:
                query = query.filter(
                    or_(
                        MaterialCategoryModel.is_system.is_(True),
                        MaterialCategoryModel.owner_user_id == normalized_viewer_id,
                    ),
                )
            else:
                query = query.filter(MaterialCategoryModel.is_system.is_(True))
        else:
            query = query.filter(MaterialCategoryModel.is_system.is_(True))
        rows = query.order_by(
            MaterialCategoryModel.is_system.desc(),
            MaterialCategoryModel.parent_id.asc().nullsfirst(),
            MaterialCategoryModel.sort_order.asc(),
            MaterialCategoryModel.created_at.asc(),
            MaterialCategoryModel.name.asc(),
            MaterialCategoryModel.code.asc(),
            MaterialCategoryModel.id.asc(),
        ).all()
        category_counts = {
            str(category_code or "").strip().lower(): int(item_count or 0)
            for category_code, item_count in (
                db.query(
                    func.lower(MaterialModel.category),
                    func.count(MaterialModel.id),
                )
                .filter(MaterialModel.category.isnot(None))
                .group_by(func.lower(MaterialModel.category))
                .all()
            )
            if str(category_code or "").strip()
        }
        owner_profiles = _load_category_owner_profiles(
            db,
            [item.owner_user_id for item in rows],
        )
        return [
            _serialize_category(
                item,
                owner_profiles.get(str(item.owner_user_id or "")),
                item_count=category_counts.get(str(item.code or "").strip().lower(), 0),
            )
            for item in rows
        ]
    finally:
        db.close()


def get_material_category_row_by_id(item_id: str | int) -> MaterialCategoryModel | None:
    db = SessionLocal()
    try:
        return db.get(MaterialCategoryModel, int(item_id))
    finally:
        db.close()


def get_material_category_by_id(
    item_id: str | int,
    *,
    viewer_user_id: str | None = None,
    viewer_role: str | None = None,
) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(MaterialCategoryModel, int(item_id))
        if not item:
            return None

        is_admin = str(viewer_role or "").strip().lower() == "admin"
        normalized_viewer_id = str(viewer_user_id or "").strip()
        if not is_admin and not bool(item.is_system) and str(item.owner_user_id or "").strip() != normalized_viewer_id:
            return None

        owner_profile = None
        if item.owner_user_id:
            owner_profile = _load_category_owner_profiles(db, [item.owner_user_id]).get(str(item.owner_user_id))

        return _serialize_category(item, owner_profile)
    finally:
        db.close()


def create_material_category(
    *,
    code: str | None = None,
    name: str,
    description: str | None = None,
    image_url: str | None = None,
    owner_user_id: str | None = None,
    parent_id: int | None = None,
    sort_order: int = 0,
    is_active: bool = True,
    is_system: bool = True,
) -> dict | None:
    db = SessionLocal()
    try:
        normalized_name = _normalize_text(name)
        if not normalized_name:
            return None

        normalized_code = _normalize_code(code)
        if not normalized_code:
            normalized_code = _generate_unique_category_code(db, normalized_name)
        else:
            normalized_code = _generate_unique_category_code(db, normalized_code)

        item = MaterialCategoryModel(
            code=normalized_code,
            name=normalized_name,
            description=_normalize_text(description),
            image_url=_normalize_text(image_url),
            owner_user_id=_normalize_text(owner_user_id),
            parent_id=int(parent_id) if parent_id is not None else None,
            sort_order=int(sort_order or 0),
            is_active=bool(is_active),
            is_system=bool(is_system),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        owner_profile = None
        if item.owner_user_id:
            owner_profile = _load_category_owner_profiles(db, [item.owner_user_id]).get(str(item.owner_user_id))
        return _serialize_category(item, owner_profile)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def update_material_category(
    item_id: str | int,
    *,
    name: str | None = None,
    description: str | None = None,
    image_url: str | None = None,
    parent_id: int | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
    is_system: bool | None = None,
) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(MaterialCategoryModel, int(item_id))
        if not item:
            return None

        if name is not None:
            normalized_name = _normalize_text(name)
            if normalized_name:
                item.name = normalized_name

        if description is not None:
            item.description = _normalize_text(description)

        if image_url is not None:
            item.image_url = _normalize_text(image_url)

        if parent_id is not None:
            item.parent_id = int(parent_id)

        if sort_order is not None:
            item.sort_order = int(sort_order or 0)

        if is_active is not None:
            item.is_active = bool(is_active)

        if is_system is not None:
            item.is_system = bool(is_system)

        db.commit()
        db.refresh(item)
        owner_profile = None
        if item.owner_user_id:
            owner_profile = _load_category_owner_profiles(db, [item.owner_user_id]).get(str(item.owner_user_id))
        return _serialize_category(item, owner_profile)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def count_materials_in_category(category_code: str) -> int:
    db = SessionLocal()
    try:
        return int(
            db.query(func.count(MaterialModel.id))
            .filter(MaterialModel.category == category_code)
            .scalar()
            or 0,
        )
    finally:
        db.close()


def delete_material_category(item_id: str | int) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(MaterialCategoryModel, int(item_id))
        if not item:
            return None

        serialized = _serialize_category(item)
        db.delete(item)
        db.commit()
        return serialized
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def count_materials_by_manufacturer(manufacturer_id: str | int) -> int:
    db = SessionLocal()
    try:
        return int(
            db.query(func.count(MaterialModel.id))
            .filter(MaterialModel.manufacturer_id == int(manufacturer_id))
            .scalar()
            or 0,
        )
    finally:
        db.close()


def delete_material_manufacturer(item_id: str | int) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(MaterialManufacturerModel, int(item_id))
        if not item:
            return None

        serialized = _serialize_manufacturer(item)
        db.delete(item)
        db.commit()
        return serialized
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def list_material_manufacturers(
    *,
    active_only: bool = True,
    viewer_user_id: str | None = None,
    viewer_role: str | None = None,
    include_private_manufacturers: bool = False,
) -> list[dict]:
    db = SessionLocal()
    try:
        query = db.query(MaterialManufacturerModel)
        if active_only:
            query = query.filter(MaterialManufacturerModel.is_active.is_(True))
        is_admin = str(viewer_role or "").strip().lower() == "admin"
        normalized_viewer_id = str(viewer_user_id or "").strip()
        if include_private_manufacturers:
            if is_admin:
                pass
            elif normalized_viewer_id:
                query = query.filter(
                    or_(
                        MaterialManufacturerModel.is_system.is_(True),
                        MaterialManufacturerModel.owner_user_id == normalized_viewer_id,
                    ),
                )
            else:
                query = query.filter(MaterialManufacturerModel.is_system.is_(True))
        else:
            query = query.filter(MaterialManufacturerModel.is_system.is_(True))
        rows = query.order_by(
            MaterialManufacturerModel.is_system.desc(),
            MaterialManufacturerModel.name.asc(),
            MaterialManufacturerModel.normalized_name.asc(),
            MaterialManufacturerModel.code.asc().nullslast(),
            MaterialManufacturerModel.id.asc(),
        ).all()
        owner_profiles = _load_category_owner_profiles(
            db,
            [item.owner_user_id for item in rows],
        )
        return [_serialize_manufacturer(item, owner_profiles.get(str(item.owner_user_id or ""))) for item in rows]
    finally:
        db.close()


def get_material_manufacturer_by_id(
    item_id: str | int,
    *,
    viewer_user_id: str | None = None,
    viewer_role: str | None = None,
) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(MaterialManufacturerModel, int(item_id))
        if not item:
            return None

        is_admin = str(viewer_role or "").strip().lower() == "admin"
        normalized_viewer_id = str(viewer_user_id or "").strip()
        if not is_admin and not bool(item.is_system) and str(item.owner_user_id or "").strip() != normalized_viewer_id:
            return None

        owner_profile = None
        if item.owner_user_id:
            owner_profile = _load_category_owner_profiles(db, [item.owner_user_id]).get(str(item.owner_user_id))

        return _serialize_manufacturer(item, owner_profile)
    finally:
        db.close()


def _upsert_manufacturer_alias(
    db,
    *,
    manufacturer_id: int,
    alias: str,
    source: str | None = None,
) -> None:
    normalized_alias = _normalize_identity_text(alias)
    if not normalized_alias:
        return

    existing = (
        db.query(MaterialManufacturerAliasModel)
        .filter(MaterialManufacturerAliasModel.normalized_alias == normalized_alias)
        .first()
    )
    if existing:
        if int(existing.manufacturer_id) != int(manufacturer_id):
            return
        existing.alias = _normalize_text(alias) or existing.alias
        if source is not None:
            existing.source = _normalize_text(source)
        return

    db.add(
        MaterialManufacturerAliasModel(
            manufacturer_id=int(manufacturer_id),
            alias=_normalize_text(alias) or alias,
            normalized_alias=normalized_alias,
            source=_normalize_text(source),
        )
    )


def create_material_manufacturer(
    *,
    name: str,
    code: str | None = None,
    website_url: str | None = None,
    logo_url: str | None = None,
    owner_user_id: str | None = None,
    is_active: bool = True,
    is_system: bool = True,
) -> dict | None:
    db = SessionLocal()
    try:
        normalized_name = _normalize_text(name)
        normalized_identity = _normalize_identity_text(name)
        if not normalized_name or not normalized_identity:
            return None

        item = MaterialManufacturerModel(
            name=normalized_name,
            normalized_name=normalized_identity,
            code=_generate_unique_manufacturer_code(
                db,
                _normalize_code(code) or normalized_name,
            ),
            website_url=_normalize_text(website_url),
            logo_url=_normalize_text(logo_url),
            owner_user_id=_normalize_text(owner_user_id),
            is_active=bool(is_active),
            is_system=bool(is_system),
        )
        db.add(item)
        db.flush()
        _upsert_manufacturer_alias(db, manufacturer_id=int(item.id), alias=normalized_name, source="create")
        db.commit()
        db.refresh(item)
        owner_profile = None
        if item.owner_user_id:
            owner_profile = _load_category_owner_profiles(db, [item.owner_user_id]).get(str(item.owner_user_id))
        return _serialize_manufacturer(item, owner_profile)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()


def update_material_manufacturer(
    item_id: str | int,
    *,
    name: str | None = None,
    code: str | None = None,
    website_url: str | None = None,
    logo_url: str | None = None,
    owner_user_id: str | None = None,
    is_active: bool | None = None,
    is_system: bool | None = None,
) -> dict | None:
    db = SessionLocal()
    try:
        item = db.get(MaterialManufacturerModel, int(item_id))
        if not item:
            return None

        previous_name = item.name

        if name is not None:
            normalized_name = _normalize_text(name)
            normalized_identity = _normalize_identity_text(name)
            if normalized_name and normalized_identity:
                item.name = normalized_name
                item.normalized_name = normalized_identity
                _upsert_manufacturer_alias(db, manufacturer_id=int(item.id), alias=normalized_name, source="update")
                if previous_name and previous_name != normalized_name:
                    _upsert_manufacturer_alias(db, manufacturer_id=int(item.id), alias=previous_name, source="legacy")

        if code is not None:
            normalized_code = _normalize_code(code)
            if normalized_code:
                item.code = _generate_unique_manufacturer_code(
                    db,
                    normalized_code,
                    excluded_item_id=item.id,
                )

        if website_url is not None:
            item.website_url = _normalize_text(website_url)

        if logo_url is not None:
            item.logo_url = _normalize_text(logo_url)

        if owner_user_id is not None:
            item.owner_user_id = _normalize_text(owner_user_id)

        if is_active is not None:
            item.is_active = bool(is_active)

        if is_system is not None:
            item.is_system = bool(is_system)

        db.commit()
        db.refresh(item)
        owner_profile = None
        if item.owner_user_id:
            owner_profile = _load_category_owner_profiles(db, [item.owner_user_id]).get(str(item.owner_user_id))
        return _serialize_manufacturer(item, owner_profile)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()
