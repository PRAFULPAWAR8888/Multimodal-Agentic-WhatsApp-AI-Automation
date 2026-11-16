"""
Mock CRM Provider for testing and development.
"""

from __future__ import annotations

import asyncio
from typing import Any

from whatsapp_agent.integrations.crm.base import CRMProvider
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)


class MockCRMProvider(CRMProvider):
    """A mock implementation of CRMProvider."""

    def __init__(self) -> None:
        self._customers = {
            # A dummy customer for testing
            "1234567890": {
                "name": "Alice Smith",
                "email": "alice@example.com",
                "tier": "Premium",
                "ltv": "$1,250",
                "recent_order": "ORD-9982"
            }
        }
        
        self._tickets = {
            "TKT-100": {"status": "Resolved", "issue": "Late delivery"},
            "TKT-101": {"status": "In Progress", "issue": "Broken item"},
        }
        
        self._next_ticket_id = 102

    async def get_customer_record(self, phone: str) -> dict[str, Any] | None:
        """Mock retrieving a customer record."""
        logger.info("mock_crm_get_customer", phone=phone)
        await asyncio.sleep(0.5)
        
        # In a real system, we'd look up by the exact phone string.
        # For the mock, if we don't have it, we just return a generic profile
        # to ensure the demo works smoothly regardless of the test phone number.
        if phone not in self._customers:
            return {
                "name": "Valued Customer",
                "tier": "Standard",
                "notes": "No recent orders found."
            }
            
        return self._customers.get(phone)

    async def create_ticket(
        self, phone: str, issue_description: str, **kwargs: Any
    ) -> str | None:
        """Mock creating a ticket."""
        logger.info("mock_crm_create_ticket", phone=phone, issue=issue_description[:50])
        await asyncio.sleep(1.0)
        
        ticket_id = f"TKT-{self._next_ticket_id}"
        self._next_ticket_id += 1
        
        self._tickets[ticket_id] = {
            "status": "Open",
            "issue": issue_description,
            "phone": phone
        }
        
        return ticket_id

    async def get_ticket_status(self, ticket_id: str) -> str | None:
        """Mock retrieving ticket status."""
        logger.info("mock_crm_get_ticket_status", ticket_id=ticket_id)
        await asyncio.sleep(0.5)
        
        ticket = self._tickets.get(ticket_id.upper())
        if not ticket:
            return None
            
        return ticket.get("status")

    async def create_lead(self, phone: str, name: str | None, email: str | None, **kwargs: Any) -> str | None:
        """Mock creating a lead."""
        logger.info("mock_crm_create_lead", phone=phone, name=name)
        await asyncio.sleep(0.05)
        
        lead_id = f"LEAD-{phone}"
        client_name = name or kwargs.get("client_name") or "Unknown"
        reason = (
            kwargs.get("reasons_to_reach_us") 
            or kwargs.get("reason_to_reach_us") 
            or kwargs.get("reason") 
            or kwargs.get("requirement") 
            or ""
        )
        self._customers[phone] = {
            "lead_id": lead_id,
            "name": client_name,
            "client_name": client_name,
            "email": email or "unknown@example.com",
            "phone": phone,
            "mobile_no": phone,
            "reasons_to_reach_us": reason,
            "requirement": reason,
            "tier": "New Lead",
            "status": kwargs.get("status", "New"),
            "lead_score": kwargs.get("lead_score", 0),
            "company": kwargs.get("company", ""),
            "ltv": "$0",
            "notes": kwargs.get("notes", "Imported from WhatsApp")
        }
        
        return lead_id

    async def update_lead(self, lead_id: str | None = None, **kwargs: Any) -> bool:
        """Mock updating an existing lead with Client Name, Email, Phone, and Reasons to Reach us."""
        logger.info("mock_crm_update_lead", lead_id=lead_id, kwargs=kwargs)
        await asyncio.sleep(0.05)

        target_phone = None
        phone_val = kwargs.get("phone") or kwargs.get("mobile_no")

        if lead_id:
            for phone, record in self._customers.items():
                if record.get("lead_id") == lead_id or f"LEAD-{phone}" == lead_id:
                    target_phone = phone
                    break
        elif phone_val and phone_val in self._customers:
            target_phone = phone_val
        elif phone_val:
            # If lead doesn't exist yet, create mock record
            self._customers[phone_val] = {"lead_id": f"LEAD-{phone_val}", "phone": phone_val}
            target_phone = phone_val

        if target_phone:
            record = self._customers[target_phone]

            # 1. Client Name
            client_name = kwargs.get("client_name") or kwargs.get("name")
            if client_name:
                record["name"] = client_name
                record["client_name"] = client_name

            # 2. Email
            if "email" in kwargs and kwargs["email"]:
                record["email"] = kwargs["email"]

            # 3. Phone
            phone_val = kwargs.get("phone") or kwargs.get("mobile_no")
            if phone_val:
                record["phone"] = phone_val
                record["mobile_no"] = phone_val

            # 4. Reasons to Reach us
            reason_val = (
                kwargs.get("reasons_to_reach_us") 
                or kwargs.get("reason_to_reach_us") 
                or kwargs.get("reason") 
                or kwargs.get("requirement") 
                or kwargs.get("notes")
            )
            if reason_val:
                record["reasons_to_reach_us"] = reason_val
                record["requirement"] = reason_val

            if "status" in kwargs and kwargs["status"]:
                record["status"] = kwargs["status"]
            if "lead_score" in kwargs and kwargs["lead_score"] is not None:
                record["lead_score"] = kwargs["lead_score"]

            for k, v in kwargs.items():
                if v is not None:
                    record[k] = v

            logger.info("mock_crm_lead_updated", lead_id=lead_id, updated_record=record)
            return True

        logger.warning("mock_crm_lead_not_found_for_update", lead_id=lead_id)
        return False

    async def get_lead(self, lead_id: str) -> dict[str, Any] | None:
        """Mock getting lead details."""
        logger.info("mock_crm_get_lead", lead_id=lead_id)
        await asyncio.sleep(0.05)
        for phone, record in self._customers.items():
            if record.get("lead_id") == lead_id or f"LEAD-{phone}" == lead_id:
                return {**record, "id": lead_id, "phone": record.get("phone", phone)}
        return None

    async def get_employee_details(self, employee_id: str) -> dict[str, Any] | None:
        logger.info("mock_get_employee_details", employee_id=employee_id)
        if employee_id == "EMP001":
            return {"employee_id": "EMP001", "name": "John Doe", "department": "Engineering"}
        return None

    async def get_invoice_details(self, invoice_id: str, phone: str) -> dict[str, Any] | None:
        logger.info("mock_get_invoice_details", invoice_id=invoice_id, phone=phone)
        if invoice_id == "INV001":
            return {"invoice_id": "INV001", "status": "Paid", "amount": 1500}
        return None

    async def send_whatsapp_otp(self, phone: str) -> str | bool:
        logger.info("mock_send_whatsapp_otp", phone=phone)
        # Store mock OTP logic somewhere if needed
        return True

    async def verify_whatsapp_otp(self, phone: str, otp: str) -> bool:
        logger.info("mock_verify_whatsapp_otp", phone=phone, otp=otp)
        return otp == "123456"
