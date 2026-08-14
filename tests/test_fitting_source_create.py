from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models import fitting as fitting_models  # noqa: F401
from database.repositories import inventory_repository


class FittingSourceCreateTests(unittest.TestCase):
    def test_source_creation_creates_canonical_product_and_links_technical_product(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "catalog.db"
            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            Base.metadata.create_all(bind=engine)
            session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

            with patch.object(inventory_repository, "SessionLocal", session_factory):
                created = inventory_repository.create_fitting(
                    city="kyiv",
                    code="SRC-1",
                    article="84628",
                    name="Стяжка VB 35/18, біла (9116929) Hettich",
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
                        "name": "Стяжка VB 35/18, біла (9116929) Hettich",
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
                    text("SELECT id, article, code, name, brand, is_active FROM fitting_products"),
                ).fetchall()
                fitting_rows = session.execute(
                    text("SELECT id, article, name, technical_product_id, source_url, is_system FROM fittings"),
                ).fetchall()

            self.assertEqual(len(product_rows), 1)
            self.assertEqual(product_rows[0][1], "84628")
            self.assertEqual(product_rows[0][3], "Стяжка VB 35/18, біла (9116929) Hettich")
            self.assertEqual(len(fitting_rows), 1)
            self.assertEqual(fitting_rows[0][1], "84628")
            self.assertEqual(fitting_rows[0][2], "Стяжка VB 35/18, біла (9116929) Hettich")
            self.assertEqual(fitting_rows[0][3], product_rows[0][0])
            self.assertEqual(fitting_rows[0][4], "https://example.com/item")
            self.assertTrue(fitting_rows[0][5])
            self.assertEqual(created["technical_product_id"], product_rows[0][0])


if __name__ == "__main__":
    unittest.main()
