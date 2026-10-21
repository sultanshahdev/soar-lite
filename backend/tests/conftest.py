"""Shared fixtures; PostgreSQL tests require an explicitly disposable database."""

import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.main import app
from app.persistence.database import get_db


def reset_disposable_schema(engine) -> None:
    """Erase only the dedicated test schema, including stale Alembic metadata."""
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="session")
def test_engine():
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    if "soar_lite_test" not in database_url:
        raise RuntimeError("TEST_DATABASE_URL must target a disposable soar_lite_test database")

    engine = create_engine(database_url, future=True)
    reset_disposable_schema(engine)
    with engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    try:
        yield engine
    finally:
        reset_disposable_schema(engine)
        engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def api_client(db_session: Session):
    settings = Settings(
        database_url=str(db_session.bind.url),
        webhook_secret="test-webhook-secret",
        analyst_api_key="test-analyst-key",
    )

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = override_db
    try:
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def alert_payload() -> dict[str, object]:
    return {
        "event_id": "test-alert-001",
        "event_type": "suspicious_login",
        "severity": "high",
        "observed_at": "2026-10-21T16:00:00Z",
        "source_ip": "198.51.100.23",
        "destination_host": "lab-server-01",
        "rule": "Repeated failed login attempts",
        "metadata": {"failed_attempts": 12, "window_seconds": 60},
    }


@pytest.fixture
def webhook_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-webhook-secret", "Content-Type": "application/json"}


@pytest.fixture
def analyst_headers() -> dict[str, str]:
    return {"X-API-Key": "test-analyst-key"}
