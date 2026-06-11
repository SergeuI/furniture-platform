from collections import defaultdict

from database.models.fitting import (
    FittingModel,
)
from database.models.material import (
    MaterialModel,
)
from database.models.material_price import (
    MaterialPriceModel,
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

        return sorted(
            {
                row[0]
                for row in [*material_city_rows, *fitting_city_rows]
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

        return [
            {
                "id": str(item.id),
                "article": item.article,
                "name": item.name,
                "category": item.category,
                "image": item.image,
                "source_url": item.source_url,
                "tg_file_id": item.tg_file_id,
                "is_default": bool(item.is_default),
                "prices": [
                    {
                        "city": price.city,
                        "price": _normalize_price_value(price.price),
                    }
                    for price in sorted(
                        prices_by_article.get(item.article, []),
                        key=lambda row: ((row.city or ""), row.id),
                    )
                ],
                "current_price": next(
                    (
                        _normalize_price_value(price.price)
                        for price in prices_by_article.get(item.article, [])
                        if city and price.city == city
                    ),
                    None,
                ),
            }
            for item in materials
        ]

    finally:

        db.close()


def list_fittings(
    search: str | None = None,
    city: str | None = None,
) -> list[dict]:

    db = SessionLocal()

    try:

        query = db.query(FittingModel)

        if city:
            query = query.filter(
                FittingModel.city == city,
            )

        if search:
            search_value = f"%{search.strip()}%"
            query = query.filter(
                FittingModel.name.ilike(search_value) |
                FittingModel.article.ilike(search_value) |
                FittingModel.code.ilike(search_value)
            )

        fittings = (
            query.order_by(
                FittingModel.code.asc(),
                FittingModel.city.asc(),
                FittingModel.name.asc(),
            )
            .all()
        )

        return [
            {
                "id": str(item.id),
                "city": item.city,
                "code": item.code,
                "article": item.article,
                "name": item.name,
                "price": item.price,
                "stock": item.stock,
            }
            for item in fittings
        ]

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

        db.commit()
        db.refresh(row)

        return {
            "article": row.article,
            "city": row.city,
            "price": row.price,
        }

    finally:

        db.close()
