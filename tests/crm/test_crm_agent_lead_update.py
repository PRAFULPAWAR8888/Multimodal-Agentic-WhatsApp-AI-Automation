import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from whatsapp_agent.agents.crm.agent import crm_agent_node


@pytest.mark.asyncio
async def test_crm_agent_updates_lead_fields():
    """
    Test that the CRM Agent handles customer requests to update:
    - Client Name
    - Email
    - Phone
    - Reasons to Reach us
    using the update_crm_lead tool.
    """
    state = {
        "workspace_id": "ws-12345",
        "contact_wa_id": "+13105550199",
        "raw_text": (
            "Hi, please update my information: My name is Sarah Connor, "
            "email is sarah@sky.net, phone is +13105550199, and the reason "
            "I'm reaching out is to build an automated AI WhatsApp agent."
        ),
        "effective_text": (
            "Hi, please update my information: My name is Sarah Connor, "
            "email is sarah@sky.net, phone is +13105550199, and the reason "
            "I'm reaching out is to build an automated AI WhatsApp agent."
        ),
        "conversation_history": [],
        "business_profile": {
            "business_name": "AI Automation Corp",
            "ai_persona_name": "SupportBot",
            "ai_use_emoji": True,
        },
        "language_detected": "en"
    }

    mock_llm = AsyncMock()

    # Turn 1: LLM decides to call update_crm_lead tool
    mock_tool_call = {
        "function": {
            "name": "update_crm_lead",
            "arguments": json.dumps({
                "client_name": "Sarah Connor",
                "email": "sarah@sky.net",
                "phone": "+13105550199",
                "reasons_to_reach_us": "Build an automated AI WhatsApp agent"
            })
        }
    }
    mock_llm_response_1 = MagicMock(content=None)

    # Turn 2: LLM receives tool execution observation and sends polite confirmation to user
    mock_llm_response_2 = MagicMock(
        content=(
            "I have successfully updated your details in our CRM! "
            "Name: Sarah Connor, Email: sarah@sky.net, Phone: +13105550199, "
            "and Reason: Build an automated AI WhatsApp agent."
        )
    )

    mock_llm.complete_with_tools.side_effect = [
        (mock_llm_response_1, [mock_tool_call]),
        (mock_llm_response_2, [])
    ]

    mock_runner = AsyncMock()
    mock_runner.execute.return_value = True

    with patch("whatsapp_agent.agents.crm.agent.get_llm_provider", return_value=mock_llm):
        with patch("whatsapp_agent.agents.crm.agent.ToolRunner.execute", new_callable=AsyncMock) as mock_tool_exec:
            mock_tool_exec.return_value = True

            result = await crm_agent_node(state)

            # 1. Verify Tool execution was triggered with all 4 required fields
            mock_tool_exec.assert_called_once()
            call_kwargs = mock_tool_exec.call_args.kwargs
            assert call_kwargs["tool_name"] == "update_crm_lead"
            
            tool_args = call_kwargs["arguments"]
            assert tool_args["client_name"] == "Sarah Connor"
            assert tool_args["email"] == "sarah@sky.net"
            assert tool_args["phone"] == "+13105550199"
            assert tool_args["reasons_to_reach_us"] == "Build an automated AI WhatsApp agent"

            # 2. Verify Agent output response
            assert "successfully updated your details" in result["response_text"]
            assert "Sarah Connor" in result["response_text"]
