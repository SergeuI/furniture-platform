from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = PROJECT_ROOT / ".server-catalog-sync"
LOCAL_UPLOADS_ROOT = PROJECT_ROOT / "data" / "uploads"
KNOWN_SOURCE_SITES = {"viyar", "kronas", "mt"}


def normalize_text(value: object | None) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def normalize_source_url(value: object | None) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    if text.startswith("data:"):
        return text
    return text


def detect_fitting_source_site(source_url: str | None) -> str:
    normalized = normalize_text(source_url)
    if not normalized:
        return "manual"

    parsed = urlparse(normalized if "://" in normalized else f"https://{normalized}")
    host = (parsed.netloc or parsed.path or "").lower()

    if "viyar" in host:
        return "viyar"
    if "kronas" in host:
        return "kronas"
    if "mt.ua" in host:
        return "mt"
    return "generic"


def infer_fitting_source_site(
    source: object | None,
    source_url: object | None,
    *,
    payload_source_site: object | None = None,
) -> str | None:
    normalized_source = normalize_text(source)
    if normalized_source and normalized_source.casefold() in KNOWN_SOURCE_SITES:
        return normalized_source.casefold()

    normalized_payload_site = normalize_text(payload_source_site)
    if normalized_payload_site and normalized_payload_site.casefold() in KNOWN_SOURCE_SITES:
        return normalized_payload_site.casefold()

    normalized_url = normalize_text(source_url)
    if normalized_url:
        detected = detect_fitting_source_site(normalized_url)
        if detected in KNOWN_SOURCE_SITES:
            return detected

    return None


def slugify_bundle_name(value: str | None) -> str:
    text = normalize_text(value) or "catalog"
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-._")
    return text or "catalog"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_output_dir(timestamp: str) -> Path:
    return DEFAULT_BUNDLE_ROOT / timestamp


def uploads_path_from_logo_url(logo_url: str | None) -> Path | None:
    normalized = normalize_text(logo_url)
    if not normalized:
        return None
    if not normalized.startswith("/uploads/"):
        return None
    relative = normalized.removeprefix("/uploads/")
    return LOCAL_UPLOADS_ROOT / relative
