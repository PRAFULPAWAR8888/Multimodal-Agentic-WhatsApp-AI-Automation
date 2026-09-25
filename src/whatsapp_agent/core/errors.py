"""
Error response schemas and FastAPI exception handlers.

Provides consistent, safe error responses to API clients.
Never expose internal stack traces, sensitive data, or raw exception messages
directly to clients in production.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from whatsapp_agent.core.exceptions import (
    AgentError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConflictError,
    MediaValidationError,
    NotFoundError,
    PayloadTooLargeError,
    ProviderError,
    RateLimitError,
    RetrievalError,
    ToolExecutionError,
    ToolPermissionError,
    ValidationError,
    WhatsAppAgentError,
    WorkspaceIsolationError,
)
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)


class ErrorDetail(BaseModel):
    """Individual error detail item."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """
    Standardized API error response body.

    All error responses from the API use this schema, allowing clients
    to reliably parse errors regardless of the error type.
    """

    error: str
    code: str
    message: str
    request_id: str
    details: list[ErrorDetail] = []


def _make_error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    """Build a JSONResponse from error components."""
    body = ErrorResponse(
        error=_status_to_error_name(status_code),
        code=code,
        message=message,
        request_id=request_id,
        details=details or [],
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
    )


def _status_to_error_name(status_code: int) -> str:
    """Convert HTTP status code to a human-readable error category name."""
    mapping = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        413: "Payload Too Large",
        415: "Unsupported Media Type",
        422: "Validation Error",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
    }
    return mapping.get(status_code, "Error")


def _get_request_id(request: Request) -> str:
    """Extract or generate a request ID for correlation."""
    # Check if middleware already set it (e.g., X-Request-ID header)
    return getattr(request.state, "request_id", str(uuid.uuid4()))


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all custom exception handlers on the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(RequestValidationError)
    async def pydantic_validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Handle Pydantic v2 request validation errors."""
        request_id = _get_request_id(request)
        details = [
            ErrorDetail(
                field=" → ".join(str(loc) for loc in error["loc"]),
                message=error["msg"],
                code=error["type"],
            )
            for error in exc.errors()
        ]
        logger.warning(
            "request_validation_failed",
            request_id=request_id,
            path=str(request.url.path),
            error_count=len(details),
        )
        return _make_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message="Request validation failed. Check the 'details' field for specifics.",
            request_id=request_id,
            details=details,
        )

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        request: Request,
        exc: AuthenticationError,
    ) -> JSONResponse:
        """Handle authentication failures."""
        request_id = _get_request_id(request)
        logger.warning(
            "authentication_failed",
            request_id=request_id,
            code=exc.code,
            path=str(request.url.path),
        )
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(
        request: Request,
        exc: AuthorizationError,
    ) -> JSONResponse:
        """Handle authorization failures."""
        request_id = _get_request_id(request)
        logger.warning(
            "authorization_failed",
            request_id=request_id,
            code=exc.code,
            path=str(request.url.path),
        )
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(WorkspaceIsolationError)
    async def workspace_isolation_error_handler(
        request: Request,
        exc: WorkspaceIsolationError,
    ) -> JSONResponse:
        """
        Handle cross-workspace isolation violations.
        This is a critical security event — always log it with high priority.
        """
        request_id = _get_request_id(request)
        logger.error(
            "SECURITY: workspace_isolation_violation",
            request_id=request_id,
            path=str(request.url.path),
            details=exc.details,
        )
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message="Access denied.",  # Safe generic message
            request_id=request_id,
        )

    @app.exception_handler(ToolPermissionError)
    async def tool_permission_error_handler(
        request: Request,
        exc: ToolPermissionError,
    ) -> JSONResponse:
        """Handle tool permission denials (always audit)."""
        request_id = _get_request_id(request)
        logger.warning(
            "tool_permission_denied",
            request_id=request_id,
            code=exc.code,
            details=exc.details,
        )
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(
        request: Request,
        exc: NotFoundError,
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(ConflictError)
    async def conflict_error_handler(
        request: Request,
        exc: ConflictError,
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(
        request: Request,
        exc: ValidationError,
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(PayloadTooLargeError)
    async def payload_too_large_handler(
        request: Request,
        exc: PayloadTooLargeError,
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(RateLimitError)
    async def rate_limit_error_handler(
        request: Request,
        exc: RateLimitError,
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        logger.warning("rate_limit_exceeded", request_id=request_id, path=str(request.url.path))
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(ProviderError)
    async def provider_error_handler(
        request: Request,
        exc: ProviderError,
    ) -> JSONResponse:
        """Handle all external provider errors."""
        request_id = _get_request_id(request)
        logger.error(
            "provider_error",
            request_id=request_id,
            code=exc.code,
            exc_info=exc,
        )
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            # Safe user-facing message; internal details stay in logs
            message="An external service is temporarily unavailable. Please try again.",
            request_id=request_id,
        )

    @app.exception_handler(AgentError)
    async def agent_error_handler(
        request: Request,
        exc: AgentError,
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        logger.error(
            "agent_error",
            request_id=request_id,
            code=exc.code,
            exc_info=exc,
        )
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message="The AI agent encountered an error processing your request.",
            request_id=request_id,
        )

    @app.exception_handler(WhatsAppAgentError)
    async def platform_error_handler(
        request: Request,
        exc: WhatsAppAgentError,
    ) -> JSONResponse:
        """Catch-all for any platform error not handled above."""
        request_id = _get_request_id(request)
        logger.error(
            "platform_error",
            request_id=request_id,
            code=exc.code,
            exc_info=exc,
        )
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """
        Last-resort handler for completely unexpected exceptions.
        Never expose internal details to the client.
        """
        request_id = _get_request_id(request)
        logger.exception(
            "unhandled_exception",
            request_id=request_id,
            path=str(request.url.path),
            exc_info=exc,
        )
        return _make_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred. Our team has been notified.",
            request_id=request_id,
        )
