"""
Pytest configuration and shared fixtures.

Provides:
- Async test support (pytest-asyncio)
- Test database (in-memory SQLite or test PostgreSQL)
- HTTP test client (httpx AsyncClient)
- Settings overrides for test environment
- Factory fixtures for creating test data
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from whatsapp_agent.config.settings import AppSettings, get_settings
from whatsapp_agent.database.base import Base
from whatsapp_agent.database.session import get_db_session


# ── Settings Override ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def override_settings() -> AppSettings:
    """
    Override application settings for the test session.
    Uses an in-memory SQLite database so tests don't need a real PostgreSQL instance.
    """
    import os

    os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_whatsapp_agent")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
    os.environ.setdefault("APP_ENV", "testing")
    os.environ.setdefault("WHATSAPP_PROVIDER", "mock")
    os.environ.setdefault("CRM_PROVIDER", "mock")
    os.environ.setdefault("LLM_PROVIDER", "openai")
    os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")

    # Clear the settings cache to pick up test env vars
    get_settings.cache_clear()
    settings = get_settings()
    return settings


# ── Async Event Loop ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.DefaultEventLoopPolicy:
    """Use the default asyncio event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


# ── Test Database ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[Any, None]:
    """
    Create a test database engine.

    Uses a real PostgreSQL test database. Requires TEST_DATABASE_URL or
    falls back to the DATABASE_URL with a '_test' suffix.
    """
    import os
    test_db_url = os.getenv(
        "TEST_DATABASE_URL",
        os.getenv("DATABASE_URL", "").replace(
            "/whatsapp_agent", "/whatsapp_agent_test"
        ),
    )
    engine = create_async_engine(test_db_url, echo=False)

    async with engine.begin() as conn:
        # Import all models to register with Base.metadata
        import whatsapp_agent.database.models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an isolated database session for each test.
    Wraps each test in a transaction that is rolled back after the test,
    ensuring test isolation without needing to truncate tables.
    """
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


# ── HTTP Test Client ───────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an async HTTP test client for the FastAPI application.
    Overrides the DB session dependency to use the isolated test session.
    """
    from apps.api.main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ── Mock Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_openai_client() -> AsyncMock:
    """Mock OpenAI client for LLM tests."""
    mock = AsyncMock()
    mock.chat.completions.create.return_value = AsyncMock(
        choices=[
            AsyncMock(
                message=AsyncMock(
                    content="This is a test response from the mock LLM.",
                    role="assistant",
                )
            )
        ],
        usage=AsyncMock(prompt_tokens=50, completion_tokens=20, total_tokens=70),
    )
    return mock


@pytest.fixture
def sample_workspace_id() -> uuid.UUID:
    """A fixed workspace UUID for test isolation."""
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    """A fixed user UUID for test auth context."""
    return uuid.UUID("87654321-4321-8765-4321-876543218765")


# ── WhatsApp Webhook Fixture ────────────────────────────────────────────────────

@pytest.fixture
def sample_text_webhook_payload() -> dict[str, Any]:
    """Sample WhatsApp Cloud API webhook payload for a text message."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID_123",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "919876543210",
                                "phone_number_id": "PHONE_NUMBER_ID_123",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Test Customer"},
                                    "wa_id": "919123456789",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "919123456789",
                                    "id": "wamid.HBgLOTE5MTIz",
                                    "timestamp": "1727000000",
                                    "type": "text",
                                    "text": {"body": "Hi, I need help with your products."},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


@pytest.fixture
def sample_voice_webhook_payload() -> dict[str, Any]:
    """Sample WhatsApp Cloud API webhook payload for a voice note."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID_123",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "919876543210",
                                "phone_number_id": "PHONE_NUMBER_ID_123",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Test Customer"},
                                    "wa_id": "919123456789",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "919123456789",
                                    "id": "wamid.HBgLOTE5MTIz_audio",
                                    "timestamp": "1727000001",
                                    "type": "audio",
                                    "audio": {
                                        "mime_type": "audio/ogg; codecs=opus",
                                        "sha256": "abc123def456",
                                        "id": "MEDIA_ID_AUDIO_123",
                                        "voice": True,
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
