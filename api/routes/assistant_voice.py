from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.dependencies.auth import require_current_user
from services.assistant_voice_provider import AssistantVoiceProviderError
from services.assistant_voice_service import AssistantVoiceService


router = APIRouter()

DEV_VOICE_ID = "Xb7hH8MSUJpSbSDYk0k2"
DEV_LANGUAGE = "uk-UA"


class AssistantVoiceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/voice")
def generate_assistant_voice(
    payload: AssistantVoiceRequest,
    current_user = Depends(require_current_user),
):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text is required")

    service = AssistantVoiceService()

    try:
        result = service.generate_mp3(
            text=text,
            voice_id=DEV_VOICE_ID,
            language=DEV_LANGUAGE,
        )
    except AssistantVoiceProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail="Assistant voice provider failed",
        ) from exc

    response = StreamingResponse(
        BytesIO(result.audio),
        media_type="audio/mpeg",
    )
    response.headers["X-MPFC-Voice-Cache"] = "HIT" if result.cache_hit else "MISS"
    return response
