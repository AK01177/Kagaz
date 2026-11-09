import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/kagaz",
)

connect_args = {}
if "postgresql" in DATABASE_URL:
    connect_args["connect_timeout"] = 2

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception:
    engine = None
    SessionLocal = None


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    if SessionLocal is None:
        yield None
        return

    try:
        db = SessionLocal()
    except Exception:
        yield None
        return

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        try:
            db.close()
        except Exception:
            pass
        yield None
        return

    try:
        yield db
    finally:
        try:
            db.close()
        except Exception:
            pass
