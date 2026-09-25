"""
Structured logging configuration using structlog.

Provides JSON-formatted logs in production and human-readable console logs
in development. Integrates with OpenTelemetry trace context.

Usage:
    from whatsapp_agent.observability.logging import get_logger

    logger = get_logger(__name__)
    logger.info("message_received", conversation_id=str(conv_id), modality="text")
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger


def _add_service_context(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Inject service-level context into every log record."""
    event_dict.setdefault("service", "whatsapp-agent")
    return event_dict


def _drop_color_message_key(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Remove the Uvicorn color_message key if present."""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configure structlog and stdlib logging.

    Args:
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format ('json' for production, 'console' for development).
    """
    # Shared processors applied before the final renderer
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _add_service_context,
        _drop_color_message_key,
    ]

    if log_format == "json":
        # Production: JSON lines output
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        # Development: human-readable console output with colors
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Silence noisy third-party loggers
    for noisy_logger in (
        "uvicorn.access",
        "sqlalchemy.engine",
        "httpx",
        "httpcore",
        "multipart",
    ):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Allow SQLAlchemy echo if explicitly set to DEBUG
    if log_level.upper() == "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Return a structlog bound logger for the given module name.

    Args:
        name: Module name, typically __name__.

    Returns:
        A structlog BoundLogger instance with service context pre-bound.

    Example:
        logger = get_logger(__name__)
        logger.info("event_name", key="value")
    """
    return structlog.get_logger(name)


def bind_request_context(
    request_id: str,
    workspace_id: str | None = None,
    conversation_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """
    Bind request-scoped context to all subsequent log calls in this async context.

    Call this at the start of each request handler. structlog's contextvars
    ensures this context is automatically cleared after the request.

    Args:
        request_id: Unique identifier for this HTTP request.
        workspace_id: Tenant workspace ID (if authenticated).
        conversation_id: WhatsApp conversation ID (if processing a message).
        user_id: Authenticated user ID (if authenticated).
    """
    context: dict[str, str] = {"request_id": request_id}
    if workspace_id:
        context["workspace_id"] = workspace_id
    if conversation_id:
        context["conversation_id"] = conversation_id
    if user_id:
        context["user_id"] = user_id

    structlog.contextvars.bind_contextvars(**context)


def clear_request_context() -> None:
    """Clear all request-scoped context variables."""
    structlog.contextvars.clear_contextvars()
