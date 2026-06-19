import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


UPLOAD_ROOT = Path("data/uploads/ai_scans")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
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
