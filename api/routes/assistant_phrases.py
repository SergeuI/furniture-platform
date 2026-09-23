from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies.auth import require_current_user
from database.repositories.assistant_phrase_repository import record_unknown_phrase


router = APIRouter()


class AssistantUnknownPhraseRequest(BaseModel):
    phrase: str = Field(min_length=1, max_length=2000)


@router.post("/unknown-phrases")
def capture_unknown_phrase(
    payload: AssistantUnknownPhraseRequest,
    current_user = Depends(require_current_user),
):
    phrase = payload.phrase.strip()

    if not phrase:
        raise HTTPException(status_code=422, detail="Phrase is required")

    record = record_unknown_phrase(
        raw_phrase=phrase,
        user_id=current_user.id,
    )

    if record is None:
        raise HTTPException(status_code=422, detail="Phrase is required")

    return {
        "success": True,
        "id": record.id,
        "normalized_phrase": record.normalized_phrase,
        "count": record.count,
        "status": record.status,
    }
