from __future__ import annotations

import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import fitting as fitting_models  # noqa: F401
from database.models import service_drilling_rule  # noqa: F401
from database.repositories import inventory_repository
from services.fitting_image_gallery_service import PreparedFittingGalleryImage


class FittingSourceCreateTests(unittest.TestCase):
    def test_source_creation_creates_canonical_product_and_links_technical_product(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "catalog.db"
            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            Base.metadata.create_all(bind=engine)
            session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

            with patch.object(inventory_repository, "SessionLocal", session_factory):
                with session_factory() as session:
                    session.add_all(
                        [
                            fitting_models.FittingManufacturerModel(
                                code="hettich",
                                name="Hettich",
                                is_active=True,
                                sort_order=1,
                            ),
                            fitting_models.FittingCategoryModel(
                                code="connectors_fasteners",
                                name="Connectors and fasteners",
                                is_active=True,
                                sort_order=1,
                            ),
                        ]
                    )
                    session.commit()

                created = inventory_repository.create_fitting(
                    city="kyiv",
                    code="SRC-1",
                    article="84628",
                    name="Дюбель під стяжку VB DU 321 (9021847) Hettich",
                    description="Parsed from source",
                    price=12.5,
                    stock="in stock",
                    source="viyar",
                    brand="Hettich",
                    fitting_type="connectors_fasteners",
                    fitting_group="fasteners",
                    image_url="https://example.com/image.jpg",
                    source_url="https://example.com/item",
                    source_payload_json='{"source":"viyar"}',
                    owner_user_id=None,
                    is_system=True,
                    is_active=True,
                    sort_order=0,
                    technical_product={
                        "article": "84628",
                        "code": "SRC-1",
                        "name": "Дюбель під стяжку VB DU 321 (9021847) Hettich",
                        "brand": "Hettich",
                        "description": "Parsed from source",
                        "manufacturer_id": None,
                        "series_id": None,
                        "category_id": None,
                        "is_active": True,
                    },
                    prepared_gallery_images=None,
                )

            with session_factory() as session:
                product_rows = session.execute(
                    text(
                        "SELECT id, article, code, name, brand, manufacturer_id, category_id, is_active "
                        "FROM fitting_products",
                    ),
                ).fetchall()
                fitting_rows = session.execute(
                    text("SELECT id, article, name, technical_product_id, source_url, is_system FROM fittings"),
                ).fetchall()

            self.assertEqual(len(product_rows), 1)
            self.assertEqual(product_rows[0][1], "84628")
            self.assertEqual(product_rows[0][3], "Дюбель під стяжку VB DU 321 (9021847) Hettich")
            self.assertEqual(product_rows[0][4], "Hettich")
            self.assertEqual(len(fitting_rows), 1)
            self.assertEqual(fitting_rows[0][1], "84628")
            self.assertEqual(fitting_rows[0][2], "Дюбель під стяжку VB DU 321 (9021847) Hettich")
            self.assertEqual(fitting_rows[0][3], product_rows[0][0])
            self.assertEqual(fitting_rows[0][4], "https://example.com/item")
            self.assertTrue(fitting_rows[0][5])
            self.assertEqual(created["technical_product_id"], product_rows[0][0])

    def test_source_creation_reuses_equivalent_source_row_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "catalog.db"
            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            Base.metadata.create_all(bind=engine)
            session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

            image_bytes = b"fake-image-bytes"
            gallery_image = PreparedFittingGalleryImage(
                sort_order=0,
                is_primary=True,
                source_url="https://cdn.example.com/fittings/main.jpg",
                image_bytes=image_bytes,
                content_type="image/jpeg",
                sha256=sha256(image_bytes).hexdigest(),
            )

            payload = dict(
                city="kyiv",
                code="SRC-1",
                article="61136",
                name="Дюбель під стяжку VB DU 321 (9021847) Hettich",
                description="Parsed from source",
                price=12.5,
                stock="in stock",
                source="viyar",
                brand="Hettich",
                fitting_type="connectors_fasteners",
                fitting_group="fasteners",
                image_url="https://cdn.example.com/fittings/main.jpg",
                source_url="https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                source_payload_json='{"source":"viyar"}',
                owner_user_id=None,
                is_system=True,
                is_active=True,
                sort_order=0,
                technical_product={
                    "article": "61136",
                    "code": "SRC-1",
                    "name": "Дюбель під стяжку VB DU 321 (9021847) Hettich",
                    "brand": "Hettich",
                    "description": "Parsed from source",
                    "manufacturer_id": None,
                    "series_id": None,
                    "category_id": None,
                    "is_active": True,
                },
                supplier_offer={
                    "supplier_id": 1,
                    "article": "61136",
                    "external_product_id": None,
                    "source_url": "https://viyar.ua/ua/catalog/dyubel_vvinchivaemyy_pod_styazhku_vb_du_321_9021847_hettich/",
                    "price": 12.5,
                    "currency": "UAH",
                    "unit": "шт",
                    "stock": "in stock",
                    "is_active": True,
                    "priority": 100,
                },
                prepared_gallery_images=[gallery_image],
            )

            with patch.object(inventory_repository, "SessionLocal", session_factory):
                with session_factory() as session:
                    session.add(fitting_models.SupplierModel(code="viyar", name="VIYAR", is_active=True))
                    session.commit()

                first = inventory_repository.create_fitting(**payload)
                second = inventory_repository.create_fitting(**payload)

            with session_factory() as session:
                fitting_count = session.execute(text("SELECT COUNT(*) FROM fittings")).fetchone()[0]
                product_count = session.execute(text("SELECT COUNT(*) FROM fitting_products")).fetchone()[0]
                image_count = session.execute(text("SELECT COUNT(*) FROM fitting_images")).fetchone()[0]
                offer_count = session.execute(text("SELECT COUNT(*) FROM fitting_supplier_offers")).fetchone()[0]
                fitting_rows = session.execute(
                    text("SELECT id, technical_product_id, source, source_url, city FROM fittings ORDER BY id"),
                ).fetchall()

            self.assertEqual(first["operation"], "created")
            self.assertEqual(second["operation"], "reused")
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(fitting_count, 1)
            self.assertEqual(product_count, 1)
            self.assertEqual(image_count, 1)
            self.assertEqual(offer_count, 1)
            self.assertEqual(len(fitting_rows), 1)
            self.assertIsNotNone(fitting_rows[0][1])
            self.assertEqual(fitting_rows[0][2], "viyar")
            self.assertEqual(fitting_rows[0][3], payload["source_url"])
            self.assertEqual(fitting_rows[0][4], "kyiv")


if __name__ == "__main__":
    unittest.main()
