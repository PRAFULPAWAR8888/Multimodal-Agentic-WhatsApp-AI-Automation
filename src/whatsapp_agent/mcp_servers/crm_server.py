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

@mcp.tool()
async def apply_for_leave(employee_id: str, leave_type: str, from_date: str, to_date: str, reason: str) -> bool:
    """Submit a Leave Application for an employee to ERPNext. Ensure the employee is OTP verified before doing this."""
    crm = get_crm_provider()
    return await crm.apply_for_leave(employee_id, leave_type, from_date, to_date, reason)

@mcp.tool()
async def create_expense_claim(employee_id: str, expense_type: str, amount: float, reason: str) -> bool:
    """Submit an Expense Claim for an employee to ERPNext. Ensure the employee is OTP verified before doing this."""
    crm = get_crm_provider()
    return await crm.create_expense_claim(employee_id, expense_type, amount, reason)

@mcp.tool()
async def create_support_ticket(raised_by: str, subject: str, description: str) -> bool:
    """Create a new Support Ticket (Issue) in ERPNext for the customer or employee."""
    crm = get_crm_provider()
    return await crm.create_support_ticket(raised_by, subject, description)

if __name__ == "__main__":
    mcp.run(transport='stdio')
