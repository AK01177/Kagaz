import os
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/kagaz",
)

_engines: dict = {}


def get_engine(url: str | None = None):
    db_url = url or os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/kagaz",
    )
    if db_url not in _engines:
        if db_url.startswith("sqlite"):
            engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool if ":memory:" in db_url else None,
            )

            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

            _engines[db_url] = engine
        else:
            _engines[db_url] = create_engine(db_url, pool_pre_ping=True)
    return _engines[db_url]


def SessionLocal(url: str | None = None):
    engine = get_engine(url)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return factory()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
