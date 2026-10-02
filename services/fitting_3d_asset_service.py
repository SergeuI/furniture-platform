from __future__ import annotations

import hashlib
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from database.models.fitting import FittingModel
from database.models.fitting_3d_asset import Fitting3DAssetModel, Fitting3DAssetSourceModel
from services.fitting_3d_conversion import ConversionResult

logger = logging.getLogger(__name__)


class Fitting3DAssetPersistenceError(RuntimeError):
    pass


class Fitting3DAssetConflictError(Fitting3DAssetPersistenceError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _role(path: Path) -> str:
    return "model" if path.suffix.casefold() == ".obj" else "material" if path.suffix.casefold() == ".mtl" else "texture"


def persist_fitting_3d_asset(db, fitting_id: int, conversion_result: ConversionResult, storage_root: Path | str = Path("data/uploads"), replace_existing: bool = False):
    fitting = db.query(FittingModel).filter(FittingModel.id == fitting_id).one_or_none()
    if fitting is None:
        raise Fitting3DAssetPersistenceError("fitting not found")
    existing_asset = db.query(Fitting3DAssetModel).filter(Fitting3DAssetModel.fitting_id == fitting_id).one_or_none()
    if existing_asset is not None and not replace_existing:
        raise Fitting3DAssetConflictError("fitting already has a 3D asset")
    if conversion_result.canonical_format != "glb" or not conversion_result.canonical_path.is_file():
        raise Fitting3DAssetPersistenceError("invalid canonical conversion result")
    if _sha256(conversion_result.canonical_path) != conversion_result.canonical.sha256:
        raise Fitting3DAssetPersistenceError("canonical checksum mismatch")
    source_root = conversion_result.workspace / "source" if conversion_result.workspace else None
    if source_root is None or not source_root.is_dir():
        raise Fitting3DAssetPersistenceError("conversion source workspace is unavailable")

    asset_uuid = uuid.uuid4().hex
    root = Path(storage_root) / "fitting-3d-assets"
    staging = root / f".{asset_uuid}.staging"
    final = root / asset_uuid
    stage = "filesystem_persist"
    try:
        (staging / "canonical").mkdir(parents=True)
        (staging / "sources").mkdir()
        canonical_target = staging / "canonical" / "model.glb"
        shutil.copyfile(conversion_result.canonical_path, canonical_target)
        if canonical_target.stat().st_size != conversion_result.canonical.file_size or _sha256(canonical_target) != conversion_result.canonical.sha256:
            raise Fitting3DAssetPersistenceError("canonical copy verification failed")
        source_rows = []
        for order, source in enumerate(sorted(conversion_result.source_files, key=lambda item: (0 if _role(Path(item.filename)) == "model" else 1 if _role(Path(item.filename)) == "material" else 2, item.filename.casefold()))):
            source_path = source_root / source.filename
            target = staging / "sources" / source.filename
            if not source_path.is_file() or target.parent != (staging / "sources"):
                raise Fitting3DAssetPersistenceError("source file is unavailable or unsafe")
            shutil.copyfile(source_path, target)
            if target.stat().st_size != source.size or _sha256(target) != source.sha256:
                raise Fitting3DAssetPersistenceError("source copy verification failed")
            source_rows.append((source, f"/uploads/fitting-3d-assets/{asset_uuid}/sources/{source.filename}", order))
        os.replace(staging, final)
        dimensions = conversion_result.canonical.dimensions or (None, None, None)
        bbox_min = conversion_result.canonical.bbox_min or (None, None, None)
        bbox_max = conversion_result.canonical.bbox_max or (None, None, None)
        if existing_asset is None:
            asset = Fitting3DAssetModel(fitting_id=fitting_id)
            db.add(asset)
        else:
            asset = existing_asset
            asset.sources.clear()
        asset.status = "validated"
        asset.canonical_format = "glb"
        asset.canonical_file_url = f"/uploads/fitting-3d-assets/{asset_uuid}/canonical/model.glb"
        asset.canonical_file_size = conversion_result.canonical.file_size
        asset.canonical_sha256 = conversion_result.canonical.sha256
        asset.units = conversion_result.units
        asset.dimensions_x, asset.dimensions_y, asset.dimensions_z = dimensions
        asset.bbox_min_x, asset.bbox_min_y, asset.bbox_min_z = bbox_min
        asset.bbox_max_x, asset.bbox_max_y, asset.bbox_max_z = bbox_max
        asset.coordinate_system_configured = 0
        asset.material_color_override = None
        asset.material_overrides_json = None
        asset.validated_at = datetime.now(timezone.utc)
        stage = "db_asset_update"
        db.flush()
        stage = "source_record_persist"
        for source, url, order in source_rows:
            db.add(Fitting3DAssetSourceModel(asset_id=asset.id, file_role=_role(Path(source.filename)), file_format=source.extension.lstrip("."), file_name=source.filename, file_url=url, file_size=source.size, sha256=source.sha256, order_index=order))
        stage = "flush"
        db.flush()
        return asset
    except Exception as exc:
        logger.exception(
            "Fitting 3D persistence failed: fitting_id=%s replace=%s stage=%s canonical_path=%s exception_type=%s",
            fitting_id,
            replace_existing,
            stage,
            str(final / "canonical" / "model.glb"),
            type(exc).__name__,
        )
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(final, ignore_errors=True)
        try:
            root.rmdir()
        except OSError:
            pass
        try:
            Path(storage_root).rmdir()
        except OSError:
            pass
        if isinstance(exc, Fitting3DAssetPersistenceError):
            raise
        raise Fitting3DAssetPersistenceError(f"persistence failed at {stage}") from exc
