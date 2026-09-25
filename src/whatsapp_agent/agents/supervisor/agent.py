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
    "inquiry",          # General question about products/services
    "purchase",         # Ready to buy
    "support",          # Help with an existing issue
    "lead_capture",     # New lead requiring qualification
    "knowledge_query",  # Searching the knowledge base
    "scheduling",       # Booking appointments/meetings
    "media_analysis",   # Sent an image/document to analyze
    "voice_query",      # Voice note processed to text
    "crm_action",       # CRM-related (contact update, deal update)
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
    "support": "support",
    "lead_capture": "lead",
    "knowledge_query": "knowledge",
    "scheduling": "scheduling",
    "media_analysis": "media",
    "voice_query": "knowledge",     # Voice queries go to knowledge base by default
    "crm_action": "crm",
    "human_escalation": "human_escalation",
    "greeting": "deterministic",     # Handled directly, bypassed workflow
    "thanks": "deterministic",       # Handled directly
    "bye": "deterministic",          # Handled directly
    "unknown": "knowledge",          # Default fallback
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
- Be conservative with escalation — only escalate if the customer explicitly asks for a human, or the issue is clearly beyond AI capabilities (legal threats, abuse, complex billing disputes)
- Consider the conversation history for context
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
    "language": "<detected BCP-47 language code e.g. en, hi, mr, ta, te>"
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
    for turn in history[-5:]:  # Last 5 turns for context
        role = "Customer" if turn.get("role") == "user" else "AI"
        content = turn.get("content", "")[:200]
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
    effective_text = (
        state.get("effective_text")
        or state.get("transcription")
        or state.get("raw_text")
        or state.get("image_analysis")
        or state.get("document_text")
        or ""
    )

    if not effective_text.strip():
        logger.warning(
            "supervisor_empty_text",
            workspace_id=workspace_id,
            message_id=message_id,
        )
        return {
            **state,
            "intent": "unknown",
            "confidence_score": 0.0,
            "routed_to_agent": "knowledge",
            "language_detected": "en",
            "max_output_tokens": ResponseBudgetManager.get_output_budget("unknown")
        }

    # Deterministic bypass for simple messages to save LLM tokens
    text_lower = effective_text.strip().lower()
    deterministic_intent = None
    if text_lower in {"hi", "hello", "hey", "hola", "namaste"}:
        deterministic_intent = "greeting"
    elif text_lower in {"thanks", "thank you", "thx", "ty"}:
        deterministic_intent = "thanks"
    elif text_lower in {"bye", "goodbye", "cya"}:
        deterministic_intent = "bye"
        
    if deterministic_intent:
        logger.info(
            "supervisor_deterministic_bypass",
            workspace_id=workspace_id,
            intent=deterministic_intent
        )
        return {
            **state,
            "intent": deterministic_intent,
            "confidence_score": 1.0,
            "routed_to_agent": "deterministic",
            "escalation_required": False,
            "language_detected": "en",
            "max_output_tokens": ResponseBudgetManager.get_output_budget(deterministic_intent),
            "deterministic_response_trigger": True
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
        # Graceful degradation: route to knowledge agent on error
        return {
            **state,
            "intent": "unknown",
            "confidence_score": 0.0,
            "routed_to_agent": "knowledge",
            "error": f"Supervisor error: {exc}",
            "model_latency_ms": latency_ms,
            "max_output_tokens": ResponseBudgetManager.get_output_budget("unknown"),
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
