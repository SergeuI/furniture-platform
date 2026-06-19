import json
import re
from datetime import datetime
from pathlib import Path


OCR_LOG_ROOT = Path("data/ai_scan_logs")
DIMENSION_PATTERN = re.compile(
    r"(?P<a>\d{3,4})\s*(?:x|\u0445|\u00d7|\*)\s*(?P<b>\d{3,4})\s*(?:x|\u0445|\u00d7|\*)\s*(?P<c>\d{2,4})",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")


def _parse_number(value: str) -> int | None:
    try:
        return int(float(value.replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _extract_numbers(text: str) -> list[int]:
    numbers = []

    for match in NUMBER_PATTERN.findall(text or ""):
        number = _parse_number(match)
        if number is not None and 20 <= number <= 10000:
            numbers.append(number)

    return numbers


def _infer_dimensions_from_text(text: str, numbers: list[int]) -> dict:
    match = DIMENSION_PATTERN.search(text or "")

    if match:
        return {
            "width": int(match.group("a")),
            "height": int(match.group("b")),
            "depth": int(match.group("c")),
        }

    candidates = [number for number in numbers if 250 <= number <= 4000]

    if len(candidates) < 3:
        return {}

    sorted_values = sorted(candidates[:8], reverse=True)
    width = sorted_values[0]
    height = sorted_values[1]
    depth_candidates = [value for value in candidates if 250 <= value <= 900]
    depth = min(depth_candidates) if depth_candidates else sorted_values[2]

    return {
        "width": width,
        "height": height,
        "depth": depth,
    }


def _extract_text_with_tesseract(file_path: str) -> str:
    try:
        from PIL import Image
        import pytesseract
    except Exception:
        return ""

    try:
        image = Image.open(file_path)
        return pytesseract.image_to_string(
            image,
            lang="ukr+rus+eng",
        ).strip()
    except Exception:
        return ""


def _extract_text_from_pdf(file_path: str) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader
        except Exception:
            return ""

    try:
        reader = PdfReader(file_path)
        pages = [
            page.extract_text() or ""
            for page in reader.pages
        ]
        return "\n".join(pages).strip()
    except Exception:
        return ""


def _build_fallback_text(file_path: str) -> str:
    path = Path(file_path)
    stem = re.sub(r"_[0-9a-f]{32}$", "", path.stem, flags=re.IGNORECASE)
    return stem.replace("_", " ").replace("-", " ")


def log_ocr_result(result: dict) -> str:
    OCR_LOG_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    target_path = OCR_LOG_ROOT / f"{timestamp}.json"
    target_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(target_path)


def extract_text_from_image(file_path: str) -> dict:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        raw_text = _extract_text_from_pdf(file_path)
        engine = "pdf_text"
    else:
        raw_text = _extract_text_with_tesseract(file_path)
        engine = "tesseract"

    warnings = []

    if not raw_text:
        raw_text = _build_fallback_text(file_path)
        engine = "filename_fallback"
        warnings.append(
            "OCR engine is unavailable or did not find text; filename fallback was used."
        )

    numbers = _extract_numbers(raw_text)
    possible_dimensions = _infer_dimensions_from_text(raw_text, numbers)
    result = {
        "raw_text": raw_text,
        "numbers": numbers,
        "possible_dimensions": possible_dimensions,
        "engine": engine,
        "warnings": warnings,
    }
    result["log_path"] = log_ocr_result(result)
    return result
