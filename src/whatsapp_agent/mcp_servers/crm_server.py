from typing import Any
from mcp.server.mcpserver import MCPServer
from whatsapp_agent.integrations.crm.factory import get_crm_provider
import asyncio

mcp = MCPServer("CRM_Server")

@mcp.tool()
async def get_customer_record(phone: str) -> dict[str, Any] | None:
    """Look up the customer's profile, tier, and recent order history using their phone number."""
    crm = get_crm_provider()
    return await crm.get_customer_record(phone)

@mcp.tool()
async def create_ticket(phone: str, issue_description: str) -> str | None:
    """Create a new support ticket for the customer's issue."""
    crm = get_crm_provider()
    return await crm.create_ticket(phone, issue_description)

@mcp.tool()
async def get_ticket_status(ticket_id: str) -> str | None:
    """Check the status of an existing support ticket."""
    crm = get_crm_provider()
    return await crm.get_ticket_status(ticket_id)

@mcp.tool()
async def get_employee_details_with_otp(employee_id: str) -> dict[str, Any] | None:
    """Fetch employee details using Employee ID. Assumes OTP is verified prior."""
    crm = get_crm_provider()
    return await crm.get_employee_details(employee_id)

@mcp.tool()
async def get_invoice_details_with_otp(invoice_id: str, phone: str) -> dict[str, Any] | None:
    """Fetch invoice details using Invoice ID and phone. Assumes OTP is verified prior."""
    crm = get_crm_provider()
    return await crm.get_invoice_details(invoice_id, phone)

@mcp.tool()
async def request_whatsapp_otp(phone: str) -> bool:
    """Request an OTP to be sent to the given WhatsApp number."""
    crm = get_crm_provider()
    return await crm.send_whatsapp_otp(phone)

@mcp.tool()
async def verify_whatsapp_otp(phone: str, otp: str) -> bool:
    """Verify an OTP sent to the given WhatsApp number."""
    crm = get_crm_provider()
    return await crm.verify_whatsapp_otp(phone, otp)

if __name__ == "__main__":
    mcp.run(transport='stdio')
