"""
Human Escalation Agent.

Handles taking over the conversation from the AI. This agent updates the database
to pause the AI from responding to future messages and politely informs the customer
that they are being transferred to a human.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from whatsapp_agent.agents.state import AgentState
from whatsapp_agent.database.models.whatsapp import (
    ConversationStatus,
    WhatsAppConversation,
    WhatsAppMessage,
)
from whatsapp_agent.database.session import _get_session_factory
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)


async def human_escalation_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Human Escalation.
    Pauses the AI for this conversation in the DB.
    """
    workspace_id = state.get("workspace_id", "")
    message_id = state.get("message_id", "")

    logger.info("human_escalation_agent_responding", workspace_id=workspace_id, message_id=message_id)

    response_text = (
        "I understand. I am transferring you to a human support agent now. "
        "Please hold on, and someone will be with you shortly."
    )

    try:
        msg_uuid = uuid.UUID(message_id)
        factory = _get_session_factory()
        
        async with factory() as db:
            # Find the message to get the conversation ID
            msg_result = await db.execute(
                select(WhatsAppMessage).where(WhatsAppMessage.id == msg_uuid)
            )
            message = msg_result.scalar_one_or_none()
            
            if message:
                # Find the conversation
                conv_result = await db.execute(
                    select(WhatsAppConversation).where(WhatsAppConversation.id == message.conversation_id)
                )
                conversation = conv_result.scalar_one_or_none()
                
                if conversation:
                    # Perform the actual handoff by disabling the AI
                    logger.warning(
                        "pausing_ai_for_human_handoff", 
                        conversation_id=str(conversation.id),
                        phone=state.get("contact_wa_id", "")
                    )
                    conversation.ai_enabled = False
                    conversation.status = ConversationStatus.ESCALATED
                    await db.commit()
                else:
                    logger.error("escalation_failed_conversation_not_found", message_id=message_id)
            else:
                logger.error("escalation_failed_message_not_found", message_id=message_id)
                
    except Exception as exc:
        logger.error("human_escalation_error", error=str(exc), exc_info=exc)
        # We still want to send the fallback text even if DB fails
        return {
            **state,
            "response_text": response_text,
            "error": f"Human escalation error: {exc}",
        }

    return {
        **state,
        "response_text": response_text,
        "response_voice": state.get("input_modality") == "voice",
    }
