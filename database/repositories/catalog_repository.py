from database.session import (
    SessionLocal
)

from database.models.catalog_item import (
    CatalogItemModel
)


DEFAULT_CATALOG_ITEMS = {
    "project_type": [
        "dresser",
        "wardrobe",
        "cabinet",
        "kitchen",
        "drawer_unit"
    ],
    "slide_type": [
        "tandem",
        "movento",
        "telescopic"
    ],
    "bottom_type": [
        "hdf",
        "hdf_3",
        "dsp",
        "dsp_18"
    ],
    "material_thickness": [
        "16",
        "18",
        "19"
    ],
    "edge_banding": [
        "abs_0_5",
        "abs_1",
        "abs_2",
        "pvc_0_5",
        "pvc_1",
        "pvc_2"
    ],
    "handle_position": [
        "top",
        "center",
        "bottom",
        "left",
        "right",
        "integrated"
    ]
}


def _to_int_values(values: list[str]) -> list[int]:

    result = []

    for value in values:

        try:

            result.append(
                int(value)
            )

        except ValueError:

            continue

    return result


# =====================================================
# SEED CATALOG ITEMS
# =====================================================

def seed_default_catalog_items():

    db = SessionLocal()

    try:

        for category, values in DEFAULT_CATALOG_ITEMS.items():

            for sort_order, value in enumerate(values):

                existing_item = (

                    db.query(CatalogItemModel)

                    .filter(

                        CatalogItemModel.category == category,

                        CatalogItemModel.value == value
                    )

                    .first()
                )

                if existing_item:

                    continue

                db.add(

                    CatalogItemModel(

                        category=category,

                        value=value,

                        sort_order=sort_order,

                        is_active=True
                    )
                )

        db.commit()

    finally:

        db.close()


# =====================================================
# LIST CATALOG VALUES
# =====================================================

def list_catalog_values(

    category: str
) -> list[str]:

    db = SessionLocal()

    try:

        items = (

            db.query(CatalogItemModel)

            .filter(

                CatalogItemModel.category == category,

                CatalogItemModel.is_active.is_(True)
            )

            .order_by(

                CatalogItemModel.sort_order.asc(),

                CatalogItemModel.value.asc()
            )

            .all()
        )

        return [
            item.value
            for item in items
        ]

    finally:

        db.close()


# =====================================================
# GET SPECIFICATION CATALOG
# =====================================================

def get_specification_catalog() -> dict:

    db = SessionLocal()

    try:

        items = (

            db.query(CatalogItemModel)

            .filter(
                CatalogItemModel.is_active.is_(True)
            )

            .order_by(

                CatalogItemModel.category.asc(),

                CatalogItemModel.sort_order.asc(),

                CatalogItemModel.value.asc()
            )

            .all()
        )

        values_by_category = {
            category: []
            for category in DEFAULT_CATALOG_ITEMS
        }

        for item in items:

            if item.category not in values_by_category:

                continue

            values_by_category[item.category].append(item.value)

        return {
            "project_types": values_by_category["project_type"],
            "slide_types": values_by_category["slide_type"],
            "bottom_types": values_by_category["bottom_type"],
            "material_thicknesses": _to_int_values(
                values_by_category["material_thickness"]
            ),
            "edge_bandings": values_by_category["edge_banding"],
            "handle_positions": values_by_category["handle_position"]
        }

    finally:

        db.close()
