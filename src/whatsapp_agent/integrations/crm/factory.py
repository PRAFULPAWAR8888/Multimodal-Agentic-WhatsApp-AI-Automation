"""
CRM Provider Factory.
"""

from __future__ import annotations

from whatsapp_agent.config.settings import CRMProvider as ProviderEnum, get_settings
from whatsapp_agent.integrations.crm.base import CRMProvider
from whatsapp_agent.integrations.crm.mock import MockCRMProvider
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

# Singleton instance
_provider_instance: CRMProvider | None = None


def get_crm_provider() -> CRMProvider:
    """
    Get the configured CRM provider singleton.
    
    Returns:
        CRMProvider implementation based on AppSettings.
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    settings = get_settings()

    if settings.crm_provider == ProviderEnum.MOCK:
        logger.info("initializing_mock_crm_provider")
        _provider_instance = MockCRMProvider()
    elif settings.crm_provider == ProviderEnum.FRAPPE:
        from whatsapp_agent.integrations.crm.frappe import FrappeCRMProvider
        logger.info("initializing_frappe_crm_provider")
        _provider_instance = FrappeCRMProvider()
    elif settings.crm_provider == ProviderEnum.HUBSPOT:
        from whatsapp_agent.integrations.crm.hubspot import HubSpotCRMProvider
        logger.info("initializing_hubspot_crm_provider")
        _provider_instance = HubSpotCRMProvider()
    else:
        logger.warning(
            "unsupported_crm_provider_fallback_to_mock",
            provider=settings.crm_provider,
        )
        _provider_instance = MockCRMProvider()

    return _provider_instance
