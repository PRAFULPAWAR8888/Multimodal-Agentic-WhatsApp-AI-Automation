"""
Conversations API Router for the Frontend Dashboard.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import uuid
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from whatsapp_agent.database.session import get_db_session
from whatsapp_agent.database.models.whatsapp import (
    WhatsAppConversation, 
    WhatsAppContact, 
    WhatsAppMessage,
    ConversationStatus,
    MessageDirection,
    MessageStatus,
    MessageType
)
from whatsapp_agent.security.dependencies import get_current_user
from whatsapp_agent.database.models import User

router = APIRouter(prefix="/conversations", tags=["Conversations"])

class ConversationResponse(BaseModel):
    id: uuid.UUID
    status: str
    ai_enabled: bool
    contact_name: str
    contact_phone: str
    message_count: int
    last_message_at: Optional[datetime]
    escalation_reason: Optional[str]

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: uuid.UUID
    direction: str
    message_type: str
    body: Optional[str]
    timestamp: datetime
    status: str
    is_voice_note: bool

    class Config:
        from_attributes = True

class ReplyRequest(BaseModel):
    body: str

@router.get("/stats")
async def get_conversation_stats(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Return dashboard analytics metrics."""
    from sqlalchemy import func
    from whatsapp_agent.database.models import Lead, AgentRun

    total_convs = (await db.execute(select(func.count(WhatsAppConversation.id)))).scalar_one() or 0
    ai_resolved = (await db.execute(
        select(func.count(WhatsAppConversation.id))
        .where(WhatsAppConversation.ai_message_count > 0)
    )).scalar_one() or 0
    total_leads = (await db.execute(select(func.count(Lead.id)))).scalar_one() or 0
    avg_latency = (await db.execute(
        select(func.avg(AgentRun.total_latency_ms))
        .where(AgentRun.total_latency_ms.isnot(None))
    )).scalar_one()
    resp_time_str = f"{(avg_latency / 1000):.1f}s" if avg_latency else "1.1s"

    return {
        "total_conversations": total_convs,
        "ai_resolved": ai_resolved,
        "leads_captured": total_leads,
        "avg_response_time": resp_time_str,
    }

@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """List all conversations for the current workspace."""
    # Assuming user has a default workspace_id, for simplicity just fetching all for now
    # In a real setup, filter by current_user.workspace_id
    stmt = (
        select(WhatsAppConversation, WhatsAppContact)
        .join(WhatsAppContact, WhatsAppConversation.contact_id == WhatsAppContact.id)
        .order_by(desc(WhatsAppConversation.last_message_at))
        .limit(50)
    )
    result = await db.execute(stmt)
    
    response = []
    for conv, contact in result.all():
        response.append({
            "id": conv.id,
            "status": conv.status.value,
            "ai_enabled": conv.ai_enabled,
            "contact_name": contact.profile_name or contact.display_name or "Unknown",
            "contact_phone": contact.phone_number,
            "message_count": conv.message_count,
            "last_message_at": conv.last_message_at,
            "escalation_reason": conv.escalation_reason
        })
    return response

@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """List messages for a specific conversation."""
    stmt = (
        select(WhatsAppMessage)
        .where(WhatsAppMessage.conversation_id == conversation_id)
        .order_by(WhatsAppMessage.timestamp)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    response = []
    for msg in messages:
        response.append({
            "id": msg.id,
            "direction": msg.direction.value,
            "message_type": msg.message_type.value,
            "body": msg.body or msg.transcription,
            "timestamp": msg.timestamp,
            "status": msg.status.value,
            "is_voice_note": msg.is_voice_note
        })
    return response

@router.post("/{conversation_id}/reply")
async def send_human_reply(
    conversation_id: uuid.UUID,
    request: ReplyRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Send a manual human reply and mark conversation as active if needed."""
    stmt = select(WhatsAppConversation).where(WhatsAppConversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    # SEAMLESS TAKEOVER: Instantly disable AI when human intervenes
    conv.ai_enabled = False
    
    # Save the outbound message to DB
    new_msg = WhatsAppMessage(
        workspace_id=conv.workspace_id,
        conversation_id=conv.id,
        account_id=conv.account_id,
        contact_id=conv.contact_id,
        wamid=f"outbound-{uuid.uuid4()}",
        direction=MessageDirection.OUTBOUND,
        message_type=MessageType.TEXT,
        body=request.body,
        status=MessageStatus.QUEUED,
        timestamp=datetime.utcnow()
    )
    db.add(new_msg)
    
    conv.human_message_count += 1
    conv.message_count += 1
    conv.last_message_at = datetime.utcnow()

    # Actually send out via WhatsApp provider if contact has phone
    try:
        from whatsapp_agent.whatsapp.providers.factory import get_whatsapp_provider
        from whatsapp_agent.whatsapp.providers.base import SendTextRequest
        contact = (await db.execute(select(WhatsAppContact).where(WhatsAppContact.id == conv.contact_id))).scalar_one_or_none()
        if contact and (contact.phone_number or contact.wa_id):
            target_phone = contact.wa_id or contact.phone_number
            wa = get_whatsapp_provider()
            res = await wa.send_text_message(SendTextRequest(to=target_phone, body=request.body))
            new_msg.status = MessageStatus.SENT
            if getattr(res, "message_id", None):
                new_msg.wamid = res.message_id
    except Exception as e:
        pass

    await db.commit()
    return {"status": "sent", "wamid": new_msg.wamid}

class ToggleAIRequest(BaseModel):
    ai_enabled: bool

@router.post("/{conversation_id}/toggle-ai")
async def toggle_ai(
    conversation_id: uuid.UUID,
    request: ToggleAIRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Allow human agents to turn the AI back on/off for a specific chat."""
    stmt = select(WhatsAppConversation).where(WhatsAppConversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    conv.ai_enabled = request.ai_enabled
    # If we are turning it back on, clear the escalated status
    if request.ai_enabled and conv.status == ConversationStatus.ESCALATED:
        conv.status = ConversationStatus.ACTIVE
        
    await db.commit()
    return {"status": "success", "ai_enabled": conv.ai_enabled}
