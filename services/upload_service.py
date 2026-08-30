import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image


UPLOAD_ROOT = Path("data/uploads/ai_scans")
SUPPLIER_LOGO_UPLOAD_ROOT = Path("data/uploads/supplier-logos")
MANUFACTURER_LOGO_UPLOAD_ROOT = Path("data/uploads/fitting-manufacturer-logos")
MATERIAL_MANUFACTURER_LOGO_UPLOAD_ROOT = Path("data/uploads/material-manufacturer-logos")
MATERIAL_CATEGORY_IMAGE_UPLOAD_ROOT = Path("data/uploads/material-category-images")
EDGE_IMAGE_UPLOAD_ROOT = Path("data/uploads/edge-images")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_SIZE_BYTES = 12 * 1024 * 1024


def _safe_filename_stem(filename: str) -> str:
    stem = Path(filename or "scan").stem.lower()
    stem = re.sub(r"[^a-zа-яіїєґё0-9]+", "_", stem, flags=re.IGNORECASE)
    stem = stem.strip("_")
    return stem[:80] or "scan"


def validate_file_type(file: UploadFile) -> bool:
    suffix = Path(file.filename or "").suffix.lower()
    return suffix in ALLOWED_EXTENSIONS


def validate_file_size(size_bytes: int) -> bool:
    return 0 < size_bytes <= MAX_UPLOAD_SIZE_BYTES


def _validate_image_payload(*, filename: str, content: bytes, content_type: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    normalized_content_type = str(content_type or "").strip().lower()

    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Unsupported file type. Use PNG, JPG, JPEG, or WEBP.")

    if normalized_content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError("Unsupported file type. Use PNG, JPG, JPEG, or WEBP.")

    if not validate_file_size(len(content)):
        raise ValueError("Uploaded file is empty or too large")

    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
            image_format = (image.format or "").upper()
    except Exception as exc:
        raise ValueError("Unsupported file type. Use PNG, JPG, JPEG, or WEBP.") from exc

    detected_mime_type = {
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }.get(image_format)

    if detected_mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError("Unsupported file type. Use PNG, JPG, JPEG, or WEBP.")

    return detected_mime_type


async def save_uploaded_file(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    safe_name = f"{_safe_filename_stem(file.filename or '')}_{uuid4().hex}{suffix}"
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    target_path = UPLOAD_ROOT / safe_name

    content = await file.read()

    if not validate_file_size(len(content)):
        raise ValueError("Uploaded file is empty or too large")

    target_path.write_bytes(content)
    await file.seek(0)
    return str(target_path)


def save_uploaded_bytes(filename: str, content: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type. Use JPG, PNG, or PDF.")

    if not validate_file_size(len(content)):
        raise ValueError("Uploaded file is empty or too large")

    safe_name = f"{_safe_filename_stem(filename)}_{uuid4().hex}{suffix}"
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    target_path = UPLOAD_ROOT / safe_name
    target_path.write_bytes(content)
    return str(target_path)


async def save_supplier_logo_file(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    content = await file.read()
    detected_content_type = _validate_image_payload(
        filename=file.filename or "",
        content=content,
        content_type=file.content_type,
    )

    normalized_content_type = str(file.content_type or "").strip().lower()
    if detected_content_type != normalized_content_type:
        raise ValueError("Unsupported file type. Use PNG, JPG, JPEG, or WEBP.")

    safe_name = f"{_safe_filename_stem(file.filename or '')}_{uuid4().hex}{suffix}"
    SUPPLIER_LOGO_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    target_path = SUPPLIER_LOGO_UPLOAD_ROOT / safe_name
    target_path.write_bytes(content)
    await file.seek(0)
    return f"/uploads/supplier-logos/{safe_name}"


async def save_manufacturer_logo_file(file: UploadFile) -> str:
    return await _save_uploaded_image_file(
        file,
        upload_root=MANUFACTURER_LOGO_UPLOAD_ROOT,
        url_prefix="/uploads/fitting-manufacturer-logos",
    )


async def save_material_manufacturer_logo_file(file: UploadFile) -> str:
    return await _save_uploaded_image_file(
        file,
        upload_root=MATERIAL_MANUFACTURER_LOGO_UPLOAD_ROOT,
        url_prefix="/uploads/material-manufacturer-logos",
    )


async def save_material_category_image_file(file: UploadFile) -> str:
    return await _save_uploaded_image_file(
        file,
        upload_root=MATERIAL_CATEGORY_IMAGE_UPLOAD_ROOT,
        url_prefix="/uploads/material-category-images",
    )


async def save_edge_image_file(file: UploadFile) -> str:
    return await _save_uploaded_image_file(
        file,
        upload_root=EDGE_IMAGE_UPLOAD_ROOT,
        url_prefix="/uploads/edge-images",
    )


async def _save_uploaded_image_file(
    file: UploadFile,
    *,
    upload_root: Path,
    url_prefix: str,
) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    content = await file.read()
    detected_content_type = _validate_image_payload(
        filename=file.filename or "",
        content=content,
        content_type=file.content_type,
    )

    normalized_content_type = str(file.content_type or "").strip().lower()
    if detected_content_type != normalized_content_type:
        raise ValueError("Unsupported file type. Use PNG, JPG, JPEG, or WEBP.")

    safe_name = f"{_safe_filename_stem(file.filename or '')}_{uuid4().hex}{suffix}"
    upload_root.mkdir(parents=True, exist_ok=True)
    target_path = upload_root / safe_name
    target_path.write_bytes(content)
    await file.seek(0)
    return f"{url_prefix}/{safe_name}"
