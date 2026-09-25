"""
WhatsApp provider factory and dependency injection.

Provides a get_whatsapp_provider() FastAPI dependency that returns
the correct WhatsApp provider based on the WHATSAPP_PROVIDER setting.

Current providers:
- mock: MockWhatsAppProvider (DEVELOPMENT / MOCK IMPLEMENTATION)
- official: OfficialWhatsAppProvider (PLANNED — requires Meta Business verification)
"""

from __future__ import annotations

from functools import lru_cache

from whatsapp_agent.config.settings import WhatsAppProvider as WhatsAppProviderEnum
from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.core.exceptions import ConfigurationError
from whatsapp_agent.observability.logging import get_logger
from whatsapp_agent.whatsapp.providers.base import WhatsAppProvider
from whatsapp_agent.whatsapp.providers.mock import MockWhatsAppProvider

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_whatsapp_provider() -> WhatsAppProvider:
    """
    Create and cache the WhatsApp provider singleton.

    The provider is selected based on the WHATSAPP_PROVIDER environment variable.
    Cache is cleared on test teardown via get_settings.cache_clear().
    """
    settings = get_settings()
    provider_type = settings.whatsapp_provider

    if provider_type == WhatsAppProviderEnum.MOCK:
        logger.info(
            "whatsapp_provider_selected",
            provider="MockWhatsAppProvider",
            status="DEVELOPMENT / MOCK IMPLEMENTATION",
        )
        return MockWhatsAppProvider(app_secret=settings.whatsapp_app_secret or "mock-secret")

    elif provider_type == WhatsAppProviderEnum.OFFICIAL:
        # PLANNED: Phase 6 — Official WhatsApp Cloud API provider
        # Requires: WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_APP_SECRET
        logger.warning(
            "official_whatsapp_provider_not_yet_implemented",
            fallback="MockWhatsAppProvider",
        )
        # Temporary fallback until official provider is implemented
        return MockWhatsAppProvider(app_secret=settings.whatsapp_app_secret or "mock-secret")

    else:
        raise ConfigurationError(
            f"Unknown WhatsApp provider: {provider_type}. "
            f"Valid options: {[e.value for e in WhatsAppProviderEnum]}"
        )


def get_whatsapp_provider() -> WhatsAppProvider:
    """
    FastAPI dependency that returns the configured WhatsApp provider.

    Usage:
        @router.post("/send")
        async def send_message(
            provider: WhatsAppProvider = Depends(get_whatsapp_provider)
        ):
            await provider.send_text_message(...)
    """
    return _get_whatsapp_provider()
