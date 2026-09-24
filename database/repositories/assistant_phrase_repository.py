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
            if record.status == "mapped":
                return record

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
            if record.status == "mapped":
                return record
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


def list_unknown_phrases(
    status: str | None = "new",
):
    db = SessionLocal()

    try:
        query = db.query(AssistantUnknownPhraseModel)

        if status:
            query = query.filter(
                AssistantUnknownPhraseModel.status == status
            )

        return (
            query
            .order_by(
                AssistantUnknownPhraseModel.count.desc(),
                AssistantUnknownPhraseModel.last_seen.desc(),
            )
            .all()
        )

    finally:
        db.close()



def list_phrase_mappings():
    db = SessionLocal()

    try:
        return (
            db.query(AssistantUnknownPhraseModel)
            .filter(
                AssistantUnknownPhraseModel.status == "mapped",
                AssistantUnknownPhraseModel.mapped_action_id.isnot(None),
            )
            .order_by(AssistantUnknownPhraseModel.normalized_phrase.asc())
            .all()
        )
    finally:
        db.close()

def map_unknown_phrase(
    phrase_id: str,
    action_id: str,
):
    db = SessionLocal()

    try:
        record = (
            db.query(AssistantUnknownPhraseModel)
            .filter(AssistantUnknownPhraseModel.id == phrase_id)
            .first()
        )

        if record is None:
            return None

        new_action_id = str(action_id or "").strip()
        if not new_action_id:
            raise ValueError("action_id is required")

        existing_action_id = str(record.mapped_action_id or "").strip()
        if existing_action_id:
            if existing_action_id == new_action_id:
                return record
            raise ValueError("phrase is already mapped to another action")

        record.mapped_action_id = new_action_id
        record.status = "mapped"

        db.commit()
        db.refresh(record)

        return record

    finally:
        db.close()
