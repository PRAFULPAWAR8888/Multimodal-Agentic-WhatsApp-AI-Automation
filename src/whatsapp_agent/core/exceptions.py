"""Custom exception hierarchy for the WhatsApp AI Platform.

All exceptions inherit from WhatsAppAgentError to allow catch-all handling.
Domain-specific exceptions are organized by subsystem.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any


class WhatsAppAgentError(Exception):
    """Base exception for all platform errors.

    Attributes:
        message: Human-readable error description.
        code: Machine-readable error code for API clients.
        status_code: HTTP status code for API responses.
        details: Optional additional context (never include sensitive data).
    """

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code or self.__class__.code
        self.details = details or {}
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


# ── Authentication & Authorization ─────────────────────────────────────────────

class AuthenticationError(WhatsAppAgentError):
    """Raised when authentication fails (invalid credentials, expired token)."""

    status_code = HTTPStatus.UNAUTHORIZED
    code = "AUTHENTICATION_FAILED"


class AuthorizationError(WhatsAppAgentError):
    """Raised when an authenticated user lacks permission for an action."""

    status_code = HTTPStatus.FORBIDDEN
    code = "AUTHORIZATION_FAILED"


class TokenExpiredError(AuthenticationError):
    """Raised when a JWT token has expired."""

    code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    """Raised when a JWT token is malformed or invalid."""

    code = "INVALID_TOKEN"


# ── Validation ─────────────────────────────────────────────────────────────────

class ValidationError(WhatsAppAgentError):
    """Raised when input validation fails."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"


class MediaValidationError(ValidationError):
    """Raised when an uploaded media file fails validation."""

    code = "MEDIA_VALIDATION_ERROR"


class PayloadTooLargeError(ValidationError):
    """Raised when an uploaded file exceeds the size limit."""

    status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    code = "PAYLOAD_TOO_LARGE"


# ── Resource Errors ────────────────────────────────────────────────────────────

class NotFoundError(WhatsAppAgentError):
    """Raised when a requested resource does not exist."""

    status_code = HTTPStatus.NOT_FOUND
    code = "NOT_FOUND"


class ConflictError(WhatsAppAgentError):
    """Raised when an operation conflicts with current state (e.g., duplicate)."""

    status_code = HTTPStatus.CONFLICT
    code = "CONFLICT"


# ── Provider Errors ────────────────────────────────────────────────────────────

class ProviderError(WhatsAppAgentError):
    """Base class for external provider errors."""

    status_code = HTTPStatus.BAD_GATEWAY
    code = "PROVIDER_ERROR"


class LLMError(ProviderError):
    """Raised when the LLM provider call fails."""

    code = "LLM_ERROR"


class LLMRateLimitError(LLMError):
    """Raised when the LLM provider enforces rate limits."""

    status_code = HTTPStatus.TOO_MANY_REQUESTS
    code = "LLM_RATE_LIMIT"


class LLMContextLengthError(LLMError):
    """Raised when the prompt exceeds the model's context window."""

    code = "LLM_CONTEXT_TOO_LONG"


class EmbeddingError(ProviderError):
    """Raised when embedding generation fails."""

    code = "EMBEDDING_ERROR"


class STTError(ProviderError):
    """Raised when speech-to-text transcription fails."""

    code = "STT_ERROR"


class TTSError(ProviderError):
    """Raised when text-to-speech synthesis fails."""

    code = "TTS_ERROR"


class VisionError(ProviderError):
    """Raised when image/vision processing fails."""

    code = "VISION_ERROR"


class WhatsAppProviderError(ProviderError):
    """Raised when WhatsApp Cloud API calls fail."""

    code = "WHATSAPP_PROVIDER_ERROR"


class WhatsAppWebhookError(WhatsAppProviderError):
    """Raised when WhatsApp webhook processing fails."""

    code = "WHATSAPP_WEBHOOK_ERROR"


class WebhookSignatureError(WhatsAppWebhookError):
    """Raised when webhook HMAC-SHA256 signature verification fails."""

    status_code = HTTPStatus.UNAUTHORIZED
    code = "WEBHOOK_SIGNATURE_INVALID"


class CRMProviderError(ProviderError):
    """Raised when CRM provider calls fail."""

    code = "CRM_PROVIDER_ERROR"


class CalendarProviderError(ProviderError):
    """Raised when Calendar provider calls fail."""

    code = "CALENDAR_PROVIDER_ERROR"


# ── Agent & Workflow Errors ────────────────────────────────────────────────────

class AgentError(WhatsAppAgentError):
    """Base class for agent execution errors."""

    code = "AGENT_ERROR"


class SupervisorError(AgentError):
    """Raised when the supervisor agent fails to route or orchestrate."""

    code = "SUPERVISOR_ERROR"


class WorkflowError(AgentError):
    """Raised when a LangGraph workflow fails."""

    code = "WORKFLOW_ERROR"


class EscalationRequiredError(AgentError):
    """Raised when the agent determines human escalation is required."""

    status_code = HTTPStatus.ACCEPTED  # Not a true error; signals workflow transition
    code = "ESCALATION_REQUIRED"


# ── RAG Errors ────────────────────────────────────────────────────────────────

class RetrievalError(WhatsAppAgentError):
    """Raised when vector store retrieval fails."""

    code = "RETRIEVAL_ERROR"


class DocumentProcessingError(WhatsAppAgentError):
    """Raised when document ingestion or extraction fails."""

    code = "DOCUMENT_PROCESSING_ERROR"


class KnowledgeSourceError(WhatsAppAgentError):
    """Raised when a knowledge source operation fails."""

    code = "KNOWLEDGE_SOURCE_ERROR"


# ── Tool Errors ────────────────────────────────────────────────────────────────

class ToolExecutionError(WhatsAppAgentError):
    """Raised when a tool fails during execution."""

    code = "TOOL_EXECUTION_ERROR"


class ToolNotFoundError(ToolExecutionError):
    """Raised when a requested tool is not registered."""

    status_code = HTTPStatus.NOT_FOUND
    code = "TOOL_NOT_FOUND"


class ToolPermissionError(ToolExecutionError):
    """Raised when an agent lacks permission to execute a tool."""

    status_code = HTTPStatus.FORBIDDEN
    code = "TOOL_PERMISSION_DENIED"


class ToolRiskLevelError(ToolExecutionError):
    """Raised when a high-risk tool requires human approval before execution."""

    status_code = HTTPStatus.ACCEPTED
    code = "TOOL_REQUIRES_APPROVAL"


class ToolSchemaValidationError(ToolExecutionError):
    """Raised when tool input/output fails schema validation."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "TOOL_SCHEMA_INVALID"


# ── Media Errors ───────────────────────────────────────────────────────────────

class MediaProcessingError(WhatsAppAgentError):
    """Raised when media file processing fails."""

    code = "MEDIA_PROCESSING_ERROR"


class UnsupportedMediaTypeError(MediaProcessingError):
    """Raised when a media file type is not supported."""

    status_code = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    code = "UNSUPPORTED_MEDIA_TYPE"


# ── Configuration & Integration Errors ────────────────────────────────────────

class ConfigurationError(WhatsAppAgentError):
    """Raised when required configuration is missing or invalid."""

    code = "CONFIGURATION_ERROR"


class IntegrationError(WhatsAppAgentError):
    """Raised when an external service integration fails."""

    code = "INTEGRATION_ERROR"


# ── Rate Limiting ──────────────────────────────────────────────────────────────

class RateLimitError(WhatsAppAgentError):
    """Raised when a client exceeds the allowed request rate."""

    status_code = HTTPStatus.TOO_MANY_REQUESTS
    code = "RATE_LIMIT_EXCEEDED"


# ── Multi-tenancy ──────────────────────────────────────────────────────────────

class WorkspaceIsolationError(WhatsAppAgentError):
    """
    Raised when a cross-workspace data access attempt is detected.
    This is a critical security error and should always be audited.
    """

    status_code = HTTPStatus.FORBIDDEN
    code = "WORKSPACE_ISOLATION_VIOLATION"
