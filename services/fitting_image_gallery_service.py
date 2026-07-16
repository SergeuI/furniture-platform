from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import Any, Callable, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse

from services.material_catalog_service import fetch_remote_image_payload


class FittingGalleryPreparationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedFittingGalleryImage:
    sort_order: int
    is_primary: bool
    source_url: str
    image_bytes: bytes
    content_type: str
    sha256: str


GalleryFetcher = Callable[[str], dict[str, Any] | None]


def _normalize_text(value: object | None) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_image_url(value: object | None) -> str | None:
    url = _normalize_text(value)
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None

    query_items = [
        (key, item_value)
        for key, item_value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() != "size"
    ]
    return parsed._replace(query=urlencode(query_items, doseq=True), fragment="").geturl()


def _normalize_image_urls(values: Sequence[object]) -> list[str]:
    normalized: list[str] = []

    for value in values:
        url = _normalize_image_url(value)
        if not url:
            raise FittingGalleryPreparationError("Gallery image URLs must be valid http/https links.")
        normalized.append(url)

    if not normalized:
        raise FittingGalleryPreparationError("image_urls must not be empty.")

    return normalized


def normalize_fitting_gallery_image_urls(values: Sequence[object]) -> list[str]:
    return _normalize_image_urls(values)


def _detect_content_type(image_bytes: bytes) -> str | None:
    try:
        from PIL import Image
    except Exception:
        return None

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            image_format = (image.format or "").upper()
    except Exception:
        return None

    mime_map = {
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "PNG": "image/png",
    }
    return mime_map.get(image_format)


def _normalize_content_type(image_bytes: bytes, content_type: object | None) -> str:
    detected_content_type = _detect_content_type(image_bytes)
    if detected_content_type:
        return detected_content_type

    raise FittingGalleryPreparationError("Unable to validate gallery image format.")


def _sha256_hex(image_bytes: bytes) -> str:
    return sha256(image_bytes).hexdigest()


def _prepare_image_record(
    *,
    source_url: str,
    image_bytes: bytes,
    content_type: object | None,
    sort_order: int,
    is_primary: bool,
) -> PreparedFittingGalleryImage:
    if not image_bytes:
        raise FittingGalleryPreparationError(f"Gallery image payload is empty: {source_url}")

    normalized_content_type = _normalize_content_type(image_bytes, content_type)
    return PreparedFittingGalleryImage(
        sort_order=sort_order,
        is_primary=is_primary,
        source_url=source_url,
        image_bytes=image_bytes,
        content_type=normalized_content_type,
        sha256=_sha256_hex(image_bytes),
    )


def prepare_fitting_gallery_images(
    image_urls: Sequence[object],
    *,
    existing_primary_bytes: bytes | None = None,
    existing_primary_content_type: str | None = None,
    fetcher: GalleryFetcher = fetch_remote_image_payload,
) -> tuple[PreparedFittingGalleryImage, ...]:
    normalized_urls = _normalize_image_urls(image_urls)
    prepared_images: list[PreparedFittingGalleryImage] = []
    seen_hashes: set[str] = set()

    if existing_primary_bytes is not None:
        primary_source_url = normalized_urls[0]
        primary_image = _prepare_image_record(
            source_url=primary_source_url,
            image_bytes=existing_primary_bytes,
            content_type=existing_primary_content_type,
            sort_order=0,
            is_primary=True,
        )
        prepared_images.append(primary_image)
        seen_hashes.add(primary_image.sha256)
        next_sort_order = 1
        urls_to_process = normalized_urls[1:]
    else:
        next_sort_order = 0
        urls_to_process = normalized_urls

    for source_url in urls_to_process:
        payload = fetcher(source_url)
        if not payload:
            raise FittingGalleryPreparationError(f"Unable to validate gallery image: {source_url}")

        image_bytes = payload.get("bytes")
        content_type = payload.get("content_type")
        if not isinstance(image_bytes, (bytes, bytearray)) or not bytes(image_bytes):
            raise FittingGalleryPreparationError(f"Gallery image payload is empty: {source_url}")

        prepared_image = _prepare_image_record(
            source_url=source_url,
            image_bytes=bytes(image_bytes),
            content_type=content_type,
            sort_order=next_sort_order,
            is_primary=not prepared_images,
        )

        if prepared_image.sha256 in seen_hashes:
            continue

        prepared_images.append(prepared_image)
        seen_hashes.add(prepared_image.sha256)
        next_sort_order += 1

    if not prepared_images:
        raise FittingGalleryPreparationError("No unique gallery images were prepared.")

    return tuple(prepared_images)
