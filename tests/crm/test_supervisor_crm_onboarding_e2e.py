import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from whatsapp_agent.agents.supervisor.agent import supervisor_node
from whatsapp_agent.agents.crm.agent import crm_agent_node
from whatsapp_agent.integrations.crm.mock import MockCRMProvider


@pytest.mark.asyncio
async def test_supervisor_routes_to_crm_for_project_development_and_updates():
    """
    End-to-end test verifying:
    1. A client wanting to build/develop a project is detected by Supervisor as lead_capture and routed to CRM Agent.
    2. CRM Agent detects client details (Name, Email, Phone, Reasons to Reach us).
    3. CRM Agent updates CRM automatically.
    4. CRM Agent provides clear feedback to the client confirming the update.
    5. In the next turn, Supervisor routes to the next appropriate agent (e.g. scheduling).
    """
    # ── Turn 1: Client wants to build a project ───────────────────────────────
    client_phone = "+919876500000"
    turn_1_message = (
        "Hi, I want to develop an AI WhatsApp chatbot with ERPNext integration for my clinic. "
        "My name is Dr. Ramesh, email is dr.ramesh@clinic.com."
    )

    state_turn_1 = {
        "workspace_id": "ws-e2e-test",
        "contact_wa_id": client_phone,
        "raw_text": turn_1_message,
        "effective_text": turn_1_message,
        "conversation_history": [],
        "business_profile": {
            "business_name": "NextGen AI Solutions",
            "ai_persona_name": "NextGen Assistant",
            "ai_use_emoji": True,
        },
        "language_detected": "en"
    }

    # Supervisor analysis for Turn 1
    mock_supervisor_llm = AsyncMock()
    mock_supervisor_llm.complete_json.return_value = (
        {
            "intent": "lead_capture",
            "confidence": 0.95,
            "reasoning": "Client wants to build/develop an AI WhatsApp chatbot project.",
            "escalate_to_human": False,
            "language": "English"
        },
        AsyncMock(prompt_tokens=20, completion_tokens=15)
    )

    with patch("whatsapp_agent.agents.supervisor.agent.get_llm_provider", return_value=mock_supervisor_llm):
        supervisor_result = await supervisor_node(state_turn_1)

    # Verify Supervisor routes to CRM Agent first to capture info
    assert supervisor_result["intent"] == "lead_capture"
    assert supervisor_result["routed_to_agent"] == "crm"

    # CRM Agent execution for Turn 1
    mock_crm_provider = MockCRMProvider()

    mock_crm_llm = AsyncMock()
    mock_crm_tool_call = {
        "function": {
            "name": "update_crm_lead",
            "arguments": json.dumps({
                "client_name": "Dr. Ramesh",
                "email": "dr.ramesh@clinic.com",
                "phone": client_phone,
                "reasons_to_reach_us": "Develop an AI WhatsApp chatbot with ERPNext integration for clinic"
            })
        }
    }
    mock_crm_turn_1_reply = MagicMock(
        content=(
            "Thank you Dr. Ramesh! I have registered your project requirements in our CRM. "
            "Our engineering team has noted your request to develop an AI WhatsApp chatbot with ERPNext integration. "
            "Would you like to schedule a quick consultation call to discuss scope and timeline?"
        )
    )
    mock_crm_llm.complete_with_tools.side_effect = [
        (MagicMock(content=None), [mock_crm_tool_call]),
        (mock_crm_turn_1_reply, [])
    ]

    crm_state = {**supervisor_result, **state_turn_1}

    with patch("whatsapp_agent.agents.crm.agent.get_llm_provider", return_value=mock_crm_llm):
        with patch("whatsapp_agent.tools.definitions.crm_tools.get_crm_provider", return_value=mock_crm_provider):
            crm_result = await crm_agent_node(crm_state)

    # Verify CRM was automatically updated with the client's information
    lead_id = f"LEAD-{client_phone}"
    stored_lead = await mock_crm_provider.get_lead(lead_id)
    assert stored_lead is not None
    assert stored_lead["client_name"] == "Dr. Ramesh"
    assert stored_lead["email"] == "dr.ramesh@clinic.com"
    assert stored_lead["phone"] == client_phone
    assert "AI WhatsApp chatbot with ERPNext integration" in stored_lead["reasons_to_reach_us"]

    # Verify Client received feedback confirming the update
    assert "registered your project requirements in our CRM" in crm_result["response_text"]
    assert "Dr. Ramesh" in crm_result["response_text"]

    # ── Turn 2: Client wants to schedule a meeting after onboarding ───────────
    turn_2_message = "Yes, please schedule a consultation call for tomorrow at 3 PM."
    state_turn_2 = {
        "workspace_id": "ws-e2e-test",
        "contact_wa_id": client_phone,
        "raw_text": turn_2_message,
        "effective_text": turn_2_message,
        "conversation_history": [
            {"role": "user", "content": turn_1_message},
            {"role": "assistant", "content": crm_result["response_text"]},
        ],
        "business_profile": {
            "business_name": "NextGen AI Solutions",
            "ai_persona_name": "NextGen Assistant",
        },
        "language_detected": "en"
    }

    mock_supervisor_llm.complete_json.return_value = (
        {
            "intent": "scheduling",
            "confidence": 0.98,
            "reasoning": "Client accepted the offer and wants to schedule a consultation call.",
            "escalate_to_human": False,
            "language": "English"
        },
        AsyncMock(prompt_tokens=30, completion_tokens=15)
    )

    with patch("whatsapp_agent.agents.supervisor.agent.get_llm_provider", return_value=mock_supervisor_llm):
        supervisor_turn_2_result = await supervisor_node(state_turn_2)

    # Verify Supervisor now routes to Scheduling Agent based on conversation context
    assert supervisor_turn_2_result["intent"] == "scheduling"
    assert supervisor_turn_2_result["routed_to_agent"] == "scheduling"


@pytest.mark.asyncio
async def test_crm_agent_5_field_onboarding_and_feedback():
    """
    Test verifying that when a client initially arrives saying they want to develop a project:
    1. The CRM agent requests all 5 fields (Name, Email, Phone, Address, Reason/Scope) in a structured format.
    2. When the client responds with their details, the CRM agent calls update_crm_lead with all 5 fields.
    3. The CRM stores all 5 fields.
    4. The client receives clear confirmation feedback detailing all registered information.
    """
    client_phone = "+919811223344"
    mock_crm_provider = MockCRMProvider()

    # Turn 1: Client says "I want to develop a project"
    state_turn_1 = {
        "workspace_id": "ws-e2e-5field",
        "contact_wa_id": client_phone,
        "raw_text": "I want to develop a project",
        "effective_text": "I want to develop a project",
        "conversation_history": [],
        "business_profile": {
            "business_name": "Associative Tech",
            "ai_persona_name": "Associative Consultant",
            "ai_use_emoji": True,
        },
        "language_detected": "en"
    }

    turn_1_reply_content = (
        "Welcome to Associative Tech! We would be thrilled to help you build and develop your project. 🚀\n\n"
        "To help our technical team understand your scope and prepare the best solution and proposal for you, could you please share a few quick details:\n\n"
        "1. 👤 *Full Name*:\n"
        "2. 📧 *Email Address*:\n"
        "3. 📱 *Phone Number* (or confirm this WhatsApp number):\n"
        "4. 📍 *Address / Location (City or Company)*:\n"
        "5. 📝 *Reason to Reach Us / Project Details* (What specific app, software, or features would you like to build?):\n\n"
        "Once you share these details, our solutions team will review your scope and get in touch with you!"
    )

    mock_llm_turn_1 = AsyncMock()
    mock_llm_turn_1.complete_with_tools.return_value = (
        MagicMock(content=turn_1_reply_content),
        []
    )

    with patch("whatsapp_agent.agents.crm.agent.get_llm_provider", return_value=mock_llm_turn_1):
        with patch("whatsapp_agent.tools.definitions.crm_tools.get_crm_provider", return_value=mock_crm_provider):
            res_turn_1 = await crm_agent_node(state_turn_1)

    # Verify Turn 1 asks for all 5 required fields in proper format
    assert "*Full Name*" in res_turn_1["response_text"]
    assert "*Email Address*" in res_turn_1["response_text"]
    assert "*Phone Number*" in res_turn_1["response_text"]
    assert "*Address / Location" in res_turn_1["response_text"]
    assert "*Reason to Reach Us" in res_turn_1["response_text"]

    # Turn 2: Client provides all 5 details
    turn_2_message = (
        "1. Full Name: Rajesh Sharma\n"
        "2. Email: rajesh@techcorp.in\n"
        "3. Phone: +919811223344\n"
        "4. Address: Hinjewadi, Pune\n"
        "5. Reason: Custom Real Estate CRM portal with WhatsApp notifications"
    )

    state_turn_2 = {
        "workspace_id": "ws-e2e-5field",
        "contact_wa_id": client_phone,
        "raw_text": turn_2_message,
        "effective_text": turn_2_message,
        "conversation_history": [
            {"role": "user", "content": state_turn_1["effective_text"]},
            {"role": "assistant", "content": res_turn_1["response_text"]},
        ],
        "business_profile": {
            "business_name": "Associative Tech",
            "ai_persona_name": "Associative Consultant",
            "ai_use_emoji": True,
        },
        "language_detected": "en"
    }

    mock_crm_tool_call = {
        "function": {
            "name": "update_crm_lead",
            "arguments": json.dumps({
                "client_name": "Rajesh Sharma",
                "email": "rajesh@techcorp.in",
                "phone": "+919811223344",
                "address": "Hinjewadi, Pune",
                "reasons_to_reach_us": "Custom Real Estate CRM portal with WhatsApp notifications"
            })
        }
    }

    turn_2_reply_content = (
        "Thank you, Rajesh Sharma! 🎉 Your project details have been successfully recorded in our system:\n\n"
        "• *Name*: Rajesh Sharma\n"
        "• *Email*: rajesh@techcorp.in\n"
        "• *Phone*: +919811223344\n"
        "• *Address / Location*: Hinjewadi, Pune\n"
        "• *Project Requirements*: Custom Real Estate CRM portal with WhatsApp notifications\n\n"
        "Our technical solutions team is reviewing your requirements. Would you like to schedule a discovery call with our tech lead?"
    )

    mock_llm_turn_2 = AsyncMock()
    mock_llm_turn_2.complete_with_tools.side_effect = [
        (MagicMock(content=None), [mock_crm_tool_call]),
        (MagicMock(content=turn_2_reply_content), [])
    ]

    with patch("whatsapp_agent.agents.crm.agent.get_llm_provider", return_value=mock_llm_turn_2):
        with patch("whatsapp_agent.tools.definitions.crm_tools.get_crm_provider", return_value=mock_crm_provider):
            res_turn_2 = await crm_agent_node(state_turn_2)

    # Verify CRM Lead was updated with all 5 fields
    stored_lead = await mock_crm_provider.get_lead(f"LEAD-{client_phone}")
    assert stored_lead is not None
    assert stored_lead["client_name"] == "Rajesh Sharma"
    assert stored_lead["email"] == "rajesh@techcorp.in"
    assert stored_lead["phone"] == "+919811223344"
    assert stored_lead["address"] == "Hinjewadi, Pune"
    assert stored_lead["reasons_to_reach_us"] == "Custom Real Estate CRM portal with WhatsApp notifications"

    # Verify Client received confirmation feedback
    assert "Rajesh Sharma" in res_turn_2["response_text"]
    assert "rajesh@techcorp.in" in res_turn_2["response_text"]
    assert "Hinjewadi, Pune" in res_turn_2["response_text"]
    assert "successfully recorded" in res_turn_2["response_text"]

