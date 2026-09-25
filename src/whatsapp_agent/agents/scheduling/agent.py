"""
Scheduling Agent.

Handles Calendar booking requests. Has access to tools to check availability 
and book appointments via the configured CalendarProvider.
"""

from __future__ import annotations

import json
import time
from datetime import datetime

from whatsapp_agent.agents.llm_provider import get_llm_provider
from whatsapp_agent.agents.state import AgentState
from whatsapp_agent.tools.registry import default_registry, ToolRunner, ToolExecutionError
import whatsapp_agent.tools.definitions  # Ensure tools are registered
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

# ── Tool Definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_availability",
            "description": "Check available appointment slots for a specific date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The date to check in YYYY-MM-DD format (e.g. 2026-09-24).",
                    }
                },
                "required": ["date"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment for a specific date and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The date to book in YYYY-MM-DD format (e.g. 2026-09-24).",
                    },
                    "time": {
                        "type": "string",
                        "description": "The time to book (e.g. '10:00 AM').",
                    },
                    "name": {
                        "type": "string",
                        "description": "The customer's name.",
                    }
                },
                "required": ["date", "time", "name"],
            },
        }
    }
]

# ── Agent Logic ───────────────────────────────────────────────────────────────

SCHEDULING_SYSTEM_PROMPT = """You are {persona_name}, a helpful scheduling assistant for {business_name}.
Your job is to help the user book an appointment. 
Today's date is {today}.

CRITICAL RULES:
1. Be polite, concise, and professional. Use {language} language.
2. {emoji_instruction}
3. If the user wants to book an appointment but hasn't specified a date, ask them what date works for them.
4. When they give a date, USE THE `get_availability` TOOL to check the calendar. DO NOT invent available times.
5. Once you have the available times, list them to the user and ask them to choose one.
6. Once they choose a time, and you know their name, USE THE `book_appointment` TOOL to book it.
7. Confirm the booking only after the tool returns success.
8. If the tool returns failure (e.g., slot already taken), apologize and offer alternative slots using the `get_availability` tool.

Do NOT confirm an appointment without calling the `book_appointment` tool.
"""


def _build_scheduling_prompt(state: AgentState) -> str:
    profile = state.get("business_profile") or {}
    emoji_instruction = (
        "You MAY use relevant emojis." if profile.get("ai_use_emoji") else "Do NOT use emojis."
    )
    
    return SCHEDULING_SYSTEM_PROMPT.format(
        persona_name=profile.get("ai_persona_name", "AI Assistant"),
        business_name=profile.get("business_name", "our business"),
        today=datetime.now().strftime("%Y-%m-%d"),
        language=state.get("language_detected", "en"),
        emoji_instruction=emoji_instruction,
    )


async def scheduling_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Scheduling Agent.
    """
    start_time = time.monotonic()
    workspace_id = state.get("workspace_id", "")
    message_id = state.get("message_id", "")
    phone = state.get("contact_wa_id", "Unknown")

    logger.info("scheduling_agent_responding", workspace_id=workspace_id, message_id=message_id)

    llm = get_llm_provider()
    tool_runner = ToolRunner(default_registry)
    system_prompt = _build_scheduling_prompt(state)
    effective_text = state.get("effective_text") or state.get("raw_text") or ""
    
    conversation_history = state.get("conversation_history", [])

    # The agent loop handles up to 3 tool calls in a single turn
    max_loops = 3
    current_message = effective_text
    
    for _ in range(max_loops):
        try:
            # We use complete_with_tools which returns the LLMResponse and a list of tool calls
            # Wait, our complete_with_tools signature expects dicts for history but our history is role/content dicts.
            response, tool_calls = await llm.complete_with_tools(
                system_prompt=system_prompt,
                user_message=current_message,
                tools=TOOLS,
                conversation_history=conversation_history,
            )
            
            # If no tool calls, we are done, the LLM is just replying to the user
            if not tool_calls:
                latency_ms = round((time.monotonic() - start_time) * 1000)
                logger.info("scheduling_agent_finished", latency_ms=latency_ms)
                return {
                    **state,
                    "response_text": response.content,
                    "response_voice": state.get("input_modality") == "voice",
                }

            # We have tool calls. We execute them and feed the results back.
            tool_results_content = []
            
            for tc in tool_calls:
                fn_name = tc.get("function", {}).get("name")
                try:
                    args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                    
                logger.info("executing_tool", tool=fn_name, args=args)
                
                # Inject state context into tool args where implicitly needed by the old hardcoded logic
                if fn_name == "book_appointment":
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

            # Append the LLM's tool-calling request to the history so it knows what it did
            # To keep it simple, we just inject the results as a system/user observation for the next loop
            conversation_history.append({"role": "user", "content": current_message})
            conversation_history.append({"role": "assistant", "content": "I am checking the calendar now..."})
            
            # The new message is the result of the tool execution
            current_message = "OBSERVATION from tools:\n" + "\n".join(tool_results_content) + "\nNow continue the conversation based on this information."

        except Exception as exc:
            logger.error("scheduling_agent_error", error=str(exc), exc_info=exc)
            return {
                **state,
                "response_text": "I apologize, I'm having trouble accessing the calendar right now.",
                "error": f"Scheduling agent error: {exc}",
            }

    # If we exit the loop without returning, it means we hit max loops
    return {
        **state,
        "response_text": "I'm still checking the calendar. Let me get back to you shortly.",
        "response_voice": state.get("input_modality") == "voice",
    }
