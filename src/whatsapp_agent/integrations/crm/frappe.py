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
                
                # Fetch Leave Allocations for this employee to calculate balances
                leave_url = f"{self.base_url}/api/resource/Leave Allocation"
                leave_params = {
                    "filters": f'[["employee","=","{employee_id}"]]' ,
                    "fields": '["leave_type", "total_leaves_allocated", "leaves_taken", "expired_leaves"]'
                }
                leave_resp = await client.get(leave_url, headers=self._get_headers(), params=leave_params)
                leave_data = leave_resp.json().get("data", []) if leave_resp.status_code == 200 else []
                
                balances = []
                for l in leave_data:
                    allocated = float(l.get("total_leaves_allocated") or 0)
                    taken = float(l.get("leaves_taken") or 0)
                    expired = float(l.get("expired_leaves") or 0)
                    balance = allocated - taken - expired
                    balances.append({
                        "leave_type": l.get("leave_type"),
                        "balance": balance
                    })

                return {
                    "employee_id": data.get("name"),
                    "name": data.get("employee_name"),
                    "department": data.get("department"),
                    "designation": data.get("designation"),
                    "leave_balances": balances
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
        import random
        import redis.asyncio as redis
        from whatsapp_agent.whatsapp.providers.factory import get_whatsapp_provider
        
        settings = get_settings()
        otp = str(random.randint(100000, 999999))
        
        try:
            # Store OTP in Redis with 5-minute expiry (300 seconds)
            redis_client = redis.from_url(str(settings.redis_url))
            await redis_client.setex(f"otp:{phone}", 300, otp)
            await redis_client.aclose()
            
            # Send the OTP via WhatsApp
            wa_provider = get_whatsapp_provider()
            message = f"🔒 *ERP Security Alert*\n\nYour secure login OTP is: *{otp}*\n\nThis code is valid for 5 minutes. Do not share it with anyone."
            await wa_provider.send_text_message(phone, message)
            
            logger.info("frappe_send_whatsapp_otp_success", phone=phone)
            return True
        except Exception as e:
            logger.error("frappe_send_whatsapp_otp_failed", error=str(e))
            return False

    async def verify_whatsapp_otp(self, phone: str, otp: str) -> bool:
        import redis.asyncio as redis
        settings = get_settings()
        
        try:
            redis_client = redis.from_url(str(settings.redis_url))
            stored_otp = await redis_client.get(f"otp:{phone}")
            
            if stored_otp and stored_otp.decode("utf-8") == otp:
                # OTP is valid, delete it immediately to prevent reuse
                await redis_client.delete(f"otp:{phone}")
                await redis_client.aclose()
                logger.info("frappe_verify_whatsapp_otp_success", phone=phone)
                return True
                
            await redis_client.aclose()
            logger.warning("frappe_verify_whatsapp_otp_failed", phone=phone, reason="invalid_or_expired")
            return False
        except Exception as e:
            logger.error("frappe_verify_whatsapp_otp_error", error=str(e))
            return False

    async def apply_for_leave(self, employee_id: str, leave_type: str, from_date: str, to_date: str, reason: str) -> bool:
        """Create a Leave Application in ERPNext."""
        if not self.base_url: return False
        url = f"{self.base_url}/api/resource/Leave Application"
        payload = {
            "employee": employee_id,
            "leave_type": leave_type,
            "from_date": from_date,
            "to_date": to_date,
            "description": reason,
            "status": "Open"
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                logger.info("frappe_leave_applied", employee_id=employee_id)
                return True
        except Exception as e:
            logger.error("frappe_leave_apply_failed", error=str(e))
            return False

    async def create_expense_claim(self, employee_id: str, expense_type: str, amount: float, reason: str) -> bool:
        """Create an Expense Claim in ERPNext."""
        if not self.base_url: return False
        url = f"{self.base_url}/api/resource/Expense Claim"
        payload = {
            "employee": employee_id,
            "expenses": [{
                "expense_type": expense_type,
                "amount": amount,
                "description": reason
            }]
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                logger.info("frappe_expense_created", employee_id=employee_id)
                return True
        except Exception as e:
            logger.error("frappe_expense_create_failed", error=str(e))
            return False

    async def create_support_ticket(self, raised_by: str, subject: str, description: str) -> bool:
        """Create an Issue/Support Ticket in ERPNext."""
        if not self.base_url: return False
        url = f"{self.base_url}/api/resource/Issue"
        payload = {
            "raised_by": raised_by,
            "subject": subject,
            "description": description,
            "status": "Open"
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                logger.info("frappe_issue_created", raised_by=raised_by)
                return True
        except Exception as e:
            logger.error("frappe_issue_create_failed", error=str(e))
            return False
