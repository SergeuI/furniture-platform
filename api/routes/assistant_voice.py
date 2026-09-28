from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.dependencies.auth import require_current_user
from services.assistant_voice_provider import AssistantVoiceProviderError
from services.assistant_voice_service import AssistantVoiceService
from services.assistant_voice_config import get_assistant_voice_id


router = APIRouter()

DEV_LANGUAGE = "uk-UA"


class AssistantVoiceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice_profile: str = Field(default="male", pattern="^(male|female)$")


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
            voice_id=get_assistant_voice_id(payload.voice_profile),
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
