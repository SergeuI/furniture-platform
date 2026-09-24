from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies.auth import require_current_user, require_roles
from database.repositories.assistant_phrase_repository import (
    list_phrase_mappings,
    list_unknown_phrases,
    map_unknown_phrase,
    record_unknown_phrase,
)
from services.user_roles import ROLE_ADMIN


router = APIRouter()

SUPPORTED_ASSISTANT_ACTION_IDS = {
    "materials.open",
    "fittings.open",
    "mounting_nodes.open",
}


class AssistantUnknownPhraseRequest(BaseModel):
    phrase: str = Field(min_length=1, max_length=2000)


class AssistantPhraseMappingRequest(BaseModel):
    action_id: str = Field(min_length=1, max_length=200)


def _serialize_phrase(record):
    return {
        "id": record.id,
        "normalized_phrase": record.normalized_phrase,
        "original_phrase": record.original_phrase,
        "count": record.count,
        "status": record.status,
        "mapped_action_id": record.mapped_action_id,
        "first_seen": record.first_seen,
        "last_seen": record.last_seen,
    }


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



@router.get("/phrase-mappings")
def get_phrase_mappings(
    current_user = Depends(require_current_user),
):
    records = list_phrase_mappings()

    return {
        "success": True,
        "items": [
            {
                "phrase": record.normalized_phrase,
                "action_id": record.mapped_action_id,
            }
            for record in records
        ],
    }


@router.get("/unknown-phrases")
def get_unknown_phrases(
    status: str | None = "new",
    current_user = Depends(require_roles([ROLE_ADMIN])),
):
    records = list_unknown_phrases(status=status)

    return {
        "success": True,
        "items": [
            _serialize_phrase(record)
            for record in records
        ],
    }


@router.post("/unknown-phrases/{phrase_id}/map")
def assign_unknown_phrase(
    phrase_id: str,
    payload: AssistantPhraseMappingRequest,
    current_user = Depends(require_roles([ROLE_ADMIN])),
):
    action_id = payload.action_id.strip()

    if action_id not in SUPPORTED_ASSISTANT_ACTION_IDS:
        raise HTTPException(
            status_code=422,
            detail="Unsupported assistant action",
        )

    try:
        record = map_unknown_phrase(
            phrase_id=phrase_id,
            action_id=action_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown phrase not found",
        )

    return {
        "success": True,
        "item": _serialize_phrase(record),
    }
