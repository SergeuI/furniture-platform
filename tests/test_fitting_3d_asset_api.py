import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from api.routes import catalog
from services.fitting_3d_conversion import Fitting3DPackageValidationError


class FakeQuery:
    def filter(self, *_args): return self
    def one(self): return object()


class FakeDB:
    def query(self, *_args): return FakeQuery()
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass
    def refresh(self, _asset): pass


def upload(name, content):
    return UploadFile(filename=name, file=io.BytesIO(content))


class Fitting3DAssetApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.feature_patch = patch.object(catalog, "_ensure_fitting_feature_access")
        self.feature_patch.start()

    def tearDown(self):
        self.feature_patch.stop()

    def test_openapi_declares_multiple_binary_files(self):
        from main_api import app

        schema = app.openapi()["components"]["schemas"]["Body_import_fitting_3d_asset_route_catalog_fittings__item_id__3d_asset_post"]
        files = schema["properties"]["files"]
        self.assertEqual(files["type"], "array")
        self.assertEqual(files["items"], {"type": "string", "format": "binary"})

    async def test_rejects_too_many_files_before_conversion(self):
        with self.assertRaises(HTTPException) as error:
            await catalog.import_fitting_3d_asset_route(1, [upload(f"{i}.obj", b"x") for i in range(33)], SimpleNamespace())
        self.assertEqual(error.exception.status_code, 400)

    async def test_rejects_empty_upload(self):
        with self.assertRaises(HTTPException) as error:
            await catalog.import_fitting_3d_asset_route(1, [upload("model.obj", b"")], SimpleNamespace())
        self.assertEqual(error.exception.status_code, 400)

    async def test_maps_package_validation_without_leaking_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(catalog, "convert_fitting_3d_package", side_effect=Fitting3DPackageValidationError("bad package")), patch.object(catalog, "SessionLocal", return_value=FakeDB()):
                with self.assertRaises(HTTPException) as error:
                    await catalog.import_fitting_3d_asset_route(1, [upload("model.obj", b"obj")], SimpleNamespace())
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(error.exception.detail, "Invalid 3D asset package")

    async def test_success_returns_asset_and_cleans_upload_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "conversion"
            workspace.mkdir()
            result = SimpleNamespace(workspace=workspace)
            asset = SimpleNamespace(canonical_file_url="/uploads/fitting-3d-assets/id/canonical/model.glb")
            with patch.object(catalog, "convert_fitting_3d_package", return_value=result), patch.object(catalog, "persist_fitting_3d_asset", return_value=asset), patch.object(catalog, "_serialize_fitting_detail", return_value={"three_d_asset": {"id": 1}}), patch.object(catalog, "SessionLocal", return_value=FakeDB()), patch.dict("os.environ", {"FITTING_3D_STORAGE_ROOT": temp}):
                response = await catalog.import_fitting_3d_asset_route(1, [upload("model.obj", b"obj")], SimpleNamespace())
        self.assertEqual(response, {"id": 1})
        self.assertFalse(workspace.exists())


if __name__ == "__main__": unittest.main()
