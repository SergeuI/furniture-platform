import hashlib
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.fitting import FittingModel, FittingProductModel, SupplierModel, FittingSupplierOfferModel
from database.models.fitting_3d_asset import Fitting3DAssetModel, Fitting3DAssetSourceModel
from database.models import hole_library  # noqa: F401
from database.models.user import UserModel
from services.fitting_3d_asset_service import Fitting3DAssetConflictError, persist_fitting_3d_asset
from services.fitting_3d_conversion import ConversionResult, GLBMetadata, SourceFileMetadata


class Fitting3DAssetServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name); self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[UserModel.__table__, FittingProductModel.__table__, SupplierModel.__table__, FittingModel.__table__, FittingSupplierOfferModel.__table__, Fitting3DAssetModel.__table__, Fitting3DAssetSourceModel.__table__]); self.db = sessionmaker(bind=self.engine)()
        self.db.add(FittingModel(name="Test fitting", is_active=True)); self.db.commit(); self.workspace = self.root / "workspace"; (self.workspace / "source").mkdir(parents=True)
        self.glb = self.workspace / "canonical.glb"; self.glb.write_bytes(b"canonical")
        for name, content in [("model.obj", b"obj"), ("model.mtl", b"mtl")]: (self.workspace / "source" / name).write_bytes(content)
        self.result = ConversionResult(self.glb, "glb", GLBMetadata(len(b"canonical"), hashlib.sha256(b"canonical").hexdigest(), 1, 1, 1, 1, 1, 0, 0, 446, 446, 1260, 420, (0, 0, 0), (46.8, 10.4, 10.4), (46.8, 10.4, 10.4), "X"), tuple(SourceFileMetadata(n, "." + n.split(".")[1], len(c), hashlib.sha256(c).hexdigest()) for n, c in [("model.obj", b"obj"), ("model.mtl", b"mtl")]), "unknown", "obj2gltf", "3.2.0", workspace=self.workspace)
    def tearDown(self): self.db.close(); self.engine.dispose(); self.tmp.cleanup()
    def test_persists_asset_sources_urls_metadata_and_checksums(self):
        asset = persist_fitting_3d_asset(self.db, 1, self.result, self.root / "uploads"); self.db.commit()
        self.assertEqual(asset.status, "validated"); self.assertEqual(len(asset.sources), 2); self.assertTrue((self.root / "uploads" / "fitting-3d-assets" / asset.canonical_file_url.split("/")[-3] / "canonical" / "model.glb").is_file())
        self.assertEqual([s.file_role for s in asset.sources], ["model", "material"]); self.assertEqual(asset.units, "unknown"); self.assertIsNone(asset.axis_up); self.assertIsNone(asset.origin_x)
    def test_missing_fitting_creates_no_files(self):
        with self.assertRaises(Exception): persist_fitting_3d_asset(self.db, 99, self.result, self.root / "uploads")
        self.assertFalse((self.root / "uploads").exists())
    def test_conflict_does_not_overwrite(self):
        persist_fitting_3d_asset(self.db, 1, self.result, self.root / "uploads"); self.db.commit()
        with self.assertRaises(Fitting3DAssetConflictError): persist_fitting_3d_asset(self.db, 1, self.result, self.root / "uploads")
    def test_copy_failure_cleans_directory(self):
        (self.workspace / "source" / "model.mtl").unlink()
        with self.assertRaises(Exception): persist_fitting_3d_asset(self.db, 1, self.result, self.root / "uploads")
        self.assertFalse((self.root / "uploads").exists())


if __name__ == "__main__": unittest.main()
