from sqlalchemy import and_, func

from database.session import (
    SessionLocal
)

from database.models.user import (
    UserModel
)
from datetime import datetime
from services.user_roles import (
    normalize_user_role,
)


_UNSET = object()


# =====================================================
# CREATE USER
# =====================================================

def create_user(

    email: str,

    password_hash: str,

    role: str = "free"
):

    db = SessionLocal()

    try:

        user = UserModel(

            email=email,

            username=email.split("@")[0],

            password_hash=password_hash,

            role=normalize_user_role(role)
        )

        db.add(user)

        db.commit()

        db.refresh(user)

        return user

    finally:

        db.close()


# =====================================================
# GET USER BY EMAIL
# =====================================================

def get_user_by_email(

    email: str
):

    db = SessionLocal()

    try:

        return (

            db.query(UserModel)

            .filter(

                UserModel.email == email
            )

            .first()
        )

    finally:

        db.close()


# =====================================================
# GET USER BY ID
# =====================================================

def get_user_by_id(

    user_id: str
):

    db = SessionLocal()

    try:

        return (

            db.query(UserModel)

            .filter(

                UserModel.id == user_id
            )

            .first()
        )

    finally:

        db.close()


# =====================================================
# LIST USERS
# =====================================================

def list_users(

    limit: int = 50,

    offset: int = 0
):

    db = SessionLocal()

    try:

        return (

            db.query(UserModel)

            .order_by(

                UserModel.email.asc()
            )

            .offset(offset)

            .limit(limit)

            .all()
        )

    finally:

        db.close()


def list_viyar_autosync_users(
    limit: int = 20,
):

    db = SessionLocal()

    try:

        return (
            db.query(UserModel)
            .filter(UserModel.is_active.is_(True))
            .filter(
                (UserModel.viyar_cookie.isnot(None))
                | and_(
                    UserModel.viyar_email.isnot(None),
                    UserModel.viyar_password_secret.isnot(None),
                )
            )
            .order_by(UserModel.email.asc())
            .limit(limit)
            .all()
        )

    finally:

        db.close()


# =====================================================
# COUNT USERS
# =====================================================

def count_users() -> int:

    db = SessionLocal()

    try:

        return (

            db.query(UserModel)

            .count()
        )

    finally:

        db.close()


# =====================================================
# UPDATE USER ROLE
# =====================================================

def update_user_role(

    user_id: str,

    role: str
):

    db = SessionLocal()

    try:

        user = (

            db.query(UserModel)

            .filter(

                UserModel.id == user_id
            )

            .first()
        )

        if not user:

            return None

        user.role = normalize_user_role(role)

        db.commit()

        db.refresh(user)

        return user

    finally:

        db.close()


# =====================================================
# SET USER ACTIVE
# =====================================================

def set_user_active(

    user_id: str,

    is_active: bool
):

    db = SessionLocal()

    try:

        user = (

            db.query(UserModel)

            .filter(

                UserModel.id == user_id
            )

            .first()
        )

        if not user:

            return None

        user.is_active = is_active

        db.commit()

        db.refresh(user)

        return user

    finally:

        db.close()


# =====================================================
# UPDATE USER PASSWORD
# =====================================================

def update_user_password(

    user_id: str,

    password_hash: str
):

    db = SessionLocal()

    try:

        user = (

            db.query(UserModel)

            .filter(

                UserModel.id == user_id
            )

            .first()
        )

        if not user:

            return None

        user.password_hash = password_hash

        db.commit()

        db.refresh(user)

        return user

    finally:

        db.close()


def update_user_viyar_credentials(

    user_id: str,

    viyar_email: str | None,

    viyar_password_secret: str | None = None
):

    db = SessionLocal()

    try:

        user = (

            db.query(UserModel)

            .filter(

                UserModel.id == user_id
            )

            .first()
        )

        if not user:

            return None

        credentials_changed = user.viyar_email != viyar_email or viyar_password_secret is not None

        user.viyar_email = viyar_email

        if viyar_password_secret is not None:

            user.viyar_password_secret = viyar_password_secret

        if credentials_changed:

            user.viyar_cookie = None
            user.viyar_cookie_updated_at = None
            user.viyar_last_auth_status = None
            user.viyar_last_auth_error = None

        db.commit()

        db.refresh(user)

        return user

    finally:

        db.close()


def update_user_viyar_session(

    user_id: str,

    viyar_cookie: str | None,

    status: str,

    error: str | None = None
):

    db = SessionLocal()

    try:

        user = (

            db.query(UserModel)

            .filter(

                UserModel.id == user_id
            )

            .first()
        )

        if not user:

            return None

        now = datetime.utcnow()

        user.viyar_last_auth_at = now
        user.viyar_last_auth_status = status
        user.viyar_last_auth_error = error

        if viyar_cookie:

            user.viyar_cookie = viyar_cookie
            user.viyar_cookie_updated_at = now

        elif status != "connected":

            user.viyar_cookie = None
            user.viyar_cookie_updated_at = None

        db.commit()

        db.refresh(user)

        return user

    finally:

        db.close()


def get_user_by_username(

    username: str
):

    normalized_username = username.strip().lower()

    db = SessionLocal()

    try:

        return (

            db.query(UserModel)

            .filter(

                func.lower(UserModel.username) == normalized_username
            )

            .first()
        )

    finally:

        db.close()


def get_user_by_telegram_id(

    telegram_id: str
):

    db = SessionLocal()

    try:

        return (

            db.query(UserModel)

            .filter(

                UserModel.telegram_id == str(telegram_id)
            )

            .first()
        )

    finally:

        db.close()


def update_user_profile(

    user_id: str,

    phone: str | None | object = _UNSET,

    city: str | None | object = _UNSET,

    username: str | None = None,

    telegram_id: str | None = None,

    mark_username_changed: bool = False
):

    db = SessionLocal()

    try:

        user = (

            db.query(UserModel)

            .filter(

                UserModel.id == user_id
            )

            .first()
        )

        if not user:

            return None

        if phone is not _UNSET:
            user.phone = phone

        if city is not _UNSET:
            user.city = city

        if username is not None:

            user.username = username

        if telegram_id is not None:

            user.telegram_id = str(telegram_id)

        if mark_username_changed:

            user.last_username_change_at = datetime.utcnow()

        db.commit()

        db.refresh(user)

        return user

    finally:

        db.close()


def update_user_email(

    user_id: str,

    email: str
):

    db = SessionLocal()

    try:

        user = (

            db.query(UserModel)

            .filter(

                UserModel.id == user_id
            )

            .first()
        )

        if not user:

            return None

        user.email = email

        db.commit()

        db.refresh(user)

        return user

    finally:

        db.close()
