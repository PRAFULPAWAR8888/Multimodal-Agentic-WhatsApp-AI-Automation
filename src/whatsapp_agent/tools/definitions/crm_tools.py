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

@default_registry.register(
    name="update_crm_lead",
    description="Update an existing lead record in the CRM with updated contact or qualification details (Client Name, Email, Phone, Reasons to Reach us).",
    schema={
        "type": "object",
        "properties": {
            "lead_id": {"type": "string", "description": "The CRM lead ID"},
            "client_name": {"type": "string", "description": "Updated Client Name"},
            "name": {"type": "string", "description": "Updated Client Name"},
            "email": {"type": "string", "description": "Updated Client Email"},
            "phone": {"type": "string", "description": "Updated Client Phone Number"},
            "address": {"type": "string", "description": "Updated Client Address, City, or Location"},
            "reasons_to_reach_us": {"type": "string", "description": "Updated Reasons to Reach us / Requirement description"},
            "company": {"type": "string", "description": "Updated customer company/organization"},
            "status": {"type": "string", "description": "Updated lead status (e.g. Qualified, Contacted)"},
            "lead_score": {"type": "integer", "description": "Updated qualification score (0-100)"}
        },
        "required": []
    },
    risk_level=RiskLevel.MEDIUM
)
async def update_crm_lead(lead_id: str | None = None, **kwargs):
    crm = get_crm_provider()
    res = await crm.update_lead(lead_id=lead_id, **kwargs)

    # Sync local PostgreSQL lead record if phone is known
    phone = kwargs.get("phone") or kwargs.get("mobile_no")
    if phone:
        try:
            from whatsapp_agent.database.session import _get_session_factory
            from whatsapp_agent.database.models.leads import Lead
            from sqlalchemy import select
            factory = _get_session_factory()
            async with factory() as db:
                stmt = select(Lead).where(Lead.phone == phone).order_by(Lead.created_at.desc())
                lead = (await db.execute(stmt)).scalars().first()
                if lead:
                    name_val = kwargs.get("client_name") or kwargs.get("name")
                    if name_val:
                        lead.name = name_val
                    if kwargs.get("email"):
                        lead.email = kwargs.get("email")
                    reason_val = kwargs.get("reasons_to_reach_us") or kwargs.get("requirement")
                    address_val = kwargs.get("address")
                    if reason_val and address_val:
                        lead.requirement = f"{reason_val} (Location: {address_val})"
                    elif reason_val:
                        lead.requirement = reason_val
                    if address_val:
                        lead.notes = f"Address/Location: {address_val}"
                    if kwargs.get("company"):
                        lead.company = kwargs.get("company")
                    if lead_id and not lead.crm_contact_id:
                        lead.crm_contact_id = lead_id
                    await db.commit()
                else:
                    import uuid
                    from whatsapp_agent.database.models.leads import LeadStatus, LeadIntent
                    from whatsapp_agent.database.models.workspaces import Workspace
                    ws = (await db.execute(select(Workspace).limit(1))).scalar_one_or_none()
                    ws_id = ws.id if ws else uuid.uuid4()
                    name_val = kwargs.get("client_name") or kwargs.get("name") or "New Lead"
                    reason_val = kwargs.get("reasons_to_reach_us") or kwargs.get("requirement") or ""
                    address_val = kwargs.get("address")
                    new_lead = Lead(
                        workspace_id=ws_id,
                        phone=phone,
                        name=name_val,
                        email=kwargs.get("email"),
                        company=kwargs.get("company") or None,
                        requirement=f"{reason_val} (Location: {address_val})" if reason_val and address_val else (reason_val or "Inquiry"),
                        notes=f"Address/Location: {address_val}" if address_val else None,
                        lead_score=kwargs.get("lead_score") or 75,
                        status=LeadStatus.QUALIFIED,
                        intent=LeadIntent.PURCHASE,
                        crm_contact_id=lead_id
                    )
                    db.add(new_lead)
                    await db.commit()
        except Exception:
            pass

    return {
        "status": "success" if res else "failed",
        "updated_fields": {k: v for k, v in kwargs.items() if v is not None}
    }
