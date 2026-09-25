"""
CRM Agent.

Handles customer support queries, ticket creation, and status lookups.
Has access to tools to interact with the configured CRMProvider.
"""

from __future__ import annotations

import json
import time
from typing import Any

from whatsapp_agent.agents.llm_provider import get_llm_provider
from whatsapp_agent.agents.state import AgentState
from whatsapp_agent.tools.registry import default_registry, ToolRunner, ToolExecutionError
import whatsapp_agent.tools.definitions  # Ensure tools are registered
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

# ── Tool Definitions ──────────────────────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_customer_record",
            "description": "Look up the customer's profile, tier, and recent order history using their phone number.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_ticket",
            "description": "Create a new support ticket for the customer's issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_description": {
                        "type": "string",
                        "description": "A detailed summary of the customer's issue or complaint.",
                    }
                },
                "required": ["issue_description"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ticket_status",
            "description": "Check the status of an existing support ticket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "The ID of the ticket to check (e.g. 'TKT-100').",
                    }
                },
                "required": ["ticket_id"],
            },
        }
    }
]

# ── Agent Logic ───────────────────────────────────────────────────────────────

CRM_SYSTEM_PROMPT = """You are {persona_name}, a helpful support and CRM agent for {business_name}.
Your job is to assist the customer with their account, orders, or support tickets.

CRITICAL RULES:
1. Be empathetic, concise, and professional. Use {language} language.
2. {emoji_instruction}
3. If the user asks about their account or recent orders, USE THE `get_customer_record` TOOL first to get their info.
4. If the user reports an issue, complaint, or problem, USE THE `create_ticket` TOOL to file a ticket for them.
5. If you create a ticket, always give the customer their new Ticket ID in your response.
6. If the user asks for an update on a ticket, USE THE `get_ticket_status` TOOL.

Do NOT invent ticket IDs or customer details. Always use the tools to get real data.
"""


def _build_crm_prompt(state: AgentState) -> str:
    profile = state.get("business_profile") or {}
    emoji_instruction = (
        "You MAY use relevant emojis." if profile.get("ai_use_emoji") else "Do NOT use emojis."
    )
    
    return CRM_SYSTEM_PROMPT.format(
        persona_name=profile.get("ai_persona_name", "Support Assistant"),
        business_name=profile.get("business_name", "our business"),
        language=state.get("language_detected", "en"),
        emoji_instruction=emoji_instruction,
    )


async def crm_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: CRM Agent.
    """
    start_time = time.monotonic()
    workspace_id = state.get("workspace_id", "")
    message_id = state.get("message_id", "")
    phone = state.get("contact_wa_id", "Unknown")

    logger.info("crm_agent_responding", workspace_id=workspace_id, message_id=message_id)

    llm = get_llm_provider()
    tool_runner = ToolRunner(default_registry)
    system_prompt = _build_crm_prompt(state)
    effective_text = state.get("effective_text") or state.get("raw_text") or ""
    
    conversation_history = state.get("conversation_history", [])

    max_loops = 3
    current_message = effective_text
    
    for _ in range(max_loops):
        try:
            response, tool_calls = await llm.complete_with_tools(
                system_prompt=system_prompt,
                user_message=current_message,
                tools=TOOLS,
                conversation_history=conversation_history,
            )
            
            if not tool_calls:
                latency_ms = round((time.monotonic() - start_time) * 1000)
                logger.info("crm_agent_finished", latency_ms=latency_ms)
                return {
                    **state,
                    "response_text": response.content,
                    "response_voice": state.get("input_modality") == "voice",
                }

            tool_results_content = []
            
            for tc in tool_calls:
                fn_name = tc.get("function", {}).get("name")
                try:
                    args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                except json.JSONDecodeError:
                    args: dict[str, Any] = {}
                    
                logger.info("executing_crm_tool", tool=fn_name, args=args)
                
                # Inject state context into tool args where implicitly needed by the old hardcoded logic
                if fn_name in ["get_customer_record", "create_ticket"]:
                    args["phone"] = phone

                try:
                    result = await tool_runner.execute(
                        tool_name=fn_name,
                        arguments=args,
                        context={"is_authenticated": True, "user_id": phone}
                    )
                    tool_results_content.append(f"Tool {fn_name} result: {json.dumps(result)}")
                except ToolExecutionError as exc:
                    tool_results_content.append(f"Tool {fn_name} failed: {exc}")
                except Exception as exc:
                    tool_results_content.append(f"Tool {fn_name} unexpected error: {exc}")

            conversation_history.append({"role": "user", "content": current_message})
            conversation_history.append({"role": "assistant", "content": "I am checking the CRM system now..."})
            
            current_message = "OBSERVATION from CRM tools:\n" + "\n".join(tool_results_content) + "\nNow continue the conversation based on this information."

        except Exception as exc:
            logger.error("crm_agent_error", error=str(exc), exc_info=exc)
            return {
                **state,
                "response_text": "I apologize, I'm having trouble accessing our customer database right now.",
                "error": f"CRM agent error: {exc}",
            }

    return {
        **state,
        "response_text": "I'm still processing your request. Please hold on.",
        "response_voice": state.get("input_modality") == "voice",
    }
