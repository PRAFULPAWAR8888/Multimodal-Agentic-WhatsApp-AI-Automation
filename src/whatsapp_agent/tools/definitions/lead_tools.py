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
            "phone": {"type": "string"},
            "customer_name": {"type": "string"},
            "company": {"type": "string"},
            "email": {"type": "string"},
            "budget": {"type": "string"},
            "requirement": {"type": "string"},
            "qualification_score": {"type": "integer"}
        },
        "required": ["workspace_id", "qualification_score", "phone"]
    },
    risk_level=RiskLevel.MEDIUM
)
async def upsert_lead_record(
    workspace_id: str,
    qualification_score: int,
    phone: str,
    customer_name: Optional[str] = None,
    company: Optional[str] = None,
    email: Optional[str] = None,
    budget: Optional[str] = None,
    requirement: Optional[str] = None,
) -> bool:
    try:
        factory = _get_session_factory()
        ws_uuid = uuid.UUID(workspace_id)
        
        from sqlalchemy import select

        async with factory() as db:
            stmt = select(Lead).where(
                Lead.workspace_id == ws_uuid,
                Lead.phone == phone
            ).order_by(Lead.created_at.desc())
            result = await db.execute(stmt)
            lead = result.scalars().first()

            if lead:
                if customer_name:
                    lead.name = customer_name
                if email:
                    lead.email = email
                if company:
                    lead.company = company
                if requirement:
                    lead.requirement = requirement
                if budget:
                    lead.budget = budget
                if qualification_score is not None:
                    lead.lead_score = max(lead.lead_score or 0, qualification_score)
                    if lead.lead_score >= 60 and lead.status == LeadStatus.NEW:
                        lead.status = LeadStatus.QUALIFIED
                await db.commit()
                lead_id = str(lead.id)
                logger.info("lead_updated_in_db", lead_id=lead_id, lead_score=lead.lead_score)
            else:
                lead = Lead(
                    workspace_id=ws_uuid,
                    phone=phone,
                    name=customer_name,
                    email=email,
                    company=company,
                    requirement=requirement,
                    budget=budget,
                    lead_score=qualification_score,
                    status=LeadStatus.QUALIFIED if qualification_score >= 60 else LeadStatus.NEW,
                    intent=LeadIntent.PURCHASE
                )
                db.add(lead)
                await db.commit()
                lead_id = str(lead.id)
                logger.info("lead_saved_to_db", lead_id=lead_id, lead_score=qualification_score)
            
            # Trigger asynchronous CRM sync
            from arq import create_pool
            from arq.connections import RedisSettings
            from whatsapp_agent.config.settings import get_settings
            
            settings = get_settings()
            redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
            arq_pool = await create_pool(redis_settings)
            
            await arq_pool.enqueue_job("sync_lead_to_crm", lead_id)
            await arq_pool.close()
            
            logger.info("enqueued_lead_sync_to_crm", lead_id=lead_id)

        return True
    except Exception as e:
        logger.error("lead_save_failed", error=str(e))
        return False
