"""
Supervisor Agent — Orchestrates all specialized agents.

The Supervisor is the first node in the LangGraph workflow. It:
1. Loads business profile (AI persona, tone, restrictions)
2. Loads recent conversation history
3. Analyzes the customer message to detect intent
4. Routes to the correct specialized agent
5. Enforces safety guardrails and restrictions

This is the brain of the multi-agent system.

Architecture:
    Supervisor → [Knowledge | Sales | Support | Lead | Media | Voice | Scheduling | CRM | Human Escalation]
"""

from __future__ import annotations

import json
import time
from typing import Any

from whatsapp_agent.agents.llm_provider import get_llm_provider
from whatsapp_agent.agents.state import AgentState
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

# All valid intent values the supervisor can detect
VALID_INTENTS = [
    "inquiry",          # Asking general FAQ questions about the company (not starting a project)
    "purchase",         # Ready to buy an existing off-the-shelf product
    "support",          # Help with an existing issue, raising a complaint, reporting a bug, or checking ticket status
    "lead_capture",     # ANY request to develop/build a project, build an app/CRM, hire for services, or asking for quotes/pricing. MUST route to CRM agent to take their info first.
    "knowledge_query",  # Searching the knowledge base
    "scheduling",       # Booking appointments/meetings
    "media_analysis",   # Sent an image/document to analyze
    "voice_query",      # Voice note processed to text
    "crm_action",       # Explicit CRM-related (updating Client Name, Email, Phone, Reasons to Reach us)
    "human_escalation", # Explicitly requests human or very complex issue
    "greeting",         # Simple greeting (Hi, hello)
    "thanks",           # Simple thanks
    "bye",              # Simple goodbye
    "unknown",          # Cannot determine intent
]

# Mapping from intent to the specialized agent that handles it
INTENT_TO_AGENT: dict[str, str] = {
    "inquiry": "knowledge",
    "purchase": "sales",
    "support": "crm",                # Send all support/issues directly to CRM to create tickets
    "lead_capture": "crm",            # Send project build/develop requests to CRM agent to take information first
    "knowledge_query": "knowledge",
    "scheduling": "scheduling",
    "media_analysis": "media",
    "voice_query": "knowledge",
    "crm_action": "crm",              # Contact/client update requests route directly to CRM
    "human_escalation": "human_escalation",
    "greeting": "deterministic",
    "thanks": "deterministic",
    "bye": "deterministic",
    "unknown": "knowledge",
}

from whatsapp_agent.core.governance import ResponseBudgetManager

SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor AI for a business communication platform.

Your job is to analyze the customer's message and determine:
1. Their primary intent
2. Which specialized agent should handle their request
3. Whether human escalation is required

Business Context:
{business_context}

Available intents: {intents}

IMPORTANT RULES:
- Respond ONLY with valid JSON
- CONVERSATION CONTINUITY & CONFIRMATIONS (CRITICAL):
  * You MUST analyze the customer's message in the context of recent conversation history.
  * If the customer's message is a short answer, confirmation, affirmation, or denial (e.g. 'yes', 'no', 'sure', 'ok', 'okay', 'yep', 'confirm', 'go ahead', 'tomorrow', '1 pm', etc.) responding to a question or prompt asked by the AI in the conversation history, you MUST classify it with the intent of that ongoing conversation.
  * For example:
    - If the AI just asked to confirm or schedule an appointment/date/time and the customer responds 'yes', 'sure', 'confirm', or specifies a time/date, classify as 'scheduling'.
    - If the AI asked for contact details, project scope, or address, and the customer provides them, classify as 'crm_action' or 'lead_capture'.
    - If the AI asked if they want to speak with a human agent and the customer says 'yes', classify as 'human_escalation'.
    - If the AI was discussing a product purchase and the customer confirms, classify as 'purchase'.
  * NEVER classify an affirmative/confirming response ('yes', 'ok', 'sure', etc.) as 'unknown' if there is an active question or conversation flow in the history!
- ATTACHMENTS & DOCUMENTS (RESUMES, RFPs, IMAGES): If the user input contains Document Text or Image Analysis (such as an uploaded resume, candidate CV, project RFP, requirement doc, photo, or diagram), you MUST classify as 'media_analysis' so the Media Agent can review the document, extract candidate/client details into the CRM, and respond appropriately.
- PROJECT ONBOARDING: If any client comes wanting to build, develop, create, or customize any project (software, app, CRM, website, AI automation) or asking for project pricing/quotes, classify as 'lead_capture' so the CRM Agent can collect their contact information and project requirements first.
- CLIENT DETAILS / ONBOARDING RESPONSES: If the client is providing or updating their personal/contact details (Name, Email, Phone, Address, or Project Scope/Requirements) in response to onboarding questions, classify as 'crm_action' (or 'lead_capture') so the CRM Agent can immediately update their information in the CRM and provide confirmation feedback.
- SUBSEQUENT TURNS: If the client already registered their details and now wants to book a meeting or call, route to 'scheduling'. If they ask about standard plans/pricing, route to 'purchase' or 'inquiry'.
- Be conservative with escalation — only escalate if the customer explicitly asks for a human, or the issue is clearly beyond AI capabilities (legal threats, abuse, complex billing disputes)
- For voice messages, the text is a transcription — treat as normal text

Customer's recent conversation history:
{conversation_history}

Respond with this exact JSON structure:
{{
    "intent": "<one of: {intents}>",
    "confidence": <float 0.0 to 1.0>,
    "reasoning": "<brief explanation in 1 sentence>",
    "escalate_to_human": <true/false>,
    "escalation_reason": "<only if escalate_to_human is true, else null>",
    "language": "<detect the exact language and script used by the customer. Examples: English, Hindi, Marathi, Hinglish, Mix of English and Marathi, etc.>"
}}"""


def _build_business_context(business_profile: dict[str, Any] | None) -> str:
    """Format business profile into a context string for the supervisor prompt."""
    if not business_profile:
        return "Business: AI Assistant | Tone: Professional"

    lines = [
        f"Business: {business_profile.get('business_name', 'AI Assistant')}",
        f"AI Persona: {business_profile.get('ai_persona_name', 'AI Assistant')} ({business_profile.get('ai_persona_role', 'Assistant')})",
        f"Tone: {business_profile.get('ai_persona_tone', 'professional')}",
    ]
    if desc := business_profile.get("business_description"):
        lines.append(f"Description: {desc[:200]}")
    if instructions := business_profile.get("ai_custom_instructions"):
        lines.append(f"Instructions: {instructions[:300]}")
    if restrictions := business_profile.get("ai_restrictions"):
        lines.append(f"Restrictions: {restrictions}")
    return "\n".join(lines)


def _format_conversation_history(history: list[dict[str, Any]]) -> str:
    """Format conversation history for the supervisor prompt."""
    if not history:
        return "No prior conversation."

    lines = []
    for turn in history[-10:]:  # Last 10 turns for context
        role = "Customer" if turn.get("role") == "user" else "AI"
        content = turn.get("content", "")[:500]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def supervisor_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Supervisor Agent.

    Analyzes the message, detects intent, and determines routing.

    Args:
        state: Current AgentState with message content.

    Returns:
        Updated AgentState with intent, confidence, routing, and language.
    """
    start_time = time.monotonic()
    workspace_id = state.get("workspace_id", "")
    message_id = state.get("message_id", "")

    logger.info(
        "supervisor_analyzing",
        workspace_id=workspace_id,
        message_id=message_id,
        modality=state.get("input_modality"),
    )

    # Get the effective text to analyze
    # Get the effective text to analyze by combining multimodal inputs
    parts = []
    if state.get("raw_text"):
        parts.append(f"User Message: {state.get('raw_text')}")
    if state.get("transcription"):
        parts.append(f"Voice Transcription: {state.get('transcription')}")
    if state.get("image_analysis"):
        parts.append(f"Image Analysis: {state.get('image_analysis')}")
    if state.get("document_text"):
        parts.append(f"Document Text: {state.get('document_text')}")
        
    effective_text = "\n\n".join(parts)

    if not effective_text.strip():
        logger.warning(
            "supervisor_empty_text",
            workspace_id=workspace_id,
            message_id=message_id,
        )
        return {
            **state,
            "effective_text": effective_text,
            "intent": "unknown",
            "confidence_score": 0.0,
            "routed_to_agent": "knowledge",
            "language_detected": "en",
            "max_output_tokens": ResponseBudgetManager.get_output_budget("unknown")
        }

    # Deterministic bypass for simple messages to save LLM tokens
    raw_str = (state.get("raw_text") or "").strip().lower()
    text_lower = effective_text.strip().lower()
    if text_lower.startswith("user message:"):
        text_lower = text_lower[len("user message:"):].strip()
    check_text = raw_str or text_lower

    deterministic_intent = None
    if check_text in {"hi", "hello", "hey", "hola", "namaste", "halo"}:
        deterministic_intent = "greeting"
    elif check_text in {"thanks", "thank you", "thx", "ty", "dhanyawad", "shukriya", "ok thankyou", "ok thank you", "thank you so much"}:
        deterministic_intent = "thanks"
    elif check_text in {"bye", "goodbye", "cya", "alvida"}:
        deterministic_intent = "bye"
        
    if deterministic_intent:
        logger.info(
            "supervisor_deterministic_bypass",
            workspace_id=workspace_id,
            intent=deterministic_intent
        )
        return {
            **state,
            "effective_text": effective_text,
            "intent": deterministic_intent,
            "confidence_score": 1.0,
            "routed_to_agent": "deterministic",
            "escalation_required": False,
            "language_detected": "en",
            "max_output_tokens": ResponseBudgetManager.get_output_budget(deterministic_intent),
            "deterministic_response_trigger": True
        }

    # Deterministic check for lead onboarding form submission
    text_lower_full = effective_text.lower()
    lead_indicators = [
        "full name:", "name :", "name:", 
        "email address:", "email :", "email:", 
        "phone number:", "phone :", "phone:", 
        "address / location:", "address :", "location :",
        "reason to reach us", "project details", "reasons to reach us"
    ]
    matches = sum(1 for ind in lead_indicators if ind in text_lower_full)
    if matches >= 2:
        logger.info(
            "supervisor_deterministic_lead_bypass",
            workspace_id=workspace_id,
            matches=matches
        )
        return {
            **state,
            "effective_text": effective_text,
            "intent": "lead_capture",
            "confidence_score": 1.0,
            "routed_to_agent": "crm",
            "escalation_required": False,
            "language_detected": "en",
            "max_output_tokens": ResponseBudgetManager.get_output_budget("lead_capture"),
        }

    # Build prompt
    business_context = _build_business_context(state.get("business_profile"))
    conversation_history = _format_conversation_history(
        state.get("conversation_history", [])
    )
    intents_str = " | ".join(VALID_INTENTS)

    system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
        business_context=business_context,
        conversation_history=conversation_history,
        intents=intents_str,
    )

    # Check for escalation keywords from business profile BEFORE calling LLM
    escalation_keywords: list[str] = []
    if profile := state.get("business_profile"):
        escalation_keywords = profile.get("escalation_keywords_json") or []

    keyword_escalation = any(
        kw.lower() in effective_text.lower()
        for kw in escalation_keywords
        if kw
    )

    try:
        llm = get_llm_provider()
        result, usage = await llm.complete_json(
            system_prompt=system_prompt,
            user_message=effective_text,
            conversation_history=state.get("conversation_history", []),
        )

        intent = result.get("intent", "unknown")
        if intent not in VALID_INTENTS:
            logger.warning(
                "supervisor_invalid_intent",
                intent=intent,
                workspace_id=workspace_id,
            )
            intent = "unknown"

        confidence = float(result.get("confidence", 0.5))
        escalate = bool(result.get("escalate_to_human", False)) or keyword_escalation
        language = result.get("language", "en") or "en"
        routed_agent = "human_escalation" if escalate else INTENT_TO_AGENT.get(intent, "knowledge")

        latency_ms = round((time.monotonic() - start_time) * 1000)

        logger.info(
            "supervisor_routed",
            workspace_id=workspace_id,
            message_id=message_id,
            intent=intent,
            confidence=confidence,
            routed_to=routed_agent,
            escalate=escalate,
            language=language,
            latency_ms=latency_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )

        return {
            **state,
            "effective_text": effective_text,
            "intent": intent,
            "confidence_score": confidence,
            "routed_to_agent": routed_agent,
            "escalation_required": escalate,
            "escalation_reason": result.get("escalation_reason") if escalate else None,
            "language_detected": language,
            "model_latency_ms": latency_ms,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "max_output_tokens": ResponseBudgetManager.get_output_budget(intent),
        }

    except Exception as exc:
        latency_ms = round((time.monotonic() - start_time) * 1000)
        logger.error(
            "supervisor_error",
            workspace_id=workspace_id,
            message_id=message_id,
            error=str(exc),
            latency_ms=latency_ms,
            exc_info=exc,
        )
        # Smart degradation based on message content rather than blindly sending everything to knowledge
        raw_msg = (state.get("raw_text") or effective_text).lower()
        if any(term in raw_msg for term in ["build", "develop", "project", "app", "software", "quote", "pricing", "crm", "lead", "name:", "email:"]):
            fallback_agent = "crm"
            fallback_intent = "lead_capture"
        elif any(term in raw_msg for term in ["hi", "hello", "hey", "namaste"]):
            fallback_agent = "deterministic"
            fallback_intent = "greeting"
        elif any(term in raw_msg for term in ["thank", "thx", "ty", "shukriya"]):
            fallback_agent = "deterministic"
            fallback_intent = "thanks"
        else:
            fallback_agent = "knowledge"
            fallback_intent = "unknown"

        return {
            **state,
            "effective_text": effective_text,
            "intent": fallback_intent,
            "confidence_score": 0.0,
            "routed_to_agent": fallback_agent,
            "error": f"Supervisor error: {exc}",
            "model_latency_ms": latency_ms,
            "max_output_tokens": ResponseBudgetManager.get_output_budget(fallback_intent),
        }


def supervisor_router(state: AgentState) -> str:
    """
    LangGraph conditional edge function for the supervisor.

    Reads the routing decision from state and returns the next node name.

    Args:
        state: Current AgentState after supervisor_node ran.

    Returns:
        Next node name to route to.
    """
    if state.get("escalation_required"):
        return "human_escalation_agent"

    routed = state.get("routed_to_agent", "knowledge")
    node_map = {
        "knowledge": "knowledge_agent",
        "sales": "sales_agent",
        "support": "support_agent",
        "lead": "lead_agent",
        "media": "media_agent",
        "voice": "knowledge_agent",     # Voice intent → knowledge node
        "scheduling": "scheduling_agent",
        "crm": "crm_agent",
        "human_escalation": "human_escalation_agent",
        "deterministic": "deterministic_agent", # New bypass node
    }
    next_node = node_map.get(routed, "knowledge_agent")
    logger.debug(
        "supervisor_routing",
        routed_to=routed,
        next_node=next_node,
    )
    return next_node
