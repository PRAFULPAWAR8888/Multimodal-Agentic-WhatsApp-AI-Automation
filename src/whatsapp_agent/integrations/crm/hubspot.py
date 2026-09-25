"""
HubSpot CRM Provider.
"""

from __future__ import annotations

import asyncio
from typing import Any
import httpx

from whatsapp_agent.integrations.crm.base import CRMProvider
from whatsapp_agent.observability.logging import get_logger
from whatsapp_agent.config.settings import get_settings

logger = get_logger(__name__)

class HubSpotCRMProvider(CRMProvider):
    """HubSpot CRM Provider implementation."""

    def __init__(self) -> None:
        settings = get_settings()
        # Ensure your HubSpot Client ID/Secret or Access Token are stored in settings
        self.client_id = settings.hubspot_client_id
        self.client_secret = settings.hubspot_client_secret
        self.base_url = "https://api.hubapi.com"
        # In a real integration, you would handle OAuth or Private App access tokens.
        # For simplicity, we assume an access token is available.
        self.access_token = "YOUR_HUBSPOT_ACCESS_TOKEN_HERE"

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    async def get_customer_record(self, phone: str) -> dict[str, Any] | None:
        url = f"{self.base_url}/crm/v3/objects/contacts/search"
        payload = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "phone",
                    "operator": "EQ",
                    "value": phone
                }]
            }],
            "properties": ["firstname", "lastname", "email", "phone"]
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                data = response.json()
                if data.get("total", 0) > 0:
                    contact = data["results"][0]
                    props = contact.get("properties", {})
                    return {
                        "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                        "email": props.get("email"),
                        "phone": props.get("phone")
                    }
        except Exception as e:
            logger.error("hubspot_get_customer_failed", error=str(e))
        return None

    async def create_ticket(self, phone: str, issue_description: str, **kwargs: Any) -> str | None:
        url = f"{self.base_url}/crm/v3/objects/tickets"
        payload = {
            "properties": {
                "hs_pipeline": "0",
                "hs_pipeline_stage": "1",
                "subject": f"WhatsApp Issue from {phone}",
                "content": issue_description
            }
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                return response.json().get("id")
        except Exception as e:
            logger.error("hubspot_create_ticket_failed", error=str(e))
        return None

    async def get_ticket_status(self, ticket_id: str) -> str | None:
        url = f"{self.base_url}/crm/v3/objects/tickets/{ticket_id}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json().get("properties", {}).get("hs_pipeline_stage")
        except Exception as e:
            logger.error("hubspot_get_ticket_status_failed", error=str(e))
        return None

    async def create_lead(self, phone: str, name: str | None, email: str | None, **kwargs: Any) -> str | None:
        url = f"{self.base_url}/crm/v3/objects/contacts"
        parts = (name or "").split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""
        
        payload = {
            "properties": {
                "phone": phone,
                "firstname": first_name,
                "lastname": last_name,
                "email": email or ""
            }
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                return response.json().get("id")
        except Exception as e:
            logger.error("hubspot_create_lead_failed", error=str(e))
        return None

    async def get_employee_details(self, employee_id: str) -> dict[str, Any] | None:
        logger.warning("hubspot_get_employee_details_not_supported")
        return None

    async def get_invoice_details(self, invoice_id: str, phone: str) -> dict[str, Any] | None:
        logger.warning("hubspot_get_invoice_details_not_supported")
        return None

    async def send_whatsapp_otp(self, phone: str) -> str | bool:
        logger.info("hubspot_send_whatsapp_otp_mock", phone=phone)
        return True

    async def verify_whatsapp_otp(self, phone: str, otp: str) -> bool:
        logger.info("hubspot_verify_whatsapp_otp_mock", phone=phone, otp=otp)
        return otp == "123456"
