"""
Calendar Provider Factory.
"""

from __future__ import annotations

from whatsapp_agent.config.settings import CalendarProvider as ProviderEnum, get_settings
from whatsapp_agent.integrations.calendar.base import CalendarProvider
from whatsapp_agent.integrations.calendar.mock import MockCalendarProvider
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

# Singleton instance
_provider_instance: CalendarProvider | None = None


def get_calendar_provider() -> CalendarProvider:
    """
    Get the configured calendar provider singleton.
    
    Returns:
        CalendarProvider implementation based on AppSettings.
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    settings = get_settings()

    if settings.calendar_provider == ProviderEnum.MOCK:
        logger.info("initializing_mock_calendar_provider")
        _provider_instance = MockCalendarProvider()
    else:
        logger.warning(
            "unsupported_calendar_provider_fallback_to_mock",
            provider=settings.calendar_provider,
        )
        _provider_instance = MockCalendarProvider()

    return _provider_instance
