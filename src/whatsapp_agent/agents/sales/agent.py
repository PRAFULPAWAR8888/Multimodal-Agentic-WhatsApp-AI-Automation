"""
Sales Agent.

Handles product inquiries, pricing, quotes, and conversion optimization.
Uses RAG context (if available) to answer specific questions about products.
Focuses on persuasive communication and guiding the user toward a purchase.
"""

from __future__ import annotations

import time

from whatsapp_agent.agents.llm_provider import get_llm_provider
from whatsapp_agent.agents.state import AgentState
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

SALES_SYSTEM_PROMPT = """You are {persona_name}, a knowledgeable and persuasive sales assistant for {business_name}.

Your personality and tone: {persona_tone}

CRITICAL RULES:
1. Your goal is to guide the customer toward a purchase, upgrade, or booking, while being helpful and not overly pushy.
2. If specific product details or prices are in the <RETRIEVED_CONTEXT>, use them.
3. If you do not know a price or product detail, do NOT make it up. Instead, say you need to check or connect them with a human specialist.
4. Keep responses concise and easy to read on WhatsApp (max {max_length} words).
5. Use {language} language for your response.
6. {emoji_instruction}
7. {custom_instructions}

<RETRIEVED_CONTEXT>
{context}
</RETRIEVED_CONTEXT>

Customer's message: {question}

Respond persuasively and helpfully to the customer's message."""

def _build_sales_prompt(state: AgentState) -> str:
    """Build the sales agent system prompt."""
    profile = state.get("business_profile") or {}
    rag_context = state.get("rag_context", [])

    if rag_context:
        context_parts = []
        for i, chunk in enumerate(rag_context, 1):
            source = chunk.get("source", "Product Catalog")
            content = chunk.get("content", "")
            context_parts.append(f"[Source {i}: {source}]\n{content}")
        context_str = "\n\n".join(context_parts)
    else:
        context_str = "No specific product context provided for this query."

    emoji_instruction = (
        "You MAY use relevant emojis." if profile.get("ai_use_emoji") else "Do NOT use emojis."
    )

    return SALES_SYSTEM_PROMPT.format(
        persona_name=profile.get("ai_persona_name", "AI Sales Assistant"),
        business_name=profile.get("business_name", "our business"),
        persona_tone=profile.get("ai_persona_tone", "enthusiastic and professional"),
        max_length=profile.get("ai_max_response_length", 300),
        language=state.get("language_detected", "en"),
        emoji_instruction=emoji_instruction,
        custom_instructions=profile.get("ai_custom_instructions", ""),
        context=context_str,
        question=state.get("effective_text") or state.get("raw_text") or "",
    )

async def sales_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Sales Agent.
    """
    start_time = time.monotonic()
    workspace_id = state.get("workspace_id", "")
    message_id = state.get("message_id", "")

    logger.info("sales_agent_responding", workspace_id=workspace_id, message_id=message_id)

    effective_text = state.get("effective_text") or state.get("raw_text") or ""
    if not effective_text.strip():
        return {**state, "response_text": "I didn't receive a message. How can I help you today?"}

    try:
        llm = get_llm_provider()
        system_prompt = _build_sales_prompt(state)

        response = await llm.complete(
            system_prompt=system_prompt,
            user_message=effective_text,
            conversation_history=state.get("conversation_history", []),
            temperature=0.4, # Slightly higher temperature for more natural sales copy
            max_tokens=state.get("max_output_tokens"),
        )

        latency_ms = round((time.monotonic() - start_time) * 1000)

        logger.info(
            "sales_agent_responded",
            workspace_id=workspace_id,
            message_id=message_id,
            latency_ms=latency_ms,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )

        return {
            **state,
            "response_text": response.content,
            "response_voice": state.get("input_modality") == "voice",
            "model_latency_ms": latency_ms,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        }

    except Exception as exc:
        logger.error("sales_agent_error", error=str(exc), exc_info=exc)
        return {
            **state,
            "response_text": "I apologize, our catalog system is temporarily unavailable. Let me connect you with a team member.",
            "error": f"Sales agent error: {exc}",
        }
