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
        await asyncio.sleep(0.5)
        
        self._customers[phone] = {
            "name": name or "Unknown",
            "email": email or "unknown@example.com",
            "tier": "New Lead",
            "ltv": "$0",
            "notes": "Imported from WhatsApp"
        }
        
        return f"LEAD-{phone}"

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
