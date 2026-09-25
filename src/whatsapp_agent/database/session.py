"""
SQLAlchemy async session factory and FastAPI dependency.

Provides a scoped async session per-request via FastAPI dependency injection.
Always use `get_db_session` as a FastAPI Depends to obtain a session.
Never share sessions across requests or background tasks.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from whatsapp_agent.database.engine import get_engine

# Session factory — created lazily on first use
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # Prevent lazy-loading after commit in async context
            autocommit=False,
            autoflush=False,
        )
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session per request.

    Ensures:
    - Session is committed on success
    - Session is rolled back on any exception
    - Session is always closed after the request

    Usage:
        @router.get("/example")
        async def endpoint(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session_no_commit() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async session WITHOUT auto-commit.

    Use for read-only operations or when you need manual transaction control.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()
