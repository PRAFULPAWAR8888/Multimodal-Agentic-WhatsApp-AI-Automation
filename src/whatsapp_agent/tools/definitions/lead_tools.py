import uuid
from typing import Optional
from whatsapp_agent.tools.registry import default_registry, RiskLevel
from whatsapp_agent.database.session import _get_session_factory
from whatsapp_agent.database.models.leads import Lead, LeadStatus, LeadIntent
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

@default_registry.register(
    name="upsert_lead_record",
    description="Save or update a lead record in the local database.",
    schema={
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string"},
            "customer_name": {"type": "string"},
            "company": {"type": "string"},
            "email": {"type": "string"},
            "budget": {"type": "string"},
            "requirement": {"type": "string"},
            "qualification_score": {"type": "integer"}
        },
        "required": ["workspace_id", "qualification_score"]
    },
    risk_level=RiskLevel.MEDIUM
)
async def upsert_lead_record(
    workspace_id: str,
    qualification_score: int,
    customer_name: Optional[str] = None,
    company: Optional[str] = None,
    email: Optional[str] = None,
    budget: Optional[str] = None,
    requirement: Optional[str] = None,
) -> bool:
    try:
        factory = _get_session_factory()
        ws_uuid = uuid.UUID(workspace_id)
        
        async with factory() as db:
            lead = Lead(
                workspace_id=ws_uuid,
                name=customer_name,
                email=email,
                company=company,
                requirement=requirement,
                budget=budget,
                lead_score=qualification_score,
                status=LeadStatus.NEW,
                intent=LeadIntent.PURCHASE
            )
            db.add(lead)
            await db.commit()
            logger.info("lead_saved_to_db", lead_score=qualification_score)
        return True
    except Exception as e:
        logger.error("lead_save_failed", error=str(e))
        return False
