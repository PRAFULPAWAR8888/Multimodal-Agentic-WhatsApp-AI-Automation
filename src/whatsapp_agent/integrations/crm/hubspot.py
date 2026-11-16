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

    async def update_lead(self, lead_id: str, **kwargs: Any) -> bool:
        """Update an existing HubSpot contact/lead."""
        if not lead_id:
            return False
        url = f"{self.base_url}/crm/v3/objects/contacts/{lead_id}"
        properties: dict[str, Any] = {}

        # 1. Client Name
        client_name = kwargs.get("client_name") or kwargs.get("name")
        if client_name:
            parts = str(client_name).strip().split(" ", 1)
            properties["firstname"] = parts[0]
            if len(parts) > 1:
                properties["lastname"] = parts[1]
        if "first_name" in kwargs and kwargs["first_name"]:
            properties["firstname"] = kwargs["first_name"]
        if "last_name" in kwargs and kwargs["last_name"]:
            properties["lastname"] = kwargs["last_name"]

        # 2. Email
        if "email" in kwargs and kwargs["email"]:
            properties["email"] = kwargs["email"]

        # 3. Phone
        phone_val = kwargs.get("phone") or kwargs.get("mobile_no")
        if phone_val:
            properties["phone"] = phone_val

        if "company" in kwargs and kwargs["company"]:
            properties["company"] = kwargs["company"]

        # 4. Address
        address_val = kwargs.get("address") or kwargs.get("location")
        if address_val:
            properties["address"] = str(address_val)

        # 5. Reasons to Reach Us
        reason_val = (
            kwargs.get("reasons_to_reach_us") 
            or kwargs.get("reason_to_reach_us") 
            or kwargs.get("reason") 
            or kwargs.get("requirement") 
            or kwargs.get("notes")
        )
        if reason_val:
            properties["message"] = str(reason_val)

        ignored = (
            "name", "client_name", "company", "phone", "first_name", 
            "last_name", "mobile_no", "reasons_to_reach_us", "reason_to_reach_us", 
            "reason", "requirement", "notes", "address", "location"
        )
        for k, v in kwargs.items():
            if k not in properties and k not in ignored:
                properties[k] = v

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(url, headers=self._get_headers(), json={"properties": properties})
                response.raise_for_status()
                logger.info("hubspot_update_lead_success", lead_id=lead_id)
                return True
        except Exception as e:
            logger.error("hubspot_update_lead_failed", lead_id=lead_id, error=str(e))
            return False

    async def get_lead(self, lead_id: str) -> dict[str, Any] | None:
        """Retrieve HubSpot contact/lead."""
        if not lead_id:
            return None
        url = f"{self.base_url}/crm/v3/objects/contacts/{lead_id}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                props = data.get("properties", {})
                first = props.get("firstname", "")
                last = props.get("lastname", "")
                data["client_name"] = f"{first} {last}".strip()
                data["name"] = data["client_name"]
                data["email"] = props.get("email")
                data["phone"] = props.get("phone")
                data["reasons_to_reach_us"] = props.get("message")
                data["requirement"] = props.get("message")
                return data
        except Exception as e:
            logger.error("hubspot_get_lead_failed", lead_id=lead_id, error=str(e))
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
