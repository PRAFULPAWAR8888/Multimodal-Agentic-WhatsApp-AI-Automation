"""
Lead Qualification Agent.

Extracts structured data from unstructured conversation history and current messages
to identify potential B2B or B2C leads. Saves the extracted data to PostgreSQL.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from whatsapp_agent.agents.llm_provider import get_llm_provider
from whatsapp_agent.agents.state import AgentState
from whatsapp_agent.tools.registry import default_registry, ToolRunner
import whatsapp_agent.tools.definitions  # Ensure tools are registered
from whatsapp_agent.database.models.leads import LeadExtractionSchema
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

# Moved LeadExtractionSchema to models/leads.py and _upsert_lead_in_db to lead_tools.py

LEAD_SYSTEM_PROMPT = """You are {persona_name}, a lead qualification assistant for {business_name}.

Your job is to analyze the customer's message and extract structured lead information.

Customer's message: {question}

Respond ONLY with valid JSON matching this exact structure:
{{
    "customer_name": "<full name or null if not provided>",
    "company": "<company name or null if not applicable>",
    "email": "<email address or null if not provided>",
    "budget": "<mentioned budget/price range or null>",
    "requirement": "<brief summary of what the customer needs>",
    "qualification_score": <integer 0 to 100>,
    "is_lead": <true if the person shows buying intent, false otherwise>
}}

Scoring guide:
- 0-20: Just browsing, no intent
- 21-50: Some interest but vague
- 51-80: Clear interest with some details (budget, timeline, or specific product)
- 81-100: Strong buying intent with multiple qualifying details
"""


async def lead_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Lead Agent.
    """
    start_time = time.monotonic()
    workspace_id = state.get("workspace_id", "")
    message_id = state.get("message_id", "")

    logger.info("lead_agent_responding", workspace_id=workspace_id, message_id=message_id)

    effective_text = state.get("effective_text") or state.get("raw_text") or ""
    if not effective_text.strip():
        return {**state, "response_text": "I didn't receive a message."}

    try:
        profile = state.get("business_profile") or {}
        llm = get_llm_provider()
        
        system_prompt = LEAD_SYSTEM_PROMPT.format(
            persona_name=profile.get("ai_persona_name", "AI Assistant"),
            business_name=profile.get("business_name", "our business"),
            question=effective_text
        )

        # complete_json returns a tuple: (parsed_dict, LLMUsage)
        parsed_data, usage = await llm.complete_json(
            system_prompt=system_prompt,
            user_message=effective_text,
        )

        extracted_lead = LeadExtractionSchema.model_validate(parsed_data)
        
        if extracted_lead.is_lead and workspace_id:
            tool_runner = ToolRunner(default_registry)
            await tool_runner.execute(
                tool_name="upsert_lead_record",
                arguments={
                    "workspace_id": workspace_id,
                    "customer_name": extracted_lead.customer_name,
                    "company": extracted_lead.company,
                    "email": extracted_lead.email,
                    "budget": extracted_lead.budget,
                    "requirement": extracted_lead.requirement,
                    "qualification_score": extracted_lead.qualification_score,
                },
                context={"is_authenticated": True, "user_id": "system"}
            )

        latency_ms = round((time.monotonic() - start_time) * 1000)

        logger.info(
            "lead_agent_responded",
            workspace_id=workspace_id,
            is_lead=extracted_lead.is_lead,
            score=extracted_lead.qualification_score,
            latency_ms=latency_ms,
        )
        
        # Generate a polite response based on extraction
        if extracted_lead.is_lead:
            response_text = "Thank you! I've noted down your requirements. Our sales team will reach out to you shortly."
        else:
            response_text = "Thanks for the information. Let me know if you have any specific questions about our products or pricing!"

        return {
            **state,
            "response_text": response_text,
            "response_voice": state.get("input_modality") == "voice",
            "model_latency_ms": latency_ms,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
        }

    except Exception as exc:
        logger.error("lead_agent_error", error=str(exc), exc_info=exc)
        return {
            **state,
            "response_text": "I apologize, I couldn't process your request right now.",
            "error": f"Lead agent error: {exc}",
        }
