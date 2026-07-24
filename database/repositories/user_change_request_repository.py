from datetime import datetime

from database.session import SessionLocal

from database.models.user_change_request import (
    UserChangeRequestModel,
)


def create_user_change_request(
    user_id: str,
    change_type: str,
    old_value: str | None,
    new_value: str,
):

    db = SessionLocal()

    try:

        request = UserChangeRequestModel(
            user_id=user_id,
            change_type=change_type,
            old_value=old_value,
            new_value=new_value,
            status="pending",
            created_at=datetime.utcnow(),
        )

        db.add(request)
        db.commit()
        db.refresh(request)

        return request

    finally:

        db.close()


def get_pending_change_request(
    user_id: str,
    change_type: str,
):

    db = SessionLocal()

    try:

        return (
            db.query(UserChangeRequestModel)
            .filter(
                UserChangeRequestModel.user_id == user_id,
                UserChangeRequestModel.change_type == change_type,
                UserChangeRequestModel.status == "pending",
            )
            .order_by(UserChangeRequestModel.created_at.desc())
            .first()
        )

    finally:

        db.close()


def list_user_change_requests(
    limit: int | None = None,
    offset: int = 0,
    status: str | None = None,
):

    db = SessionLocal()

    try:

        query = db.query(UserChangeRequestModel).order_by(
            UserChangeRequestModel.created_at.desc()
        )

        if status:
            query = query.filter(
                UserChangeRequestModel.status == status
            )

        if offset > 0:
            query = query.offset(offset)

        if limit is not None:
            query = query.limit(limit)

        return query.all()

    finally:

        db.close()


def get_user_change_request_by_id(
    request_id: str,
):

    db = SessionLocal()

    try:

        return (
            db.query(UserChangeRequestModel)
            .filter(
                UserChangeRequestModel.id == request_id
            )
            .first()
        )

    finally:

        db.close()


def review_user_change_request(
    request_id: str,
    status: str,
    reviewed_by_user_id: str,
):

    db = SessionLocal()

    try:

        request = (
            db.query(UserChangeRequestModel)
            .filter(
                UserChangeRequestModel.id == request_id
            )
            .first()
        )

        if not request:
            return None

        request.status = status
        request.reviewed_by_user_id = reviewed_by_user_id
        request.reviewed_at = datetime.utcnow()

        db.commit()
        db.refresh(request)

        return request

    finally:

        db.close()
