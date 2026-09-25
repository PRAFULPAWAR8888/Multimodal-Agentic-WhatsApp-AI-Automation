"""
Frappe/ERPNext CRM Provider.
"""

from __future__ import annotations

import asyncio
from typing import Any
import httpx

from whatsapp_agent.integrations.crm.base import CRMProvider
from whatsapp_agent.observability.logging import get_logger
from whatsapp_agent.config.settings import get_settings

logger = get_logger(__name__)

class FrappeCRMProvider(CRMProvider):
    """Frappe/ERPNext CRM Provider implementation."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.frappe_url.rstrip("/") if settings.frappe_url else ""
        self.api_key = settings.frappe_api_key
        self.api_secret = settings.frappe_api_secret

    def _get_headers(self) -> dict[str, str]:
        if not self.api_key or not self.api_secret:
            logger.warning("frappe_credentials_missing")
            return {}
        return {
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Accept": "application/json"
        }

    async def get_customer_record(self, phone: str) -> dict[str, Any] | None:
        """Fetch customer record from Frappe."""
        if not self.base_url:
            return None
        
        url = f"{self.base_url}/api/resource/Customer"
        params = {
            "filters": f'[["mobile_no","=","{phone}"]]',
            "fields": '["name","customer_name","email_id","customer_group"]'
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self._get_headers(), params=params)
                response.raise_for_status()
                data = response.json()
                if data.get("data") and len(data["data"]) > 0:
                    return data["data"][0]
        except Exception as e:
            logger.error("frappe_get_customer_failed", error=str(e))
        return None

    async def create_ticket(self, phone: str, issue_description: str, **kwargs: Any) -> str | None:
        """Create an Issue in Frappe/ERPNext."""
        if not self.base_url:
            return None
            
        url = f"{self.base_url}/api/resource/Issue"
        payload = {
            "subject": f"WhatsApp Issue from {phone}",
            "description": issue_description,
            "raised_by": phone
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                return response.json().get("data", {}).get("name")
        except Exception as e:
            logger.error("frappe_create_ticket_failed", error=str(e))
        return None

    async def get_ticket_status(self, ticket_id: str) -> str | None:
        if not self.base_url:
            return None
            
        url = f"{self.base_url}/api/resource/Issue/{ticket_id}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json().get("data", {}).get("status")
        except Exception as e:
            logger.error("frappe_get_ticket_status_failed", error=str(e))
        return None

    async def create_lead(self, phone: str, name: str | None, email: str | None, **kwargs: Any) -> str | None:
        if not self.base_url:
            return None
            
        url = f"{self.base_url}/api/resource/Lead"
        payload = {
            "first_name": name or "Unknown",
            "mobile_no": phone,
            "email_id": email or ""
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                return response.json().get("data", {}).get("name")
        except Exception as e:
            logger.error("frappe_create_lead_failed", error=str(e))
        return None

    async def get_employee_details(self, employee_id: str) -> dict[str, Any] | None:
        if not self.base_url:
            return None
            
        url = f"{self.base_url}/api/resource/Employee/{employee_id}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                data = response.json().get("data", {})
                return {
                    "employee_id": data.get("name"),
                    "name": data.get("employee_name"),
                    "department": data.get("department"),
                    "designation": data.get("designation")
                }
        except Exception as e:
            logger.error("frappe_get_employee_failed", error=str(e))
        return None

    async def get_invoice_details(self, invoice_id: str, phone: str) -> dict[str, Any] | None:
        if not self.base_url:
            return None
            
        url = f"{self.base_url}/api/resource/Sales Invoice/{invoice_id}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                data = response.json().get("data", {})
                # Basic check to ensure phone matches Customer's phone could be added here
                return {
                    "invoice_id": data.get("name"),
                    "status": data.get("status"),
                    "amount": data.get("grand_total"),
                    "customer": data.get("customer_name")
                }
        except Exception as e:
            logger.error("frappe_get_invoice_failed", error=str(e))
        return None

    async def send_whatsapp_otp(self, phone: str) -> str | bool:
        # Placeholder for actual OTP send logic, e.g., calling an external OTP service or Frappe method
        logger.info("frappe_send_whatsapp_otp", phone=phone)
        return True

    async def verify_whatsapp_otp(self, phone: str, otp: str) -> bool:
        # Placeholder for OTP validation
        logger.info("frappe_verify_whatsapp_otp", phone=phone, otp=otp)
        return otp == "123456"
