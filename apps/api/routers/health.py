"""
Health check router.

Provides endpoints for liveness and readiness checks used by Docker,
load balancers, and monitoring systems.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp_agent.config.settings import AppSettings, get_settings
from whatsapp_agent.database.session import get_db_session
from whatsapp_agent.observability.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

_start_time = time.time()


class ServiceStatus(BaseModel):
    """Status of an individual downstream service."""

    name: str
    status: str  # "ok" | "degraded" | "unavailable"
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    """
    Health check response body.

    Used by:
    - Docker HEALTHCHECK
    - Kubernetes liveness/readiness probes
    - Load balancer health checks
    - Monitoring dashboards
    """

    status: str  # "healthy" | "degraded" | "unhealthy"
    version: str
    environment: str
    uptime_seconds: float
    services: list[ServiceStatus]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Readiness health check",
    description=(
        "Returns the overall platform health including downstream service connectivity. "
        "Returns HTTP 200 if healthy, 503 if any critical service is unavailable."
    ),
    responses={
        200: {"description": "Platform is healthy"},
        503: {"description": "One or more critical services are unavailable"},
    },
)
async def health_check(
    db: AsyncSession = Depends(get_db_session),
    settings: AppSettings = Depends(get_settings),
) -> Any:
    """
    Perform a full readiness check.

    Tests:
    - Database connectivity (SELECT 1)
    - Overall platform readiness

    Returns HTTP 503 if the database is unavailable.
    """
    services: list[ServiceStatus] = []
    overall_healthy = True

    # ── Database Check ─────────────────────────────────────────────────────────
    db_start = time.monotonic()
    try:
        await db.execute(text("SELECT 1"))
        db_latency = round((time.monotonic() - db_start) * 1000, 2)
        services.append(
            ServiceStatus(name="postgresql", status="ok", latency_ms=db_latency)
        )
        logger.debug("health_check_db_ok", latency_ms=db_latency)
    except Exception as exc:
        db_latency = round((time.monotonic() - db_start) * 1000, 2)
        services.append(
            ServiceStatus(
                name="postgresql",
                status="unavailable",
                latency_ms=db_latency,
                detail="Database connection failed",
            )
        )
        overall_healthy = False
        logger.error("health_check_db_failed", exc_info=exc)

    uptime = round(time.time() - _start_time, 1)
    overall_status = "healthy" if overall_healthy else "unhealthy"

    response = HealthResponse(
        status=overall_status,
        version="0.1.0",
        environment=settings.app_env.value,
        uptime_seconds=uptime,
        services=services,
    )

    http_status = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    if not overall_healthy:
        logger.warning("health_check_failed", status=overall_status, services=[s.model_dump() for s in services])

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=http_status,
        content=response.model_dump(),
    )


@router.get(
    "/health/live",
    summary="Liveness probe",
    description="Lightweight liveness check — returns 200 if the process is alive.",
    status_code=status.HTTP_200_OK,
)
async def liveness_probe() -> dict[str, str]:
    """
    Kubernetes/Docker liveness probe.

    Only checks if the process is running. Does NOT check downstream services.
    Return 200 if alive (process is not deadlocked).
    """
    return {"status": "alive"}
