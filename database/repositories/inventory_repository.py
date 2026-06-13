from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse

from database.models.fitting import (
    FittingModel,
)
from database.models.material import (
    MaterialModel,
)
from database.models.material_price import (
    MaterialPriceModel,
)
from database.models.user import (
    UserModel,
)
from database.session import (
    SessionLocal,
)


def _normalize_price_value(value) -> float | None:

    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        return float(value)

    normalized = str(value).strip().replace(" ", "").replace(",", ".")

    try:
        return float(normalized)
    except ValueError:
        return None


FITTING_GROUP_LABELS = {
    "fittings": "Фурнітура",
    "fasteners": "Метизна фурнітура",
}


FITTING_CATEGORY_DEFINITIONS = [
    {
        "code": "connectors_fasteners",
        "name": "З'єднувальна та кріпильна фурнітура",
        "group": "fasteners",
        "description": "Стяжки, шканти, куточки, саморізи та інші кріпильні елементи.",
        "icon_key": "blocks",
        "keywords": [
            "саморіз",
            "шуруп",
            "гвинт",
            "євровинт",
            "болт",
            "гайк",
            "шайб",
            "стяж",
            "конфірм",
            "шкант",
            "ламел",
            "дюб",
            "метиз",
            "кутник",
            "кріп",
            "screw",
            "confirmat",
            "bolt",
            "nut",
            "washer",
        ],
    },
    {
        "code": "drawer_slides",
        "name": "Висувні механізми",
        "group": "fittings",
        "description": "Направляючі та системи висування для шухляд.",
        "icon_key": "move-horizontal",
        "keywords": [
            "направ",
            "телескоп",
            "шухляд",
            "ящик",
            "роликова",
            "tandem",
            "slide",
            "drawer",
            "box",
        ],
    },
    {
        "code": "handles_hooks",
        "name": "Ручки та гачки",
        "group": "fittings",
        "description": "Ручки меблеві, гачки та декоративні елементи відкривання.",
        "icon_key": "wrench",
        "keywords": [
            "ручк",
            "гач",
            "handle",
            "hook",
        ],
    },
    {
        "code": "profiles_gola",
        "name": "Ручки-профіль, система Gola",
        "group": "fittings",
        "description": "Профільні ручки та системи Gola для фасадів.",
        "icon_key": "panel-top",
        "keywords": [
            "gola",
            "профіл",
            "profile",
        ],
    },
    {
        "code": "plinth_vents",
        "name": "Цоколі та вентиляційні решітки",
        "group": "fittings",
        "description": "Цоколі, решітки та комплектуючі нижньої бази меблів.",
        "icon_key": "layout-grid",
        "keywords": [
            "цокол",
            "решітк",
            "вент",
            "plinth",
            "grille",
            "vent",
        ],
    },
    {
        "code": "legs_wheels",
        "name": "Ніжки, ролики",
        "group": "fittings",
        "description": "Опори, ніжки та меблеві ролики.",
        "icon_key": "circle",
        "keywords": [
            "ніжк",
            "опор",
            "ролик",
            "колес",
            "leg",
            "wheel",
            "caster",
        ],
    },
    {
        "code": "locks_magnets",
        "name": "Замки, магніти, засувки",
        "group": "fittings",
        "description": "Замки, магніти та елементи фіксації фасадів.",
        "icon_key": "lock",
        "keywords": [
            "зам",
            "магніт",
            "засув",
            "lock",
            "magnet",
            "latch",
        ],
    },
    {
        "code": "wardrobe_systems",
        "name": "Меблеві труби та системи",
        "group": "fittings",
        "description": "Труби, рейлінги, торгові та гардеробні системи.",
        "icon_key": "pipe",
        "keywords": [
            "труб",
            "рейл",
            "гардероб",
            "торгов",
            "rail",
            "wardrobe",
            "closet",
        ],
    },
    {
        "code": "hinges",
        "name": "Навіси меблеві",
        "group": "fittings",
        "description": "Петлі, навіси та рейки для корпусних меблів.",
        "icon_key": "door-open",
        "keywords": [
            "петл",
            "навіс",
            "hinge",
            "lift",
        ],
    },
    {
        "code": "bathroom",
        "name": "Фурнітура для санвузлів",
        "group": "fittings",
        "description": "Фурнітура для сантехнічних перегородок та ванних кімнат.",
        "icon_key": "bath",
        "keywords": [
            "санвуз",
            "ванн",
            "сифон",
            "bath",
            "bathroom",
            "shower",
        ],
    },
    {
        "code": "packaging",
        "name": "Пакувальний матеріал",
        "group": "fasteners",
        "description": "Стретч, скотч та пакувальні матеріали.",
        "icon_key": "package",
        "keywords": [
            "стретч",
            "скотч",
            "пакув",
            "package",
            "tape",
        ],
    },
    {
        "code": "bed_components",
        "name": "Комплектуючі для ліжок",
        "group": "fittings",
        "description": "Каркаси, підйомні механізми та фурнітура для ліжок.",
        "icon_key": "bed",
        "keywords": [
            "ліж",
            "матрац",
            "bed",
            "slat",
        ],
    },
    {
        "code": "wardrobe_fillings",
        "name": "Гардеробне наповнення",
        "group": "fittings",
        "description": "Кошики, брючниці, мікроліфти та наповнення шаф.",
        "icon_key": "shirt",
        "keywords": [
            "кошик",
            "брюч",
            "мікроліфт",
            "гардероб",
            "basket",
            "wardrobe",
        ],
    },
    {
        "code": "other_fittings",
        "name": "Інша фурнітура",
        "group": "fittings",
        "description": "Позиції, які поки не віднесено до окремого типу.",
        "icon_key": "package",
        "keywords": [],
    },
    {
        "code": "other_fasteners",
        "name": "Інший кріпіж",
        "group": "fasteners",
        "description": "Інші кріпильні елементи та метизи.",
        "icon_key": "blocks",
        "keywords": [],
    },
]

FITTING_CATEGORY_MAP = {
    item["code"]: item
    for item in FITTING_CATEGORY_DEFINITIONS
}


def _normalize_fitting_value(value: str | None) -> str | None:

    if value is None:
        return None

    normalized = str(value).strip()

    return normalized or None


def _resolve_fitting_category(
    fitting_type: str | None,
    fitting_group: str | None,
    *values: str | None,
) -> dict:

    if fitting_type and fitting_type in FITTING_CATEGORY_MAP:
        item = FITTING_CATEGORY_MAP[fitting_type]
        return {
            **item,
            "group": fitting_group or item["group"],
        }

    haystack = " ".join(
        value.lower()
        for value in values
        if value
    )

    for item in FITTING_CATEGORY_DEFINITIONS:
        if any(keyword in haystack for keyword in item["keywords"]):
            return item

    fallback_code = "other_fasteners" if fitting_group == "fasteners" else "other_fittings"

    return FITTING_CATEGORY_MAP[fallback_code]


def _serialize_fitting(item: FittingModel) -> dict:

    category = _resolve_fitting_category(
        item.fitting_type,
        item.fitting_group,
        item.name,
        item.article,
        item.code,
        item.stock,
    )

    source_site = _detect_fitting_source_site(item.source_url)

    return {
        "id": str(item.id),
        "city": item.city,
        "code": item.code,
        "article": item.article,
        "name": item.name,
        "price": item.price,
        "stock": item.stock,
        "fitting_type": category["code"],
        "fitting_type_name": category["name"],
        "fitting_group": category["group"],
        "fitting_group_name": FITTING_GROUP_LABELS.get(category["group"], category["group"]),
        "fitting_description": category.get("description"),
        "image_url": item.image_url,
        "source_url": item.source_url,
        "source_site": source_site,
        "owner_user_id": item.owner_user_id,
        "is_system": bool(item.is_system),
        "is_active": bool(item.is_active),
        "sort_order": item.sort_order or 0,
    }


def _detect_fitting_source_site(source_url: str | None) -> str:

    if not source_url:
        return "manual"

    raw_value = str(source_url).strip()

    if not raw_value:
        return "manual"

    normalized_url = raw_value if "://" in raw_value else f"https://{raw_value}"

    try:
        parsed = urlparse(normalized_url)
        host = (parsed.netloc or parsed.path or "").lower()
        path = (parsed.path or "").lower()
    except Exception:
        host = raw_value.lower()
        path = raw_value.lower()

    haystack = f"{host} {path}"

    if "viyar" in haystack:
        return "viyar"

    if "kronas" in haystack:
        return "kronas"

    if "blum" in haystack or "mt" in haystack:
        return "blum"

    return "manual"


def list_fitting_categories(
    items: list[dict] | None = None,
    group: str | None = None,
) -> list[dict]:

    counts: dict[str, int] = defaultdict(int)

    for item in items or []:
        counts[item["fitting_type"]] += 1

    categories = []

    for category in FITTING_CATEGORY_DEFINITIONS:
        if group and category["group"] != group:
            continue

        categories.append(
            {
                "code": category["code"],
                "name": category["name"],
                "group": category["group"],
                "group_name": FITTING_GROUP_LABELS.get(category["group"], category["group"]),
                "description": category.get("description"),
                "icon_key": category.get("icon_key"),
                "item_count": counts.get(category["code"], 0),
            }
        )

    return categories


def list_material_categories() -> list[dict]:

    db = SessionLocal()

    try:

        rows = (
            db.query(
                MaterialModel.category,
            )
            .filter(MaterialModel.category.isnot(None))
            .distinct()
            .order_by(MaterialModel.category.asc())
            .all()
        )

        return [
            {
                "code": row[0],
                "name": row[0],
            }
            for row in rows
            if row[0]
        ]

    finally:

        db.close()


def list_inventory_cities() -> list[str]:

    db = SessionLocal()

    try:

        material_city_rows = (
            db.query(MaterialPriceModel.city)
            .filter(MaterialPriceModel.city.isnot(None))
            .distinct()
            .all()
        )
        fitting_city_rows = (
            db.query(FittingModel.city)
            .filter(FittingModel.city.isnot(None))
            .distinct()
            .all()
        )
        user_city_rows = (
            db.query(UserModel.city)
            .filter(UserModel.is_active.is_(True))
            .filter(UserModel.city.isnot(None))
            .distinct()
            .all()
        )

        return sorted(
            {
                row[0]
                for row in [*material_city_rows, *fitting_city_rows, *user_city_rows]
                if row[0]
            }
        )

    finally:

        db.close()


def list_materials(
    search: str | None = None,
    category: str | None = None,
    city: str | None = None,
) -> list[dict]:

    db = SessionLocal()

    try:

        query = db.query(MaterialModel)

        if category:
            query = query.filter(
                MaterialModel.category == category,
            )

        if search:
            search_value = f"%{search.strip()}%"
            query = query.filter(
                MaterialModel.name.ilike(search_value) |
                MaterialModel.article.ilike(search_value)
            )

        materials = (
            query.order_by(
                MaterialModel.category.asc(),
                MaterialModel.name.asc(),
                MaterialModel.article.asc(),
            )
            .all()
        )

        material_prices = db.query(MaterialPriceModel).all()
        prices_by_article: dict[str, list[MaterialPriceModel]] = defaultdict(list)

        for price in material_prices:
            prices_by_article[price.article].append(price)

        serialized_items = []

        for item in materials:
            sorted_prices = sorted(
                prices_by_article.get(item.article, []),
                key=lambda row: ((row.city or ""), row.id),
            )
            normalized_prices = [
                {
                    "city": price.city,
                    "price": _normalize_price_value(price.price),
                }
                for price in sorted_prices
            ]
            exact_price_row = next(
                (
                    price
                    for price in normalized_prices
                    if city and price["city"] == city and price["price"] is not None
                ),
                None,
            )
            fallback_price_row = next(
                (
                    price
                    for price in normalized_prices
                    if price["price"] is not None
                ),
                None,
            )
            active_price_row = exact_price_row or fallback_price_row

            serialized_items.append(
                {
                    "id": str(item.id),
                    "article": item.article,
                    "name": item.name,
                    "category": item.category,
                    "image": item.image,
                    "source_url": item.source_url,
                    "tg_file_id": item.tg_file_id,
                    "is_default": bool(item.is_default),
                    "has_cached_image": bool(item.image_cached_bytes),
                    "prices": normalized_prices,
                    "current_price": active_price_row["price"] if active_price_row else None,
                    "current_price_city": active_price_row["city"] if active_price_row else None,
                    "current_price_exact": bool(exact_price_row),
                }
            )

        return serialized_items

    finally:

        db.close()


def list_fittings(
    search: str | None = None,
    city: str | None = None,
    viewer_user_id: str | None = None,
    viewer_role: str | None = None,
    fitting_group: str | None = None,
    fitting_type: str | None = None,
    include_inactive: bool = False,
) -> list[dict]:

    db = SessionLocal()

    try:

        query = db.query(FittingModel)

        if city:
            query = query.filter(
                (FittingModel.city == city) |
                (FittingModel.city.is_(None))
            )

        if search:
            search_value = f"%{search.strip()}%"
            query = query.filter(
                FittingModel.name.ilike(search_value) |
                FittingModel.article.ilike(search_value) |
                FittingModel.code.ilike(search_value)
            )

        if not include_inactive:
            query = query.filter(FittingModel.is_active.is_(True))

        if viewer_role != "admin":
            visible_filter = FittingModel.is_system.is_(True)

            if viewer_user_id:
                visible_filter = visible_filter | (FittingModel.owner_user_id == str(viewer_user_id))

            query = query.filter(visible_filter)

        fittings = (
            query.order_by(
                FittingModel.fitting_group.asc().nullsfirst(),
                FittingModel.fitting_type.asc().nullsfirst(),
                FittingModel.sort_order.asc(),
                FittingModel.city.asc(),
                FittingModel.name.asc(),
                FittingModel.code.asc(),
            )
            .all()
        )

        serialized = [
            _serialize_fitting(item)
            for item in fittings
        ]

        if fitting_group:
            serialized = [
                item
                for item in serialized
                if item["fitting_group"] == fitting_group
            ]

        if fitting_type:
            serialized = [
                item
                for item in serialized
                if item["fitting_type"] == fitting_type
            ]

        return serialized

    finally:

        db.close()


def create_fitting(
    *,
    city: str | None,
    code: str | None,
    article: str | None,
    name: str,
    price: float | None,
    stock: str | None,
    fitting_type: str | None,
    fitting_group: str | None,
    image_url: str | None,
    source_url: str | None,
    owner_user_id: str | None,
    is_system: bool,
    is_active: bool,
    sort_order: int = 0,
) -> dict:

    db = SessionLocal()

    try:

        category = _resolve_fitting_category(
            fitting_type,
            fitting_group,
            name,
            article,
            code,
            stock,
        )

        item = FittingModel(
            city=_normalize_fitting_value(city),
            code=_normalize_fitting_value(code),
            article=_normalize_fitting_value(article),
            name=name.strip(),
            price=_normalize_price_value(price),
            stock=_normalize_fitting_value(stock),
            fitting_type=category["code"],
            fitting_group=category["group"],
            image_url=_normalize_fitting_value(image_url),
            source_url=_normalize_fitting_value(source_url),
            owner_user_id=_normalize_fitting_value(owner_user_id),
            is_system=bool(is_system),
            is_active=bool(is_active),
            sort_order=int(sort_order or 0),
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        return _serialize_fitting(item)

    finally:

        db.close()


def get_fitting_by_id(item_id: str | int) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(FittingModel)
            .filter(FittingModel.id == int(item_id))
            .first()
        )

        if not item:
            return None

        return _serialize_fitting(item)

    finally:

        db.close()


def update_fitting(
    *,
    item_id: str | int,
    city: str | None,
    code: str | None,
    article: str | None,
    name: str,
    price: float | None,
    stock: str | None,
    fitting_type: str | None,
    fitting_group: str | None,
    image_url: str | None,
    source_url: str | None,
    owner_user_id: str | None,
    is_system: bool,
    is_active: bool,
    sort_order: int = 0,
) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(FittingModel)
            .filter(FittingModel.id == int(item_id))
            .first()
        )

        if not item:
            return None

        category = _resolve_fitting_category(
            fitting_type,
            fitting_group,
            name,
            article,
            code,
            stock,
        )

        item.city = _normalize_fitting_value(city)
        item.code = _normalize_fitting_value(code)
        item.article = _normalize_fitting_value(article)
        item.name = name.strip()
        item.price = _normalize_price_value(price)
        item.stock = _normalize_fitting_value(stock)
        item.fitting_type = category["code"]
        item.fitting_group = category["group"]
        item.image_url = _normalize_fitting_value(image_url)
        item.source_url = _normalize_fitting_value(source_url)
        item.owner_user_id = _normalize_fitting_value(owner_user_id)
        item.is_system = bool(is_system)
        item.is_active = bool(is_active)
        item.sort_order = int(sort_order or 0)

        db.commit()
        db.refresh(item)

        return _serialize_fitting(item)

    finally:

        db.close()


def delete_fitting(item_id: str | int) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(FittingModel)
            .filter(FittingModel.id == int(item_id))
            .first()
        )

        if not item:
            return None

        serialized = _serialize_fitting(item)
        db.delete(item)
        db.commit()

        return serialized

    finally:

        db.close()


def get_material_by_article(article: str) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(MaterialModel)
            .filter(MaterialModel.article == article)
            .first()
        )

        if not item:
            return None

        return {
            "id": str(item.id),
            "article": item.article,
            "name": item.name,
            "category": item.category,
            "image": item.image,
            "source_url": item.source_url,
            "tg_file_id": item.tg_file_id,
            "is_default": bool(item.is_default),
            "has_cached_image": bool(item.image_cached_bytes),
            "image_cached_bytes": item.image_cached_bytes,
            "image_cached_content_type": item.image_cached_content_type,
        }

    finally:

        db.close()


def upsert_material(
    article: str,
    name: str,
    category: str,
    image: str | None = None,
    source_url: str | None = None,
    tg_file_id: str | None = None,
    is_default: bool | None = None,
) -> dict:

    db = SessionLocal()

    try:

        item = (
            db.query(MaterialModel)
            .filter(MaterialModel.article == article)
            .first()
        )

        if not item:
            item = MaterialModel(
                article=article,
            )
            db.add(item)

        item.name = name
        item.category = category
        item.image = image
        if source_url is not None:
            item.source_url = source_url
        if tg_file_id is not None:
            item.tg_file_id = tg_file_id
        if is_default is not None:
            item.is_default = bool(is_default)

        db.commit()
        db.refresh(item)

        return {
            "id": str(item.id),
            "article": item.article,
            "name": item.name,
            "category": item.category,
            "image": item.image,
            "source_url": item.source_url,
            "tg_file_id": item.tg_file_id,
            "is_default": bool(item.is_default),
            "has_cached_image": bool(item.image_cached_bytes),
            "image_cached_bytes": item.image_cached_bytes,
            "image_cached_content_type": item.image_cached_content_type,
        }

    finally:

        db.close()


def delete_material(article: str) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(MaterialModel)
            .filter(MaterialModel.article == article)
            .first()
        )

        if not item:
            return None

        if item.is_default:
            return {
                "deleted": False,
                "is_default": True,
            }

        (
            db.query(MaterialPriceModel)
            .filter(MaterialPriceModel.article == article)
            .delete(synchronize_session=False)
        )
        db.delete(item)
        db.commit()

        return {
            "deleted": True,
            "is_default": False,
        }

    finally:

        db.close()


def update_material_image_cache(
    article: str,
    image_bytes: bytes | None,
    content_type: str | None,
) -> dict | None:

    db = SessionLocal()

    try:

        item = (
            db.query(MaterialModel)
            .filter(MaterialModel.article == article)
            .first()
        )

        if not item:
            return None

        item.image_cached_bytes = image_bytes
        item.image_cached_content_type = content_type

        db.commit()
        db.refresh(item)

        return {
            "article": item.article,
            "has_cached_image": bool(item.image_cached_bytes),
            "image_cached_content_type": item.image_cached_content_type,
        }

    finally:

        db.close()


def upsert_material_price(
    article: str,
    city: str,
    price: float | None,
) -> dict:

    db = SessionLocal()

    try:

        row = (
            db.query(MaterialPriceModel)
            .filter(
                MaterialPriceModel.article == article,
                MaterialPriceModel.city == city,
            )
            .first()
        )

        if not row:
            row = MaterialPriceModel(
                article=article,
                city=city,
            )
            db.add(row)

        row.price = price
        row.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(row)

        return {
            "article": row.article,
            "city": row.city,
            "price": row.price,
            "updated_at": row.updated_at,
        }

    finally:

        db.close()


def list_material_price_refresh_targets(
    stale_hours: int = 24,
    limit: int = 20,
) -> list[dict]:

    db = SessionLocal()

    try:

        cutoff = datetime.utcnow() - timedelta(hours=max(1, stale_hours))
        stale_rows = (
            db.query(MaterialModel, MaterialPriceModel)
            .join(
                MaterialPriceModel,
                MaterialPriceModel.article == MaterialModel.article,
            )
            .filter(MaterialPriceModel.city.isnot(None))
            .filter(
                (MaterialPriceModel.updated_at.is_(None))
                | (MaterialPriceModel.updated_at <= cutoff)
            )
            .order_by(MaterialPriceModel.updated_at.asc().nullsfirst(), MaterialModel.article.asc())
            .limit(limit)
            .all()
        )
        targets = [
            {
                "article": material.article,
                "category": material.category or "dsp",
                "city": price.city,
                "source_url": material.source_url,
                "updated_at": price.updated_at,
            }
            for material, price in stale_rows
            if material.article and price.city
        ]

        if len(targets) >= limit:
            return targets[:limit]

        known_price_pairs = {
            (row.article, row.city)
            for row in db.query(MaterialPriceModel.article, MaterialPriceModel.city)
            .filter(MaterialPriceModel.article.isnot(None))
            .filter(MaterialPriceModel.city.isnot(None))
            .all()
        }
        queued_pairs = {
            (target["article"], target["city"])
            for target in targets
        }
        active_user_cities = [
            row[0]
            for row in db.query(UserModel.city)
            .filter(UserModel.is_active.is_(True))
            .filter(UserModel.city.isnot(None))
            .distinct()
            .order_by(UserModel.city.asc())
            .all()
            if row[0]
        ]
        materials = (
            db.query(MaterialModel)
            .filter(MaterialModel.article.isnot(None))
            .order_by(MaterialModel.article.asc())
            .all()
        )

        for city in active_user_cities:
            for material in materials:
                pair = (material.article, city)

                if pair in known_price_pairs or pair in queued_pairs:
                    continue

                targets.append(
                    {
                        "article": material.article,
                        "category": material.category or "dsp",
                        "city": city,
                        "source_url": material.source_url,
                        "updated_at": None,
                    }
                )
                queued_pairs.add(pair)

                if len(targets) >= limit:
                    return targets[:limit]

        return targets[:limit]

    finally:

        db.close()
