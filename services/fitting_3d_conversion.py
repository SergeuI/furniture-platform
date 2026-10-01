from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from services.fitting_3d_asset_storage import Fitting3DAssetStorage


class Fitting3DPackageValidationError(ValueError):
    pass


class Fitting3DConversionError(RuntimeError):
    pass


class Fitting3DCanonicalValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SourceFileMetadata:
    filename: str
    extension: str
    size: int
    sha256: str


@dataclass(frozen=True)
class GLBMetadata:
    file_size: int
    sha256: str
    scenes: int
    nodes: int
    meshes: int
    primitives: int
    materials: int
    images: int
    textures: int
    position_count: int
    normal_count: int
    index_count: int
    triangle_count: int
    bbox_min: tuple[float, float, float] | None
    bbox_max: tuple[float, float, float] | None
    dimensions: tuple[float, float, float] | None
    longest_axis: str | None


@dataclass(frozen=True)
class ConversionResult:
    canonical_path: Path
    canonical_format: str
    canonical: GLBMetadata
    source_files: tuple[SourceFileMetadata, ...]
    units: str
    converter_name: str
    converter_version: str
    validation: dict[str, Any] = field(default_factory=dict)
    workspace: Path | None = None


class Fitting3DSourceValidator:
    allowed = {".obj", ".mtl", ".png", ".jpg", ".jpeg", ".webp"}

    def __init__(self, max_files=32, max_file_size=50 * 1024 * 1024, max_total_size=100 * 1024 * 1024):
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.max_total_size = max_total_size

    def validate(self, files: Sequence[Path]) -> tuple[SourceFileMetadata, ...]:
        if not files or len(files) > self.max_files:
            raise Fitting3DPackageValidationError("invalid package file count")
        seen = set(); obj = []; names = []
        total = 0
        for source in files:
            path = Path(source)
            name = Fitting3DAssetStorage.safe_filename(path.name)
            normalized = name.casefold()
            if normalized in seen:
                raise Fitting3DPackageValidationError("duplicate normalized filename")
            seen.add(normalized); names.append(name)
            suffix = path.suffix.casefold()
            if suffix not in self.allowed:
                raise Fitting3DPackageValidationError(f"unsupported extension: {suffix}")
            if not path.is_file() or path.stat().st_size == 0:
                raise Fitting3DPackageValidationError(f"empty or missing file: {name}")
            size = path.stat().st_size
            if size > self.max_file_size:
                raise Fitting3DPackageValidationError("single file size limit exceeded")
            total += size
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            metadata = SourceFileMetadata(name, suffix, size, digest)
            if suffix == ".obj": obj.append(path)
        if len(obj) != 1:
            raise Fitting3DPackageValidationError("exactly one OBJ is required")
        if total > self.max_total_size:
            raise Fitting3DPackageValidationError("total package size limit exceeded")
        self._validate_references(files, obj[0])
        return tuple(SourceFileMetadata(Fitting3DAssetStorage.safe_filename(p.name), p.suffix.casefold(), p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()) for p in files)

    def _validate_references(self, files, obj):
        names = {Path(p).name.casefold() for p in files}
        text = obj.read_text(encoding="utf-8", errors="strict")
        if not any(line.strip().startswith("v ") for line in text.splitlines()):
            raise Fitting3DPackageValidationError("OBJ has no vertex data")
        references = []
        for line in text.splitlines():
            if line.strip().lower().startswith("mtllib "):
                references.append(line.split(None, 1)[1].strip())
        if not references:
            raise Fitting3DPackageValidationError("OBJ has no MTL reference")
        for reference in references:
            if Path(reference).name != reference or ".." in Path(reference).parts or reference.casefold() not in names:
                raise Fitting3DPackageValidationError("OBJ references MTL outside package")
        for mtl in files:
            if Path(mtl).suffix.casefold() != ".mtl": continue
            for line in Path(mtl).read_text(encoding="utf-8", errors="strict").splitlines():
                if line.strip().lower().startswith(("map_kd ", "map_ks ", "map_bump ", "bump ")):
                    reference = line.split()[-1]
                    if Path(reference).name != reference or ".." in Path(reference).parts or reference.casefold() not in names:
                        raise Fitting3DPackageValidationError("MTL references texture outside package")


def _chunks(data: bytes):
    if len(data) < 12 or data[:4] != b"glTF": raise Fitting3DCanonicalValidationError("invalid GLB header")
    version, declared = struct.unpack_from("<II", data, 4)
    if version != 2 or declared != len(data): raise Fitting3DCanonicalValidationError("invalid GLB version or length")
    offset = 12; result = []
    while offset < len(data):
        if offset + 8 > len(data): raise Fitting3DCanonicalValidationError("truncated GLB chunk")
        length, kind = struct.unpack_from("<I4s", data, offset)
        if length % 4 or offset + 8 + length > len(data): raise Fitting3DCanonicalValidationError("invalid GLB chunk")
        result.append((kind, data[offset + 8:offset + 8 + length])); offset += 8 + length
    return result


def normalize_glb_material(input_path: Path, output_path: Path) -> dict[str, Any]:
    data = Path(input_path).read_bytes(); chunks = _chunks(data)
    json_bytes = next((p for k, p in chunks if k == b"JSON"), None)
    bin_payload = next((p for k, p in chunks if k == b"BIN\x00"), None)
    if json_bytes is None or bin_payload is None: raise Fitting3DCanonicalValidationError("JSON and BIN chunks required")
    document = json.loads(json_bytes.rstrip(b" \t\r\n\x00"))
    changes = []
    for material in document.get("materials", []):
        pbr = material.get("pbrMetallicRoughness", {}); factor = pbr.get("baseColorFactor")
        if factor is None: continue
        if len(factor) != 4 or any(v < 0 or v > 255 for v in factor[:3]) or not 0 <= factor[3] <= 1:
            raise Fitting3DCanonicalValidationError("invalid baseColorFactor range")
        normalized = [v / 255 if v > 1 else v for v in factor[:3]] + [factor[3]]
        if normalized != factor:
            pbr["baseColorFactor"] = normalized
            changes.append({"material": material.get("name", ""), "original": factor, "normalized": normalized, "reason": "RGB 1..255 normalized to glTF 0..1"})
    encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode(); encoded += b" " * ((4 - len(encoded) % 4) % 4)
    body = struct.pack("<I4s", len(encoded), b"JSON") + encoded + struct.pack("<I4s", len(bin_payload), b"BIN\x00") + bin_payload
    Path(output_path).write_bytes(struct.pack("<4sII", b"glTF", 2, len(body) + 12) + body)
    return {"changes": changes, "input_bin_sha256": hashlib.sha256(bin_payload).hexdigest(), "output_bin_sha256": hashlib.sha256(bin_payload).hexdigest()}


def validate_glb(path: Path) -> GLBMetadata:
    data = Path(path).read_bytes(); chunks = _chunks(data)
    json_bytes = next((p for k, p in chunks if k == b"JSON"), None); bin_payload = next((p for k, p in chunks if k == b"BIN\x00"), None)
    if json_bytes is None or bin_payload is None: raise Fitting3DCanonicalValidationError("self-contained GLB requires JSON and BIN")
    doc = json.loads(json_bytes.rstrip(b" \t\r\n\x00"))
    for buffer in doc.get("buffers", []):
        if "uri" in buffer: raise Fitting3DCanonicalValidationError("external buffer URI rejected")
    for image in doc.get("images", []):
        if "uri" in image: raise Fitting3DCanonicalValidationError("external image URI rejected")
    meshes = doc.get("meshes", []); primitive = meshes[0]["primitives"][0] if meshes and meshes[0].get("primitives") else {}
    accessors = doc.get("accessors", []); attrs = primitive.get("attributes", {})
    position = accessors[attrs["POSITION"]] if "POSITION" in attrs else {}; normal = accessors[attrs["NORMAL"]] if "NORMAL" in attrs else {}
    index = accessors[primitive["indices"]] if "indices" in primitive else {}
    bbox_min = tuple(position.get("min", [])) or None; bbox_max = tuple(position.get("max", [])) or None
    dimensions = tuple(b - a for a, b in zip(bbox_min, bbox_max)) if bbox_min and bbox_max else None
    longest = "XYZ"[max(range(3), key=lambda i: dimensions[i])] if dimensions else None
    return GLBMetadata(len(data), hashlib.sha256(data).hexdigest(), len(doc.get("scenes", [])), len(doc.get("nodes", [])), len(meshes), sum(len(m.get("primitives", [])) for m in meshes), len(doc.get("materials", [])), len(doc.get("images", [])), len(doc.get("textures", [])), position.get("count", 0), normal.get("count", 0), index.get("count", 0), index.get("count", 0) // 3 if primitive.get("mode", 4) == 4 else 0, bbox_min, bbox_max, dimensions, longest)


class Obj2GltfAdapter:
    name = "obj2gltf"
    version = "3.2.0"
    def __init__(self, executable: str | None = None, timeout_seconds: int = 120):
        self.executable = executable or os.getenv("FITTING_3D_OBJ2GLTF_EXECUTABLE", "obj2gltf")
        self.timeout_seconds = timeout_seconds
    def convert(self, obj: Path, output: Path) -> subprocess.CompletedProcess:
        command = [self.executable, "-i", str(obj), "-o", str(output), "-b", "--secure"]
        try: result = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_seconds, shell=False)
        except (OSError, subprocess.TimeoutExpired) as exc: raise Fitting3DConversionError("obj2gltf execution failed") from exc
        if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            raise Fitting3DConversionError(f"obj2gltf failed: {result.stderr[-2000:]}")
        return result


def convert_fitting_3d_package(files: Sequence[Path], executable: str | None = None, storage: Fitting3DAssetStorage | None = None, keep_workspace: bool = True) -> ConversionResult:
    storage = storage or Fitting3DAssetStorage(); workspace = storage.create_workspace()
    try:
        metadata = Fitting3DSourceValidator().validate(files)
        source_dir = workspace / "source"; source_dir.mkdir()
        copied = []
        for source in files:
            target = source_dir / Fitting3DAssetStorage.safe_filename(Path(source).name); shutil.copyfile(source, target); copied.append(target)
        obj = next(p for p in copied if p.suffix.casefold() == ".obj"); raw = workspace / "raw.glb"; canonical = workspace / "canonical.glb"
        Obj2GltfAdapter(executable).convert(obj, raw); normalize_glb_material(raw, canonical); glb = validate_glb(canonical)
        return ConversionResult(canonical, "glb", glb, metadata, "unknown", "obj2gltf", "3.2.0", {"self_contained": True}, workspace if keep_workspace else None)
    except Exception:
        storage.cleanup(workspace); raise
