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
        
    # Re-enable AI or keep it disabled? Typically human sending a message keeps it disabled, 
    # but we might want an explicit toggle. For now, leave ai_enabled as False.
    
    # Save the outbound message to DB (Worker would usually poll and send this, or we send directly)
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
    
    await db.commit()
    return {"status": "queued"}
