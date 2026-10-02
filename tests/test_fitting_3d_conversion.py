import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.fitting_3d_conversion import (
    Fitting3DCanonicalValidationError,
    Fitting3DPackageValidationError,
    Fitting3DSourceValidator,
    Obj2GltfAdapter,
    _sanitize_obj_for_material_fallback,
    convert_fitting_3d_package,
    normalize_glb_material,
    resolve_obj2gltf_executable,
    validate_glb,
)


def make_glb(path, factor=(192, 192, 192, 1), external=False):
    doc = {"asset": {"version": "2.0"}, "scenes": [{}], "nodes": [{}], "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2}]}], "materials": [{"name": "Металь никель", "pbrMetallicRoughness": {"baseColorFactor": list(factor), "metallicFactor": 0, "roughnessFactor": 1}}], "accessors": [{"count": 3, "min": [0, 0, 0], "max": [2, 1, 1]}, {"count": 3}, {"count": 3}], "buffers": [{"byteLength": 4}], "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 4}], "images": [], "textures": []}
    if external: doc["buffers"][0]["uri"] = "bad.bin"
    payload = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode(); payload += b" " * ((4 - len(payload) % 4) % 4)
    binary = b"ABCD"
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(payload) + 8 + len(binary)) + struct.pack("<I4s", len(payload), b"JSON") + payload + struct.pack("<I4s", len(binary), b"BIN\x00") + binary)


class Fitting3DConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "part.obj").write_text("mtllib part.mtl\nv 0 0 0\nf 1 1 1\n", encoding="utf-8")
        (self.root / "part.mtl").write_text("newmtl m\nKd 1 1 1\n", encoding="utf-8")
    def tearDown(self): self.tmp.cleanup()
    def files(self): return [self.root / "part.obj", self.root / "part.mtl"]

    @patch.dict("os.environ", {"FITTING_3D_OBJ2GLTF_EXECUTABLE": "override-tool"}, clear=False)
    def test_explicit_executable_override_wins(self):
        self.assertEqual(resolve_obj2gltf_executable(), "override-tool")

    def test_project_local_executable_resolution(self):
        with patch("services.fitting_3d_conversion.PROJECT_ROOT", self.root), patch("services.fitting_3d_conversion.os.name", "nt"), patch.dict("os.environ", {}, clear=True), patch("services.fitting_3d_conversion.shutil.which", return_value=None):
            local = self.root / "tools" / "fitting-3d" / "node_modules" / ".bin" / "obj2gltf.cmd"
            local.parent.mkdir(parents=True)
            local.write_text("", encoding="utf-8")
            self.assertEqual(resolve_obj2gltf_executable(), str(local))

    def test_unix_project_local_executable_resolution(self):
        with patch("services.fitting_3d_conversion.PROJECT_ROOT", self.root), patch("services.fitting_3d_conversion.os.name", "posix"), patch.dict("os.environ", {}, clear=True), patch("services.fitting_3d_conversion.shutil.which", return_value=None):
            local = self.root / "tools" / "fitting-3d" / "node_modules" / ".bin" / "obj2gltf"
            local.parent.mkdir(parents=True)
            local.write_text("", encoding="utf-8")
            self.assertEqual(resolve_obj2gltf_executable(), str(local))

    def test_path_fallback_resolution(self):
        with patch("services.fitting_3d_conversion.PROJECT_ROOT", self.root), patch.dict("os.environ", {}, clear=True), patch("services.fitting_3d_conversion.shutil.which", return_value="path-tool"):
            self.assertEqual(resolve_obj2gltf_executable(), "path-tool")

    def test_missing_executable_has_controlled_error(self):
        with patch("services.fitting_3d_conversion.PROJECT_ROOT", self.root), patch.dict("os.environ", {}, clear=True), patch("services.fitting_3d_conversion.shutil.which", return_value=None):
            with self.assertRaisesRegex(Exception, "obj2gltf executable not found"):
                resolve_obj2gltf_executable()
    def test_valid_obj_without_mtl(self):
        obj = self.root / "obj-only.obj"
        obj.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
        result = Fitting3DSourceValidator().validate([obj])
        self.assertEqual(len(result), 1)

    def test_mtl_texture_reference_is_valid_when_uploaded(self):
        texture = self.root / "metal.png"; texture.write_bytes(b"png")
        (self.root / "part.mtl").write_text("newmtl m\nmap_Kd metal.png\n", encoding="utf-8")
        self.assertEqual(len(Fitting3DSourceValidator().validate(self.files() + [texture])), 3)

    def test_obj_only_gets_default_material(self):
        raw = self.root / "raw.glb"; out = self.root / "out.glb"; make_glb(raw)
        raw_doc = json.loads(next(payload for kind, payload in __import__("services.fitting_3d_conversion", fromlist=["_chunks"])._chunks(raw.read_bytes()) if kind == b"JSON").rstrip(b" \t\r\n\x00"))
        raw_doc["materials"] = []
        payload = json.dumps(raw_doc, separators=(",", ":")).encode(); payload += b" " * ((4 - len(payload) % 4) % 4)
        binary = b"ABCD"; raw.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(payload) + 8 + len(binary)) + struct.pack("<I4s", len(payload), b"JSON") + payload + struct.pack("<I4s", len(binary), b"BIN\x00") + binary)
        normalize_glb_material(raw, out, apply_default_material=True)
        self.assertEqual(validate_glb(out).materials, 1)

    @patch("services.fitting_3d_conversion.Obj2GltfAdapter.convert")
    def test_missing_mtl_usemtl_fallback_preserves_geometry_and_default_material(self, convert):
        obj = self.root / "bolt.obj"
        obj.write_text("mtllib missing.mtl\nusemtl SomeMaterial\nv 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvn 0 0 1\nf 1 2 3\n", encoding="utf-8")

        def fake_convert(source, output):
            sanitized = source.read_text(encoding="utf-8")
            self.assertNotIn("mtllib", sanitized.lower())
            self.assertNotIn("usemtl", sanitized.lower())
            self.assertIn("v 1 0 0", sanitized)
            self.assertIn("f 1 2 3", sanitized)
            make_glb(output)

        convert.side_effect = fake_convert
        result = convert_fitting_3d_package([obj], storage=__import__("services.fitting_3d_asset_storage", fromlist=["Fitting3DAssetStorage"]).Fitting3DAssetStorage(self.root))
        self.assertEqual(result.canonical.materials, 1)
        self.assertEqual(result.canonical_path.exists(), True)
    def test_valid_package_and_metadata(self):
        result = Fitting3DSourceValidator().validate(self.files())
        self.assertEqual(len(result), 2); self.assertGreater(result[0].size, 0)
    def test_rejects_bad_package(self):
        for name in ["../evil.obj", "part.3ds"]:
            with self.assertRaises(Fitting3DPackageValidationError): Fitting3DSourceValidator().validate([self.root / name, self.root / "part.mtl"])
    def test_rejects_missing_mtl_duplicate_and_limits(self):
        (self.root / "bad.obj").write_text("v 0 0 0\nmtllib missing.mtl\n", encoding="utf-8")
        self.assertEqual(len(Fitting3DSourceValidator().validate([self.root / "bad.obj"])), 1)
        (self.root / "part.mtl").write_text("newmtl m\nmap_Kd missing.png\n", encoding="utf-8")
        self.assertEqual(len(Fitting3DSourceValidator().validate(self.files())), 2)
        (self.root / "bad.obj").write_text("v 0 0 0\nmtllib ../part.mtl\n", encoding="utf-8")
        with self.assertRaises(Fitting3DPackageValidationError): Fitting3DSourceValidator().validate([self.root / "bad.obj", self.root / "part.mtl"])
        (self.root / "bad.obj").write_text("mtllib part.mtl\n", encoding="utf-8")
        with self.assertRaises(Fitting3DPackageValidationError): Fitting3DSourceValidator().validate([self.root / "bad.obj", self.root / "part.mtl"])
        with self.assertRaises(Fitting3DPackageValidationError): Fitting3DSourceValidator().validate([self.root / "part.obj", self.root / "part.mtl", self.root / "part.mtl"])
        with self.assertRaises(Fitting3DPackageValidationError): Fitting3DSourceValidator(max_file_size=1).validate(self.files())
    def test_normalizes_and_preserves_bin(self):
        raw = self.root / "raw.glb"; out = self.root / "out.glb"; make_glb(raw); normalize_glb_material(raw, out)
        self.assertEqual(validate_glb(raw).index_count, validate_glb(out).index_count)
        self.assertEqual(raw.read_bytes()[-4:], out.read_bytes()[-4:])
        self.assertEqual(validate_glb(out).file_size, out.stat().st_size)
    def test_normalized_unchanged_and_invalid_rejected(self):
        raw = self.root / "raw.glb"; out = self.root / "out.glb"; make_glb(raw, (0.5, 0.5, 0.5, 1)); normalize_glb_material(raw, out); self.assertEqual(raw.read_bytes(), out.read_bytes())
        make_glb(raw, (256, 1, 1, 1))
        with self.assertRaises(Fitting3DCanonicalValidationError): normalize_glb_material(raw, out)
    def test_glb_self_contained_and_external_rejected(self):
        raw = self.root / "raw.glb"; make_glb(raw, external=True)
        with self.assertRaises(Fitting3DCanonicalValidationError): validate_glb(raw)
    @patch("services.fitting_3d_conversion.subprocess.run")
    def test_adapter_uses_secure_binary_flags_without_shell(self, run):
        output = self.root / "out.glb"; output.write_bytes(b"glTF")
        run.return_value.returncode = 0; run.return_value.stderr = ""
        Obj2GltfAdapter("obj2gltf-test").convert(self.root / "part.obj", output)
        args, kwargs = run.call_args; self.assertIn("-b", args[0]); self.assertIn("--secure", args[0]); self.assertFalse(kwargs["shell"])


if __name__ == "__main__": unittest.main()
