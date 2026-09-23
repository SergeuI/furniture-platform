from datetime import datetime
import re

from sqlalchemy.exc import IntegrityError

from database.session import SessionLocal
from database.models.user import UserModel
from database.models.assistant_unknown_phrase import AssistantUnknownPhraseModel


_TRAILING_PUNCTUATION = re.compile(r"[.,!?;:]+$")


def normalize_phrase(value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = _TRAILING_PUNCTUATION.sub("", normalized)
    return " ".join(normalized.split())


def record_unknown_phrase(
    raw_phrase: str,
    user_id: str | None = None,
):
    normalized_phrase = normalize_phrase(raw_phrase)

    if not normalized_phrase:
        return None

    db = SessionLocal()

    try:
        record = (
            db.query(AssistantUnknownPhraseModel)
            .filter(
                AssistantUnknownPhraseModel.normalized_phrase == normalized_phrase
            )
            .first()
        )

        now = datetime.utcnow()

        if record:
            (
                db.query(AssistantUnknownPhraseModel)
                .filter(AssistantUnknownPhraseModel.id == record.id)
                .update(
                    {
                        AssistantUnknownPhraseModel.count: AssistantUnknownPhraseModel.count + 1,
                        AssistantUnknownPhraseModel.last_seen: now,
                        AssistantUnknownPhraseModel.last_user_id: user_id,
                    },
                    synchronize_session=False,
                )
            )
        else:
            record = AssistantUnknownPhraseModel(
                normalized_phrase=normalized_phrase,
                original_phrase=str(raw_phrase or "").strip(),
                count=1,
                status="new",
                first_seen=now,
                last_seen=now,
                last_user_id=user_id,
            )
            db.add(record)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            record = (
                db.query(AssistantUnknownPhraseModel)
                .filter(
                    AssistantUnknownPhraseModel.normalized_phrase == normalized_phrase
                )
                .first()
            )
            if record is None:
                raise
            (
                db.query(AssistantUnknownPhraseModel)
                .filter(AssistantUnknownPhraseModel.id == record.id)
                .update(
                    {
                        AssistantUnknownPhraseModel.count: AssistantUnknownPhraseModel.count + 1,
                        AssistantUnknownPhraseModel.last_seen: datetime.utcnow(),
                        AssistantUnknownPhraseModel.last_user_id: user_id,
                    },
                    synchronize_session=False,
                )
            )
            db.commit()

        db.refresh(record)

        return record

    finally:
        db.close()
