"""
backend/tests/conftest.py

Global test fixtures for Kagaz backend test suite.
Per Kagaz database architecture (database/db.md), unit and integration tests
run against an isolated in-memory SQLite database with foreign key enforcement
enabled (PRAGMA foreign_keys=ON) unless explicitly configured otherwise.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from main import app


@pytest.fixture(autouse=True)
def default_test_db(monkeypatch):
    """Provide a fallback SQLite test database with all tables created.

    Ensures that existing API tests that do not configure an explicit DB
    execute against a clean, foreign-key-enforced database instead of failing
    on an unavailable localhost PostgreSQL connection.
    """
    # If the test already overrides get_db, do not interfere
    if get_db in app.dependency_overrides:
        yield
        return

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    app.dependency_overrides[get_db] = lambda: session

    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

