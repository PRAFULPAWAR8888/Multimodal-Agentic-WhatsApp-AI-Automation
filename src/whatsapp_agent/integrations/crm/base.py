"""
CRM Provider Base Interface.

Defines the contract for interacting with CRM systems 
(HubSpot, Salesforce, Mock).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CRMProvider(ABC):
    """Abstract base class for all CRM providers."""

    @abstractmethod
    async def get_customer_record(self, phone: str) -> dict[str, Any] | None:
        """
        Retrieve a customer record by their phone number.
        
        Args:
            phone: The customer's WhatsApp ID/phone number.
            
        Returns:
            Dictionary containing customer details (name, email, ltv, etc.)
            or None if the customer doesn't exist.
        """
        pass

    @abstractmethod
    async def create_ticket(
        self, phone: str, issue_description: str, **kwargs: Any
    ) -> str | None:
        """
        Create a support ticket/case for the customer.
        
        Args:
            phone: Customer phone number.
            issue_description: Detailed description of the problem.
            
        Returns:
            The created ticket ID as a string, or None on failure.
        """
        pass

    @abstractmethod
    async def get_ticket_status(self, ticket_id: str) -> str | None:
        """
        Check the status of an existing ticket.
        
        Args:
            ticket_id: The ID of the ticket to check.
            
        Returns:
            The status of the ticket (e.g., 'Open', 'In Progress', 'Resolved')
            or None if the ticket doesn't exist.
        """
        pass

    @abstractmethod
    async def create_lead(self, phone: str, name: str | None, email: str | None, **kwargs: Any) -> str | None:
        """
        Create a new lead in the CRM.

        Args:
            phone: Customer phone number.
            name: Customer name.
            email: Customer email.

        Returns:
            The created lead ID, or None on failure.
        """
        pass

    @abstractmethod
    async def get_employee_details(self, employee_id: str) -> dict[str, Any] | None:
        """Fetch employee details from CRM/ERP."""
        pass

    @abstractmethod
    async def get_invoice_details(self, invoice_id: str, phone: str) -> dict[str, Any] | None:
        """Fetch invoice details from CRM/ERP."""
        pass

    @abstractmethod
    async def send_whatsapp_otp(self, phone: str) -> str | bool:
        """Send OTP to a WhatsApp number."""
        pass

    @abstractmethod
    async def verify_whatsapp_otp(self, phone: str, otp: str) -> bool:
        """Verify the OTP sent to a WhatsApp number."""
        pass

