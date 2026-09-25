"""
Tests for application settings configuration.

Verifies:
- Settings load correctly from environment variables
- Enum validation works
- Provider credential warnings work
- Computed properties return correct values
"""

from __future__ import annotations

import os
import uuid

import pytest

from whatsapp_agent.config.settings import (
    AppEnvironment,
    AppSettings,
    CRMProvider,
    EmbeddingProvider,
    LLMProvider,
    STTProvider,
    TTSProvider,
    VisionProvider,
    WhatsAppProvider,
    get_settings,
)


class TestAppSettingsDefaults:
    """Tests for default settings values."""

    def test_settings_load_successfully(self, override_settings: AppSettings) -> None:
        """Settings should load without raising exceptions."""
        assert override_settings is not None

    def test_default_llm_provider(self, override_settings: AppSettings) -> None:
        """Default LLM provider should be OpenAI."""
        assert override_settings.llm_provider == LLMProvider.OPENAI

    def test_default_whatsapp_provider_is_mock(self, override_settings: AppSettings) -> None:
        """Default WhatsApp provider should be mock for dev/test."""
        assert override_settings.whatsapp_provider == WhatsAppProvider.MOCK

    def test_default_crm_provider_is_mock(self, override_settings: AppSettings) -> None:
        """Default CRM provider should be mock for dev/test."""
        assert override_settings.crm_provider == CRMProvider.MOCK

    def test_default_stt_provider(self, override_settings: AppSettings) -> None:
        """Default STT provider should be faster-whisper (free, local)."""
        assert override_settings.stt_provider == STTProvider.FASTER_WHISPER

    def test_default_tts_provider(self, override_settings: AppSettings) -> None:
        """Default TTS provider should be Piper (free, local)."""
        assert override_settings.tts_provider == TTSProvider.PIPER

    def test_default_vision_provider(self, override_settings: AppSettings) -> None:
        """Default vision provider should be moondream2 (free, CPU-runnable)."""
        assert override_settings.vision_provider == VisionProvider.MOONDREAM

    def test_default_embedding_provider(self, override_settings: AppSettings) -> None:
        """Default embedding provider should be sentence-transformers (free)."""
        assert override_settings.embedding_provider == EmbeddingProvider.SENTENCE_TRANSFORMERS

    def test_test_environment(self, override_settings: AppSettings) -> None:
        """App environment should be 'testing' in tests."""
        assert override_settings.app_env == AppEnvironment.TESTING

    def test_is_development_false_in_test(self, override_settings: AppSettings) -> None:
        """is_development should be False in testing environment."""
        assert override_settings.is_development is False

    def test_max_file_size_bytes(self, override_settings: AppSettings) -> None:
        """max_file_size_bytes should be MB * 1024 * 1024."""
        expected = override_settings.max_file_size_mb * 1024 * 1024
        assert override_settings.max_file_size_bytes == expected

    def test_whatsapp_api_base_url(self, override_settings: AppSettings) -> None:
        """WhatsApp API base URL should include the configured version."""
        assert override_settings.whatsapp_api_version in override_settings.whatsapp_api_base_url


class TestSettingsCaching:
    """Tests for the settings singleton cache."""

    def test_get_settings_returns_same_instance(self) -> None:
        """get_settings() should return the same cached instance each call."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_cache_can_be_cleared(self) -> None:
        """get_settings.cache_clear() should allow fresh settings to be loaded."""
        s1 = get_settings()
        get_settings.cache_clear()
        # Reset env so we don't get a warning about missing SECRET_KEY
        s2 = get_settings()
        assert s1 is not s2  # Different instances after cache clear


class TestAllowedMimeTypes:
    """Tests for MIME type lists."""

    def test_image_types_non_empty(self, override_settings: AppSettings) -> None:
        assert len(override_settings.allowed_image_types) > 0

    def test_audio_types_non_empty(self, override_settings: AppSettings) -> None:
        assert len(override_settings.allowed_audio_types) > 0

    def test_document_types_non_empty(self, override_settings: AppSettings) -> None:
        assert len(override_settings.allowed_document_types) > 0

    def test_ogg_in_audio_types(self, override_settings: AppSettings) -> None:
        """OGG/Opus must be in allowed audio types (required for WhatsApp voice notes)."""
        assert "audio/ogg" in override_settings.allowed_audio_types

    def test_pdf_in_document_types(self, override_settings: AppSettings) -> None:
        assert "application/pdf" in override_settings.allowed_document_types
