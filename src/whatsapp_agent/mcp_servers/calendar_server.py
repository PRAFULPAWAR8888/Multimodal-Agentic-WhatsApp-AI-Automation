from typing import Any
from mcp.server.mcpserver import MCPServer
from whatsapp_agent.integrations.calendar.factory import get_calendar_provider
import asyncio

mcp = MCPServer("Calendar_Server")

@mcp.tool()
async def get_availability(date: str) -> list[str]:
    """Check available appointment slots for a specific date (YYYY-MM-DD)."""
    calendar = get_calendar_provider()
    return await calendar.get_availability(date)

@mcp.tool()
async def book_appointment(date: str, time: str, name: str, phone: str) -> bool:
    """Book an appointment for a specific date and time."""
    calendar = get_calendar_provider()
    return await calendar.book_appointment(date, time, name, phone)

if __name__ == "__main__":
    mcp.run(transport='stdio')
