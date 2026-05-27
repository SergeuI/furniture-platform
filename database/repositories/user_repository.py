from database.session import (
    SessionLocal
)

from database.models.user import (
    UserModel
)


# =====================================================
# CREATE USER
# =====================================================

def create_user(

    email: str,

    password_hash: str,

    role: str = "manager"
):

    db = SessionLocal()

    try:

        user = UserModel(

            email=email,

            password_hash=password_hash,

            role=role
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

        user.role = role

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
