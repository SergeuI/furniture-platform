DEFAULT_PROJECT_DIMENSIONS = {
    "width": 1000,
    "height": 800,
    "depth": 450,
}

PROJECT_TYPE_LABELS = {
    "dresser": "\u041a\u043e\u043c\u043e\u0434",
    "wardrobe": "\u0428\u0430\u0444\u0430",
    "cabinet": "\u0422\u0443\u043c\u0431\u0430",
    "kitchen": "\u041a\u0443\u0445\u043d\u044f",
    "drawer_unit": "\u0411\u043b\u043e\u043a \u0448\u0443\u0445\u043b\u044f\u0434",
}


def _build_form_defaults(project_type: str, dimensions: dict, raw_text: str) -> dict:
    project_label = PROJECT_TYPE_LABELS.get(project_type, project_type)

    return {
        "projectName": f"AI: {project_label}",
        "projectType": project_type,
        "width": dimensions["width"],
        "height": dimensions["height"],
        "depth": dimensions["depth"],
        "notes": raw_text or "",
    }


def build_project_from_scan(scan_result: dict) -> dict:
    ocr_result = scan_result.get("ocr") or {}
    detection = scan_result.get("furniture_detection") or {}
    dimensions = ocr_result.get("possible_dimensions") or {}
    missing_fields = []

    for field in ("width", "height", "depth"):
        if not dimensions.get(field):
            missing_fields.append(field)

    for field in ("material", "hardware", "handles", "edge_type"):
        missing_fields.append(field)

    project_type = detection.get("type") or "dresser"
    raw_text = ocr_result.get("raw_text", "")
    project_dimensions = {
        **DEFAULT_PROJECT_DIMENSIONS,
        **{
            key: int(value)
            for key, value in dimensions.items()
            if key in DEFAULT_PROJECT_DIMENSIONS and value
        },
    }

    return {
        "source": "image_scan",
        "type": project_type,
        "width": project_dimensions["width"],
        "height": project_dimensions["height"],
        "depth": project_dimensions["depth"],
        "status": "needs_user_confirmation",
        "missing_fields": missing_fields,
        "confidence": detection.get("confidence", 0),
        "detected_features": detection.get("detected_features", []),
        "raw_text": raw_text,
        "numbers": ocr_result.get("numbers", []),
        "ocr_engine": ocr_result.get("engine"),
        "ocr_warnings": ocr_result.get("warnings", []),
        "ocr_log_path": ocr_result.get("log_path"),
        "form_defaults": _build_form_defaults(
            project_type,
            project_dimensions,
            raw_text,
        ),
    }
