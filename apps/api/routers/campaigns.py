import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from whatsapp_agent.security.dependencies import get_current_user
from whatsapp_agent.database.models import User
from loguru import logger

router = APIRouter(prefix="/campaigns", tags=["Outbound Campaigns"])

class CampaignTriggerRequest(BaseModel):
    phone_number: str
    campaign_type: str  # "whatsapp_template" or "voice_call"
    template_name: Optional[str] = None
    template_variables: Optional[Dict[str, str]] = None
    ai_context: Optional[str] = None # e.g. "Remind customer about invoice INV-001 for $500"

@router.post("/trigger")
async def trigger_outbound_campaign(
    request: CampaignTriggerRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Trigger a proactive outbound campaign (WhatsApp Message or AI Voice Call).
    Can be called by external ERP webhooks (e.g. ERPNext, Marketo).
    """
    if request.campaign_type not in ["whatsapp_template", "voice_call"]:
        raise HTTPException(status_code=400, detail="Invalid campaign type. Use 'whatsapp_template' or 'voice_call'.")
        
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from whatsapp_agent.config.settings import get_settings
        
        settings = get_settings()
        redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
        arq_pool = await create_pool(redis_settings)
        
        # Enqueue background task for the outbound campaign
        job = await arq_pool.enqueue_job(
            "execute_outbound_campaign",
            request.phone_number,
            request.campaign_type,
            request.template_name,
            request.template_variables or {},
            request.ai_context or ""
        )
        
        await arq_pool.close()
        
        logger.info("outbound_campaign_enqueued", job_id=job.job_id, type=request.campaign_type, phone=request.phone_number)
        return {"status": "enqueued", "job_id": job.job_id}
        
    except Exception as e:
        logger.error("campaign_trigger_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
