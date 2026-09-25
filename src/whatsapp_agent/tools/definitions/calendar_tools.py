from whatsapp_agent.tools.registry import default_registry, RiskLevel
from whatsapp_agent.integrations.calendar.factory import get_calendar_provider

@default_registry.register(
    name="get_availability",
    description="Check available appointment slots for a specific date.",
    schema={
        "type": "object",
        "properties": {
            "date": {"type": "string"}
        },
        "required": ["date"]
    },
    risk_level=RiskLevel.LOW
)
async def get_availability(date: str):
    calendar = get_calendar_provider()
    return await calendar.get_availability(date)

@default_registry.register(
    name="book_appointment",
    description="Book an appointment for a specific date and time.",
    schema={
        "type": "object",
        "properties": {
            "date": {"type": "string"},
            "time": {"type": "string"},
            "name": {"type": "string"},
            "phone": {"type": "string"}
        },
        "required": ["date", "time", "name", "phone"]
    },
    risk_level=RiskLevel.MEDIUM
)
async def book_appointment(date: str, time: str, name: str, phone: str):
    calendar = get_calendar_provider()
    return await calendar.book_appointment(date, time, name, phone)
