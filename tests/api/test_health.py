"""
Tests for the health check endpoints.

Verifies:
- GET /health returns correct structure
- GET /health/live always returns 200
- Health response includes version and service statuses
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestHealthLive:
    """Tests for the lightweight liveness probe."""

    @pytest.mark.asyncio
    async def test_liveness_returns_200(self, client: AsyncClient) -> None:
        """GET /health/live should always return 200 when the process is alive."""
        response = await client.get("/health/live")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_liveness_returns_alive_status(self, client: AsyncClient) -> None:
        """GET /health/live should return status: alive."""
        response = await client.get("/health/live")
        data = response.json()
        assert data["status"] == "alive"


class TestHealthReadiness:
    """Tests for the full readiness health check."""

    @pytest.mark.asyncio
    async def test_health_check_returns_response_structure(self, client: AsyncClient) -> None:
        """GET /health should return a response with the expected structure."""
        response = await client.get("/health")
        # Status is 200 (healthy) or 503 (unhealthy) — both have valid response bodies
        assert response.status_code in (200, 503)
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "environment" in data
        assert "uptime_seconds" in data
        assert "services" in data
        assert isinstance(data["services"], list)

    @pytest.mark.asyncio
    async def test_health_check_version(self, client: AsyncClient) -> None:
        """Health response should include a version string."""
        response = await client.get("/health")
        data = response.json()
        assert data["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_health_check_environment(self, client: AsyncClient) -> None:
        """Health response should reflect the test environment."""
        response = await client.get("/health")
        data = response.json()
        assert data["environment"] == "testing"

    @pytest.mark.asyncio
    async def test_health_check_services_structure(self, client: AsyncClient) -> None:
        """Each service in the health response should have name and status fields."""
        response = await client.get("/health")
        data = response.json()

        for service in data["services"]:
            assert "name" in service
            assert "status" in service
            assert service["status"] in ("ok", "degraded", "unavailable")

    @pytest.mark.asyncio
    async def test_health_includes_postgresql_service(self, client: AsyncClient) -> None:
        """Health response should include the PostgreSQL service check."""
        response = await client.get("/health")
        data = response.json()

        service_names = [s["name"] for s in data["services"]]
        assert "postgresql" in service_names
