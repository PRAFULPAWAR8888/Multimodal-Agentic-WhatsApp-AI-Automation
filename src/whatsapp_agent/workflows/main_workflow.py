"""
LangGraph Workflow Definition.

Assembles all agent nodes into a single StateGraph workflow.

Graph structure:
    START
      │
      ▼
    [load_business_profile]   ← loads workspace config from DB
      │
      ▼
    [retrieve_context]        ← RAG: embed query + vector search pgvector
      │
      ▼
    [supervisor]              ← detect intent, route to agent
      │
      ├─→ [knowledge_agent]       ← knowledge/FAQ/product questions
      ├─→ [sales_agent]           ← purchase intent, pricing (stub)
      ├─→ [support_agent]         ← existing customer support (stub)
      ├─→ [lead_agent]            ← lead capture & qualification (stub)
      ├─→ [media_agent]           ← image/document analysis (stub)
      ├─→ [scheduling_agent]      ← appointment booking (stub)
      ├─→ [crm_agent]             ← CRM operations (stub)
      └─→ [human_escalation_agent]← human takeover (stub)
              │
              ▼
    [send_response]           ← sends via WhatsApp provider
              │
              ▼
            END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from whatsapp_agent.agents.state import AgentState
from whatsapp_agent.agents.supervisor.agent import supervisor_node, supervisor_router
from whatsapp_agent.agents.knowledge.agent import knowledge_agent_node
from whatsapp_agent.agents.sales.agent import sales_agent_node
from whatsapp_agent.agents.support.agent import support_agent_node
from whatsapp_agent.agents.lead.agent import lead_agent_node
from whatsapp_agent.agents.media.agent import media_agent_node
from whatsapp_agent.agents.scheduling.agent import scheduling_agent_node
from whatsapp_agent.agents.crm.agent import crm_agent_node
from whatsapp_agent.agents.human_escalation.agent import human_escalation_agent_node
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

async def deterministic_agent_node(state: AgentState) -> AgentState:
    """Handles fast rule-based responses bypassing the LLM entirely."""
    intent = state.get("intent")
    text_lower = (state.get("effective_text") or "").strip().lower()
    profile = state.get("business_profile") or {}
    persona = profile.get("ai_persona_name") or "AI Assistant"
    business = profile.get("business_name")
    use_emoji = profile.get("ai_use_emoji", True)

    emoji = " 😊" if use_emoji else ""
    business_intro = f" I am {persona} from {business}." if (business and business not in ["Our Business", "Default Workspace"]) else ""

    # Default English responses
    response_text = f"Hello!{business_intro} How can I assist you today?{emoji}"

    if intent == "greeting":
        if text_lower in {"namaste"}:
            response_text = f"Namaste!{business_intro} How can I assist you today? (नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?){emoji}"
        elif text_lower in {"hola"}:
            response_text = f"¡Hola!{business_intro} ¿Cómo puedo ayudarte hoy?{emoji}"
        else:
            response_text = f"Hello!{business_intro} How can I assist you today?{emoji}"
    elif intent == "thanks":
        if text_lower in {"dhanyawad", "shukriya"}:
            response_text = f"You're welcome! Let me know if you need anything else from {business or 'us'}. (आपका स्वागत है!){emoji}"
        elif text_lower in {"gracias"}:
            response_text = f"¡De nada! Déjame saber si necesitas algo más.{emoji}"
        else:
            response_text = f"You're welcome! Let me know if you need anything else.{emoji}"
    elif intent == "bye":
        if text_lower in {"alvida", "phir milenge"}:
            response_text = f"Goodbye! Have a great day! (अलविदा!){emoji}"
        elif text_lower in {"adios", "chao"}:
            response_text = f"¡Adiós! ¡Que tengas un buen día!{emoji}"
        else:
            response_text = f"Goodbye! Have a great day from {business or 'us'}!{emoji}"

    return {
        **state,
        "response_text": response_text
    }


# ── Pre-Agent Nodes ────────────────────────────────────────────────────────────

async def load_business_profile_node(state: AgentState) -> AgentState:
    """
    Load the BusinessProfile configuration for this workspace.

    TODO (Phase 8): Load from DB via WorkspaceRepository.
    For now, returns a default profile.
    """
    logger.debug(
        "loading_business_profile",
        workspace_id=state.get("workspace_id"),
    )
    import uuid
    from whatsapp_agent.database.session import _get_session_factory
    from whatsapp_agent.database.repositories.workspaces import WorkspaceRepository

    workspace_id = state.get("workspace_id")
    if not workspace_id:
        return state

    factory = _get_session_factory()
    async with factory() as db:
        repo = WorkspaceRepository(db)
        try:
            ws_uuid = uuid.UUID(workspace_id)
            profile = await repo.get_business_profile(ws_uuid)
        except Exception as e:
            logger.error("failed_to_load_business_profile", error=str(e))
            profile = None

        if not profile:
            from sqlalchemy import select
            from whatsapp_agent.database.models import Workspace
            default_ws = (await db.execute(select(Workspace).limit(1))).scalar_one_or_none()
            if default_ws:
                profile = await repo.get_business_profile(default_ws.id)

    if not profile:
        profile = {
            "business_name": "Our Business",
            "ai_persona_name": "AI Assistant",
            "ai_persona_role": "Customer Support",
            "ai_persona_tone": "professional",
            "ai_response_language": "en",
            "ai_max_response_length": 500,
            "ai_use_emoji": False,
            "ai_custom_instructions": "",
            "ai_restrictions": "",
            "escalation_keywords_json": ["speak to human", "talk to agent", "human please", "legal action"],
        }
    return {**state, "business_profile": profile}


async def retrieve_context_node(state: AgentState) -> AgentState:
    """
    RAG retrieval: embed query and search pgvector for relevant knowledge chunks.

    TODO (Phase 9): Implement full vector search with sentence-transformers + pgvector.
    For now, returns empty context (knowledge agent will handle gracefully).
    """
    logger.debug(
        "retrieving_context",
        workspace_id=state.get("workspace_id"),
        modality=state.get("input_modality"),
    )
    from whatsapp_agent.database.session import _get_session_factory
    from whatsapp_agent.rag.retrieval.vector_retriever import VectorRetriever

    workspace_id = state.get("workspace_id")
    # For RAG query, use user's explicit question or first 300 chars to prevent embedding explosion
    query = (state.get("raw_text") or state.get("effective_text") or "").strip()[:300]
    
    if not workspace_id or not query:
        return {**state, "rag_context": []}

    factory = _get_session_factory()
    chunks = []
    try:
        import asyncio
        async with factory() as db:
            retriever = VectorRetriever(db)
            chunks = await asyncio.wait_for(
                retriever.retrieve_for_agent(
                    query=query, 
                    workspace_id=workspace_id,
                    top_k=5
                ),
                timeout=4.0
            )
    except Exception as e:
        logger.error("rag_retrieval_failed", error=str(e), workspace_id=workspace_id)
        
    return {**state, "rag_context": chunks}


async def send_response_node(state: AgentState) -> AgentState:
    """
    Send the agent's response back to the customer via WhatsApp.

    Handles:
    - Text responses: send as plain text
    - Voice responses: TODO convert to OGG/Opus via Piper TTS, send as voice note
    - Respects response_voice flag (voice-in → voice-out)
    """
    from whatsapp_agent.whatsapp.providers.factory import get_whatsapp_provider
    from whatsapp_agent.whatsapp.providers.base import SendTextRequest, SendAudioRequest, UploadMediaRequest
    from whatsapp_agent.voice.tts.piper_tts import get_tts_provider

    workspace_id = state.get("workspace_id", "")
    response_text = state.get("response_text", "")
    contact_wa_id = state.get("contact_wa_id", "")
    response_voice = state.get("response_voice", False)

    if not response_text:
        logger.warning(
            "send_response_empty",
            workspace_id=workspace_id,
            contact=contact_wa_id,
        )
        return state

    if contact_wa_id in ["playground_user", "test_user"] or not contact_wa_id.replace("+", "").isdigit():
        logger.info(
            "playground_or_test_response_skip_send",
            workspace_id=workspace_id,
            contact=contact_wa_id,
            response_length=len(response_text)
        )
        return state



    try:
        provider = get_whatsapp_provider()

        if response_voice:
            try:
                # 1. Generate OGG/Opus using Piper TTS
                tts = get_tts_provider()
                ogg_bytes = await tts.generate_voice_note(response_text)
                
                # 2. Upload to WhatsApp
                media_id = await provider.upload_media(
                    UploadMediaRequest(
                        file_content=ogg_bytes,
                        mime_type="audio/ogg",
                        filename="voice_note.ogg"
                    )
                )
                
                # 3. Send as Voice Note
                result = await provider.send_voice_message(
                    SendAudioRequest(to=contact_wa_id, media_id=media_id, voice=True)
                )
                
                logger.info(
                    "voice_response_sent",
                    workspace_id=workspace_id,
                    contact=contact_wa_id,
                    wamid=result.message_id,
                    response_length=len(response_text),
                )
                return state
                
            except Exception as e:
                logger.error("voice_generation_failed_falling_back", error=str(e), exc_info=e)
                # Fall through to text if voice fails

        # Send text response
        result = await provider.send_text_message(
            SendTextRequest(to=contact_wa_id, body=response_text)
        )
        
        # Persist outbound message to database
        from whatsapp_agent.database.session import _get_session_factory
        from whatsapp_agent.database.models.whatsapp import WhatsAppMessage, MessageDirection, MessageType, MessageStatus, Modality
        from sqlalchemy import select
        from datetime import datetime, timezone

        factory = _get_session_factory()
        async with factory() as db:
            # We need the conversation_id and account_id which we can get from the inbound message_id
            message_id_str = state.get("message_id")
            if message_id_str:
                import uuid
                msg_uuid = uuid.UUID(message_id_str)
                inbound_msg = (await db.execute(select(WhatsAppMessage).where(WhatsAppMessage.id == msg_uuid))).scalar_one_or_none()
                if inbound_msg:
                    outbound_msg = WhatsAppMessage(
                        workspace_id=inbound_msg.workspace_id,
                        conversation_id=inbound_msg.conversation_id,
                        account_id=inbound_msg.account_id,
                        contact_id=inbound_msg.contact_id,
                        wamid=result.message_id or f"mock-outbound-{uuid.uuid4()}",
                        direction=MessageDirection.OUTBOUND,
                        message_type=MessageType.TEXT,
                        modality=Modality.TEXT,
                        body=response_text,
                        status=MessageStatus.SENT,
                        timestamp=datetime.now()
                    )
                    db.add(outbound_msg)
                    
                    # Update conversation metrics
                    from whatsapp_agent.database.models.whatsapp import WhatsAppConversation
                    conv = (await db.execute(select(WhatsAppConversation).where(WhatsAppConversation.id == inbound_msg.conversation_id))).scalar_one_or_none()
                    if conv:
                        conv.message_count += 1
                        conv.ai_message_count += 1
                        conv.last_message_at = outbound_msg.timestamp
                        
                    await db.commit()

        logger.info(
            "response_sent_and_persisted",
            workspace_id=workspace_id,
            contact=contact_wa_id,
            wamid=result.message_id,
            response_length=len(response_text),
            voice=False,
        )

    except Exception as exc:
        logger.error(
            "send_response_failed",
            workspace_id=workspace_id,
            contact=contact_wa_id,
            error=str(exc),
            exc_info=exc,
        )

    return state


# ── Graph Assembly ─────────────────────────────────────────────────────────────

def build_workflow() -> StateGraph:
    """
    Build and compile the full multi-agent LangGraph workflow.

    Returns:
        Compiled StateGraph ready for .ainvoke() calls.
    """
    graph = StateGraph(AgentState)

    # ── Add Nodes ──────────────────────────────────────────────────────────────
    graph.add_node("load_profile", load_business_profile_node)
    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("knowledge_agent", knowledge_agent_node)
    graph.add_node("sales_agent", sales_agent_node)
    graph.add_node("support_agent", support_agent_node)
    graph.add_node("lead_agent", lead_agent_node)
    graph.add_node("media_agent", media_agent_node)
    graph.add_node("scheduling_agent", scheduling_agent_node)
    graph.add_node("crm_agent", crm_agent_node)
    graph.add_node("human_escalation_agent", human_escalation_agent_node)
    graph.add_node("deterministic_agent", deterministic_agent_node)
    graph.add_node("send_response", send_response_node)

    # ── Sequential edges (START → pre-processing → supervisor) ────────────────
    graph.add_edge(START, "load_profile")
    graph.add_edge("load_profile", "retrieve_context")
    graph.add_edge("retrieve_context", "supervisor")

    # ── Conditional edge (supervisor → specialized agent) ─────────────────────
    graph.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "knowledge_agent": "knowledge_agent",
            "sales_agent": "sales_agent",
            "support_agent": "support_agent",
            "lead_agent": "lead_agent",
            "media_agent": "media_agent",
            "scheduling_agent": "scheduling_agent",
            "crm_agent": "crm_agent",
            "human_escalation_agent": "human_escalation_agent",
            "deterministic_agent": "deterministic_agent",
        },
    )

    # ── All agents converge at send_response ──────────────────────────────────
    for agent_node in [
        "knowledge_agent",
        "sales_agent",
        "support_agent",
        "lead_agent",
        "media_agent",
        "scheduling_agent",
        "crm_agent",
        "human_escalation_agent",
        "deterministic_agent",
    ]:
        graph.add_edge(agent_node, "send_response")

    # ── END ────────────────────────────────────────────────────────────────────
    graph.add_edge("send_response", END)

    compiled = graph.compile()
    logger.info("workflow_compiled", nodes=list(graph.nodes))
    return compiled


# Module-level compiled workflow singleton
_workflow: StateGraph | None = None


def get_workflow() -> StateGraph:
    """Return or build the compiled workflow singleton."""
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
    return _workflow
