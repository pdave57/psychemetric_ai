"""Shared pytest fixtures for in-memory SQLite test databases.

Each test gets a fresh schema via ``Base.metadata.create_all`` and a
``Session`` that is closed and torn down after the test completes.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import *  # noqa: F401, F403 — ensures all tables are registered


@pytest.fixture()
def db():
    """Yield an in-memory SQLite session with the full v2 schema."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Testing = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = Testing()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(db):
    """Yield a FastAPI TestClient configured to use the in-memory test db."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

