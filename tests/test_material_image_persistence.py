import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest import mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.material import MaterialModel  # noqa: F401
from database.models import service_drilling_rule  # noqa: F401
from database.repositories import inventory_repository
from services.fitting_image_gallery_service import PreparedFittingGalleryImage


class MaterialImagePersistenceTests(unittest.TestCase):
    def test_upsert_material_persists_prepared_gallery_images_for_new_material(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "catalog.db"
            engine = create_engine(f"sqlite:///{database_path.as_posix()}")
            Base.metadata.create_all(bind=engine)
            session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

            image_bytes = b"fake-material-gallery-image"
            gallery_image = PreparedFittingGalleryImage(
                sort_order=0,
                is_primary=True,
                source_url="https://cdn.example.com/materials/gallery-1.jpg",
                image_bytes=image_bytes,
                content_type="image/jpeg",
                sha256=sha256(image_bytes).hexdigest(),
            )

            with mock.patch.object(inventory_repository, "SessionLocal", session_factory):
                created = inventory_repository.upsert_material(
                    article="100001",
                    name="Test material",
                    category="dsp",
                    description="Test description",
                    color="Test color",
                    dimensions="2800x2070",
                    thickness="18 mm",
                    image="https://cdn.example.com/materials/main.jpg",
                    source_url="https://viyar.ua/ua/catalog/test-material/",
                    source="viyar",
                    product_type="dsp",
                    image_source_url="https://cdn.example.com/materials/main.jpg",
                    imported_at=None,
                    static_updated_at=None,
                    prepared_gallery_images=[gallery_image],
                )

            with session_factory() as session:
                material_count = session.execute(text("SELECT COUNT(*) FROM materials")).scalar_one()
                image_count = session.execute(text("SELECT COUNT(*) FROM material_images")).scalar_one()
                row = session.execute(
                    text("SELECT id, article, source_url FROM materials WHERE article = :article"),
                    {"article": "100001"},
                ).fetchone()

            self.assertIsNotNone(created)
            self.assertEqual(created["article"], "100001")
            self.assertEqual(material_count, 1)
            self.assertEqual(image_count, 1)
            self.assertIsNotNone(row)
            self.assertEqual(row._mapping["article"], "100001")
            self.assertEqual(row._mapping["source_url"], "https://viyar.ua/ua/catalog/test-material")


if __name__ == "__main__":
    unittest.main()
