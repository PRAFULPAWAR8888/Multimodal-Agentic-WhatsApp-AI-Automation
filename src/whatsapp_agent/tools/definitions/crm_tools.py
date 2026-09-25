from whatsapp_agent.tools.registry import default_registry, RiskLevel
from whatsapp_agent.integrations.crm.factory import get_crm_provider

@default_registry.register(
    name="get_customer_record",
    description="Look up the customer's profile, tier, and recent order history using their phone number.",
    schema={},
    risk_level=RiskLevel.LOW
)
async def get_customer_record(phone: str):
    crm = get_crm_provider()
    return await crm.get_customer_record(phone)

@default_registry.register(
    name="create_ticket",
    description="Create a new support ticket for the customer's issue.",
    schema={
        "type": "object",
        "properties": {
            "phone": {"type": "string"},
            "issue_description": {"type": "string"}
        },
        "required": ["phone", "issue_description"]
    },
    risk_level=RiskLevel.MEDIUM
)
async def create_ticket(phone: str, issue_description: str):
    crm = get_crm_provider()
    return await crm.create_ticket(phone, issue_description)

@default_registry.register(
    name="get_ticket_status",
    description="Check the status of an existing support ticket.",
    schema={
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string"}
        },
        "required": ["ticket_id"]
    },
    risk_level=RiskLevel.LOW
)
async def get_ticket_status(ticket_id: str):
    crm = get_crm_provider()
    return await crm.get_ticket_status(ticket_id)
