"""
FastAPI application entry point.

Sets up the app lifecycle, middleware, routers, and exception handlers.
Business logic is NOT placed here — only application wiring.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.core.errors import register_exception_handlers
from whatsapp_agent.database.engine import close_db, init_db
from whatsapp_agent.observability.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)
from arq import create_pool
from arq.connections import RedisSettings

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown procedures:
    - Startup: configure logging, initialize DB connection pool
    - Shutdown: close DB connections gracefully
    """
    # ── Startup ────────────────────────────────────────────────────────────────
    configure_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
    )
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        environment=settings.app_env.value,
        version=app.version,
        llm_provider=settings.llm_provider.value,
        whatsapp_provider=settings.whatsapp_provider.value,
        crm_provider=settings.crm_provider.value,
    )

    await init_db()
    logger.info("database_connection_pool_initialized")
    
    # Initialize ARQ Redis pool for enqueuing jobs
    app.state.redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    logger.info("arq_redis_pool_initialized")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("application_shutting_down")
    if hasattr(app.state, "redis_pool"):
        await app.state.redis_pool.close()
    await close_db()
    logger.info("database_connection_pool_closed")


def create_application() -> FastAPI:
    """
    Factory function that creates and configures the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Multimodal Agentic WhatsApp AI Automation Platform — "
            "AI-powered business communication, CRM, voice, and knowledge automation."
        ),
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # ── CORS Middleware ────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request Context Middleware ─────────────────────────────────────────────
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next: Any) -> Response:
        """
        Attach a unique request_id to every request and bind it to the log context.
        Measures and logs request duration.
        """
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        bind_request_context(request_id=request_id)
        start_time = time.monotonic()

        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code if "response" in dir() else 500,
                duration_ms=duration_ms,
            )
            clear_request_context()

        response.headers["X-Request-ID"] = request_id
        return response

    # ── Exception Handlers ─────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ────────────────────────────────────────────────────────────────
    from apps.api.routers.health import router as health_router

    app.include_router(health_router, tags=["Health"])

    # Versioned API routers (added as each phase is implemented)
    from apps.api.routers.auth import router as auth_router
    from apps.api.routers.webhooks import router as webhooks_router
    from apps.api.routers.conversations import router as conversations_router
    from apps.api.routers.workspaces import router as workspaces_router

    app.include_router(auth_router, prefix=settings.api_v1_prefix, tags=["Auth"])
    app.include_router(webhooks_router, prefix=settings.api_v1_prefix, tags=["Webhooks"])
    app.include_router(conversations_router, prefix=settings.api_v1_prefix, tags=["Conversations"])
    app.include_router(workspaces_router, prefix=settings.api_v1_prefix, tags=["Workspaces"])

    logger.info("routers_registered")
    return app


# Type annotation fix for middleware lambda
from typing import Any  # noqa: E402

app = create_application()
