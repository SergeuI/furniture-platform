from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.legacy_db_config import DEFAULT_DB_PATH

DATABASE_URL = f"sqlite:///{Path(DEFAULT_DB_PATH).as_posix()}"


engine = create_engine(

    DATABASE_URL,

    connect_args={
        "check_same_thread": False
    }
)

SessionLocal = sessionmaker(

    autocommit=False,

    autoflush=False,

    bind=engine
)
