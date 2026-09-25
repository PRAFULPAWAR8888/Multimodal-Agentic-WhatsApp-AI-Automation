"""
Support Agent.

Handles customer issues, troubleshooting, order tracking, and complaints.
Emphasizes empathy and clear instructions.
Flags escalation if the issue cannot be resolved or user is very frustrated.
"""

from __future__ import annotations

import time

from whatsapp_agent.agents.llm_provider import get_llm_provider
from whatsapp_agent.agents.state import AgentState
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

SUPPORT_SYSTEM_PROMPT = """You are {persona_name}, an empathetic customer support specialist for {business_name}.

Your personality and tone: {persona_tone}

CRITICAL RULES:
1. Show empathy and apologize if the customer is facing an issue.
2. Use the <RETRIEVED_CONTEXT> for policies, troubleshooting steps, or tracking info.
3. If you cannot solve the problem or the customer asks for a human, you MUST inform them you are transferring them to a human agent, and be sure to output <ESCALATE> somewhere in your response.
4. Do NOT make up policies or promise refunds unless it is explicitly in the context.
5. Keep responses concise (max {max_length} words).
6. Use {language} language for your response.
7. {emoji_instruction}
8. {custom_instructions}

<RETRIEVED_CONTEXT>
{context}
</RETRIEVED_CONTEXT>

Customer's message: {question}

Respond empathetically and helpfully."""

def _build_support_prompt(state: AgentState) -> str:
    """Build the support agent system prompt."""
    profile = state.get("business_profile") or {}
    rag_context = state.get("rag_context", [])

    if rag_context:
        context_parts = []
        for i, chunk in enumerate(rag_context, 1):
            source = chunk.get("source", "Support Knowledge Base")
            content = chunk.get("content", "")
            context_parts.append(f"[Source {i}: {source}]\n{content}")
        context_str = "\n\n".join(context_parts)
    else:
        context_str = "No specific support context found."

    emoji_instruction = (
        "You MAY use relevant emojis." if profile.get("ai_use_emoji") else "Do NOT use emojis."
    )

    return SUPPORT_SYSTEM_PROMPT.format(
        persona_name=profile.get("ai_persona_name", "AI Support Agent"),
        business_name=profile.get("business_name", "our business"),
        persona_tone=profile.get("ai_persona_tone", "empathetic and professional"),
        max_length=profile.get("ai_max_response_length", 400),
        language=state.get("language_detected", "en"),
        emoji_instruction=emoji_instruction,
        custom_instructions=profile.get("ai_custom_instructions", ""),
        context=context_str,
        question=state.get("effective_text") or state.get("raw_text") or "",
    )

async def support_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Support Agent.
    """
    start_time = time.monotonic()
    workspace_id = state.get("workspace_id", "")
    message_id = state.get("message_id", "")

    logger.info("support_agent_responding", workspace_id=workspace_id, message_id=message_id)

    effective_text = state.get("effective_text") or state.get("raw_text") or ""
    if not effective_text.strip():
        return {**state, "response_text": "I didn't receive a message. How can I assist you with your issue?"}

    try:
        llm = get_llm_provider()
        system_prompt = _build_support_prompt(state)

        response = await llm.complete(
            system_prompt=system_prompt,
            user_message=effective_text,
            conversation_history=state.get("conversation_history", []),
            temperature=0.2, # Low temp for policy adherence
            max_tokens=state.get("max_output_tokens"),
        )

        latency_ms = round((time.monotonic() - start_time) * 1000)
        
        # Check if the LLM decided to escalate
        escalation_required = "<ESCALATE>" in response.content
        clean_response = response.content.replace("<ESCALATE>", "").strip()

        logger.info(
            "support_agent_responded",
            workspace_id=workspace_id,
            message_id=message_id,
            escalation=escalation_required,
            latency_ms=latency_ms,
        )

        return {
            **state,
            "response_text": clean_response,
            "response_voice": state.get("input_modality") == "voice",
            "escalation_required": state.get("escalation_required", False) or escalation_required,
            "model_latency_ms": latency_ms,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        }

    except Exception as exc:
        logger.error("support_agent_error", error=str(exc), exc_info=exc)
        return {
            **state,
            "response_text": "I apologize, our support systems are down. I'll flag this for our human team to review ASAP.",
            "escalation_required": True,
            "error": f"Support agent error: {exc}",
        }
