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
