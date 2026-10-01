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
    normalize_glb_material,
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
    def test_valid_package_and_metadata(self):
        result = Fitting3DSourceValidator().validate(self.files())
        self.assertEqual(len(result), 2); self.assertGreater(result[0].size, 0)
    def test_rejects_bad_package(self):
        for name in ["../evil.obj", "part.3ds"]:
            with self.assertRaises(Fitting3DPackageValidationError): Fitting3DSourceValidator().validate([self.root / name, self.root / "part.mtl"])
    def test_rejects_missing_mtl_duplicate_and_limits(self):
        (self.root / "bad.obj").write_text("v 0 0 0\nmtllib missing.mtl\n", encoding="utf-8")
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
