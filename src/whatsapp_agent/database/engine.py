"""
SQLAlchemy async engine initialization.

Provides a single application-level async engine and connection pool.
Never create engines per-request — always use the module-level instance.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """
    Return the application-level async SQLAlchemy engine.

    Raises:
        RuntimeError: If the engine has not been initialized via init_db().
    """
    if _engine is None:
        raise RuntimeError(
            "Database engine not initialized. Call init_db() during application startup."
        )
    return _engine


async def init_db() -> None:
    """
    Initialize the async SQLAlchemy engine and connection pool.

    Should be called exactly once during application startup (in lifespan).
    Creates all tables if they don't exist (in development only).
    In production, tables are managed by Alembic migrations.
    """
    global _engine

    settings = get_settings()
    database_url = str(settings.database_url)

    logger.info(
        "initializing_database_engine",
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )

    _engine = create_async_engine(
        database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=settings.database_pool_pre_ping,
        echo=settings.database_echo,
        # PostgreSQL-specific: use statement-level timeout to prevent runaway queries
        connect_args={
            "server_settings": {
                "application_name": "whatsapp-agent-api",
                "statement_timeout": "30000",  # 30 seconds
            }
        },
    )

    logger.info("database_engine_initialized")


async def close_db() -> None:
    """
    Dispose of the engine and close all connections in the pool.

    Should be called during application shutdown (in lifespan).
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("database_engine_disposed")
