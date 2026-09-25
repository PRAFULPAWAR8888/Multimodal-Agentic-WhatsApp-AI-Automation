"""
Centralized application configuration using Pydantic Settings v2.

All configuration is loaded from environment variables (with .env file support).
Never hard-code secrets or credentials here.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AnyHttpUrl, Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(str, Enum):
    """Application deployment environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LLMProvider(str, Enum):
    """Supported LLM provider backends."""

    OPENAI = "openai"
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"


class EmbeddingProvider(str, Enum):
    """Supported embedding provider backends."""

    SENTENCE_TRANSFORMERS = "sentence_transformers"
    OPENAI = "openai"
    OLLAMA = "ollama"


class STTProvider(str, Enum):
    """Supported Speech-to-Text provider backends."""

    FASTER_WHISPER = "faster_whisper"
    OPENAI_WHISPER = "openai_whisper"


class TTSProvider(str, Enum):
    """Supported Text-to-Speech provider backends."""

    PIPER = "piper"
    OPENAI_TTS = "openai_tts"
    GTTS = "gtts"


class VisionProvider(str, Enum):
    """Supported Vision/VLM provider backends."""

    MOONDREAM = "moondream"
    OPENAI_VISION = "openai_vision"
    OLLAMA_LLAVA = "ollama_llava"


class WhatsAppProvider(str, Enum):
    """Supported WhatsApp integration backends."""

    OFFICIAL = "official"
    MOCK = "mock"


class CRMProvider(str, Enum):
    """Supported CRM provider backends."""

    HUBSPOT = "hubspot"
    FRAPPE = "frappe"
    MOCK = "mock"


class CalendarProvider(str, Enum):
    """Supported Calendar provider backends."""

    GOOGLE = "google"
    OUTLOOK = "outlook"
    MOCK = "mock"


class StorageProvider(str, Enum):
    """Supported file storage backends."""

    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"


class AppSettings(BaseSettings):
    """Core application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    app_name: str = Field(default="WhatsApp AI Platform")
    app_env: AppEnvironment = Field(default=AppEnvironment.DEVELOPMENT)
    debug: bool = Field(default=False)
    secret_key: str = Field(
        ...,
        description="Random 32+ character secret for JWT signing. NEVER commit this.",
    )
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="CORS allowed origins.",
    )
    api_v1_prefix: str = Field(default="/api/v1")
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: Any) -> list[str]:
        """Parse comma-separated origins string into list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── Database ────────────────────────────────────────────────────────────────
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL async connection URL (postgresql+asyncpg://...).",
    )
    database_pool_size: int = Field(default=10, ge=1, le=50)
    database_max_overflow: int = Field(default=20, ge=0, le=100)
    database_pool_pre_ping: bool = Field(default=True)
    database_echo: bool = Field(default=False, description="Log all SQL queries (dev only).")

    # ── Redis ───────────────────────────────────────────────────────────────────
    redis_url: RedisDsn = Field(
        ...,
        description="Redis connection URL.",
    )

    # ── LLM Provider ────────────────────────────────────────────────────────────
    llm_provider: LLMProvider = Field(default=LLMProvider.OPENAI)

    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API key.")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_max_tokens: int = Field(default=4096, ge=256)
    openai_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    openai_request_timeout: int = Field(default=60, ge=10)

    # ── LLM Governance / Token Budgets ──────────────────────────────────────────
    llm_max_input_words: int = Field(default=500)
    llm_max_input_tokens: int = Field(default=4000)

    llm_context_max_words: int = Field(default=1500)
    llm_context_max_tokens: int = Field(default=6000)

    llm_short_max_output_tokens: int = Field(default=80)
    llm_normal_max_output_tokens: int = Field(default=200)
    llm_detailed_max_output_tokens: int = Field(default=500)

    llm_max_tokens_per_request: int = Field(default=7000)
    llm_max_tokens_per_session: int = Field(default=30000)
    llm_max_tokens_per_day: int = Field(default=100000)

    llm_oversize_action: str = Field(default="reject", description="'reject', 'truncate', or 'summarize'")
    llm_context_overflow_action: str = Field(default="truncate", description="'truncate' or 'summarize'")

    llm_enable_input_limit: bool = Field(default=True)
    llm_enable_context_limit: bool = Field(default=True)
    llm_enable_output_limit: bool = Field(default=True)
    llm_enable_session_budget: bool = Field(default=True)
    llm_enable_cost_estimation: bool = Field(default=True)
    llm_enable_usage_logging: bool = Field(default=True)

    # Ollama (local fallback)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.2")

    # ── Embeddings ──────────────────────────────────────────────────────────────
    embedding_provider: EmbeddingProvider = Field(default=EmbeddingProvider.SENTENCE_TRANSFORMERS)
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    embedding_dimension: int = Field(default=384, description="Embedding vector dimension.")

    # ── Speech-to-Text ──────────────────────────────────────────────────────────
    stt_provider: STTProvider = Field(default=STTProvider.FASTER_WHISPER)
    faster_whisper_model: str = Field(default="base", description="Whisper model size.")
    faster_whisper_device: str = Field(default="cpu")
    faster_whisper_compute_type: str = Field(default="int8")
    faster_whisper_language: str | None = Field(
        default=None,
        description="Force language (None = auto-detect, supports multilingual incl. Hindi/Marathi).",
    )

    # ── Text-to-Speech ──────────────────────────────────────────────────────────
    tts_provider: TTSProvider = Field(default=TTSProvider.PIPER)
    piper_model_path: Path = Field(default=Path("./models/piper/en_US-lessac-medium.onnx"))
    openai_tts_voice: str = Field(default="nova")
    openai_tts_model: str = Field(default="tts-1")

    # ── Vision ──────────────────────────────────────────────────────────────────
    vision_provider: VisionProvider = Field(default=VisionProvider.MOONDREAM)
    moondream_model: str = Field(default="vikhyatk/moondream2")

    # ── WhatsApp ────────────────────────────────────────────────────────────────
    whatsapp_provider: WhatsAppProvider = Field(default=WhatsAppProvider.MOCK)
    whatsapp_access_token: str = Field(default="")
    whatsapp_phone_number_id: str = Field(default="")
    whatsapp_webhook_verify_token: str = Field(default="dev-verify-token")
    whatsapp_app_secret: str = Field(default="", description="Used for HMAC-SHA256 webhook verification.")
    whatsapp_business_account_id: str = Field(default="")
    whatsapp_api_version: str = Field(default="v21.0")

    @property
    def whatsapp_api_base_url(self) -> str:
        """WhatsApp Cloud API base URL."""
        return f"https://graph.facebook.com/{self.whatsapp_api_version}"

    # ── CRM ─────────────────────────────────────────────────────────────────────
    crm_provider: CRMProvider = Field(default=CRMProvider.MOCK)
    hubspot_client_id: str = Field(default="")
    hubspot_client_secret: str = Field(default="")
    hubspot_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/crm/hubspot/callback"
    )
    
    frappe_url: str = Field(default="")
    frappe_api_key: str = Field(default="")
    frappe_api_secret: str = Field(default="")

    # ── Calendar ────────────────────────────────────────────────────────────────
    calendar_provider: CalendarProvider = Field(default=CalendarProvider.MOCK)
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/calendar/google/callback"
    )

    # ── Storage ─────────────────────────────────────────────────────────────────
    storage_provider: StorageProvider = Field(default=StorageProvider.LOCAL)
    local_storage_path: Path = Field(default=Path("./media"))
    max_file_size_mb: int = Field(default=16, ge=1, le=100)

    allowed_image_types: list[str] = Field(
        default=["image/jpeg", "image/png", "image/webp"]
    )
    allowed_audio_types: list[str] = Field(
        default=["audio/ogg", "audio/mp3", "audio/mpeg", "audio/aac", "audio/amr"]
    )
    allowed_document_types: list[str] = Field(
        default=["application/pdf", "application/msword", "text/plain", "text/csv"]
    )

    @field_validator("allowed_image_types", "allowed_audio_types", "allowed_document_types", mode="before")
    @classmethod
    def parse_mime_list(cls, v: Any) -> list[str]:
        """Parse comma-separated MIME types into list."""
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        return v

    # ── Security / Auth ─────────────────────────────────────────────────────────
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=5)
    refresh_token_expire_days: int = Field(default=7, ge=1)
    rate_limit_requests: int = Field(default=100, description="Max requests per window.")
    rate_limit_window: int = Field(default=60, description="Rate limit window in seconds.")
    bcrypt_rounds: int = Field(default=12, ge=10, le=14)

    # ── Observability ───────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json", description="'json' or 'console'.")
    otel_exporter_otlp_endpoint: str = Field(default="http://localhost:4317")
    prometheus_port: int = Field(default=9090)

    # ── ARQ Worker ──────────────────────────────────────────────────────────────
    worker_max_jobs: int = Field(default=10)
    worker_job_timeout: int = Field(default=300, description="Job timeout in seconds.")
    worker_health_check_interval: int = Field(default=60)

    @model_validator(mode="after")
    def validate_provider_credentials(self) -> "AppSettings":
        """Warn if required credentials are missing for selected providers."""
        if self.llm_provider == LLMProvider.OPENAI and not self.openai_api_key:
            import warnings
            warnings.warn(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set. "
                "LLM calls will fail.",
                stacklevel=2,
            )
        if (
            self.whatsapp_provider == WhatsAppProvider.OFFICIAL
            and not self.whatsapp_access_token
        ):
            import warnings
            warnings.warn(
                "WHATSAPP_PROVIDER=official but WHATSAPP_ACCESS_TOKEN is not set.",
                stacklevel=2,
            )
        return self

    @property
    def is_development(self) -> bool:
        """True if running in development environment."""
        return self.app_env == AppEnvironment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """True if running in production environment."""
        return self.app_env == AppEnvironment.PRODUCTION

    @property
    def max_file_size_bytes(self) -> int:
        """Maximum allowed file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """
    Return the cached application settings singleton.

    Uses lru_cache to ensure settings are only loaded once per process.
    In tests, clear the cache with: get_settings.cache_clear()
    """
    return AppSettings()
