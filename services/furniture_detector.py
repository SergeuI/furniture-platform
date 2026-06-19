FURNITURE_KEYWORDS = [
    (
        "kitchen",
        [
            "\u043a\u0443\u0445\u043d\u044f",
            "\u043a\u0443\u0445\u043e\u043d\u043d",
            "\u0441\u0442\u0456\u043b\u044c\u043d\u0438\u0446",
            "\u0441\u0442\u043e\u043b\u0435\u0448",
            "\u0444\u0430\u0440\u0442\u0443\u0445",
            "kuhnya",
            "kitchen",
            "worktop",
            "countertop",
            "base cabinet",
            "wall cabinet",
        ],
    ),
    (
        "wardrobe",
        [
            "\u0448\u0430\u0444\u0430",
            "\u0448\u043a\u0430\u0444",
            "\u0433\u0430\u0440\u0434\u0435\u0440\u043e\u0431",
            "\u0433\u0430\u0440\u0434\u0435\u0440\u043e\u0431\u043d",
            "\u043a\u0443\u043f\u0435",
            "shafa",
            "wardrobe",
            "closet",
        ],
    ),
    (
        "dresser",
        [
            "\u043a\u043e\u043c\u043e\u0434",
            "\u0448\u0443\u0445\u043b\u044f\u0434",
            "\u044f\u0449\u0438\u043a",
            "\u0441\u043a\u0440\u0438\u043d",
            "komod",
            "dresser",
            "chest",
            "drawer unit",
        ],
    ),
    (
        "cabinet",
        [
            "\u0442\u0443\u043c\u0431\u0430",
            "\u043f\u0435\u043d\u0430\u043b",
            "\u043a\u043e\u0440\u043f\u0443\u0441",
            "tumba",
            "penal",
            "cabinet",
            "case",
        ],
    ),
]


def detect_furniture_type(image_path: str, extracted_text: str) -> dict:
    normalized_text = (extracted_text or "").lower()
    scored_matches = []

    for furniture_type, keywords in FURNITURE_KEYWORDS:
        matched = [
            keyword
            for keyword in keywords
            if keyword.lower() in normalized_text
        ]

        if matched:
            scored_matches.append(
                {
                    "type": furniture_type,
                    "score": len(matched),
                    "detected_features": matched,
                }
            )

    if not scored_matches:
        return {
            "type": "dresser",
            "confidence": 0.35,
            "detected_features": [],
            "reason": "No keyword match; default project type selected for confirmation.",
        }

    best_match = sorted(
        scored_matches,
        key=lambda item: item["score"],
        reverse=True,
    )[0]
    confidence = min(0.55 + best_match["score"] * 0.12, 0.92)

    return {
        "type": best_match["type"],
        "confidence": round(confidence, 2),
        "detected_features": best_match["detected_features"],
    }
