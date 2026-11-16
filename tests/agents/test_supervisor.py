import pytest
from unittest.mock import AsyncMock, patch
from whatsapp_agent.agents.supervisor.agent import supervisor_node

@pytest.fixture
def mock_llm_provider():
    with patch("whatsapp_agent.agents.supervisor.agent.get_llm_provider") as mock_get:
        mock_llm = AsyncMock()
        mock_get.return_value = mock_llm
        yield mock_llm

@pytest.mark.asyncio
async def test_supervisor_routes_to_sales(mock_llm_provider):
    """Test that supervisor routes sales queries correctly."""
    mock_llm_provider.complete_json.return_value = ({"intent": "purchase"}, AsyncMock(prompt_tokens=10, completion_tokens=10))
    state = {
        "raw_text": "I want to buy your premium plan, how much is it?",
        "effective_text": "I want to buy your premium plan, how much is it?",
        "conversation_history": [],
    }
    
    result = await supervisor_node(state)
    assert result["routed_to_agent"] == "sales"

@pytest.mark.asyncio
async def test_supervisor_routes_to_scheduling(mock_llm_provider):
    """Test that supervisor routes scheduling queries correctly."""
    mock_llm_provider.complete_json.return_value = ({"intent": "scheduling"}, AsyncMock(prompt_tokens=10, completion_tokens=10))
    state = {
        "raw_text": "Can I book an appointment for tomorrow at 2pm?",
        "effective_text": "Can I book an appointment for tomorrow at 2pm?",
        "conversation_history": [],
    }
    
    result = await supervisor_node(state)
    assert result["routed_to_agent"] == "scheduling"

@pytest.mark.asyncio
async def test_supervisor_routes_to_crm(mock_llm_provider):
    """Test that supervisor routes support/crm queries correctly."""
    mock_llm_provider.complete_json.return_value = ({"intent": "support"}, AsyncMock(prompt_tokens=10, completion_tokens=10))
    state = {
        "raw_text": "My recent order hasn't arrived. Where is it?",
        "effective_text": "My recent order hasn't arrived. Where is it?",
        "conversation_history": [],
    }
    
    result = await supervisor_node(state)
    assert result["routed_to_agent"] in ["support", "crm"]

@pytest.mark.asyncio
async def test_supervisor_routes_to_human_escalation(mock_llm_provider):
    """Test that supervisor routes human handoff requests correctly."""
    mock_llm_provider.complete_json.return_value = ({"intent": "human_escalation", "escalate_to_human": True}, AsyncMock(prompt_tokens=10, completion_tokens=10))
    state = {
        "raw_text": "I want to talk to a human manager right now!!",
        "effective_text": "I want to talk to a human manager right now!!",
        "conversation_history": [],
    }
    
    result = await supervisor_node(state)
    assert result["routed_to_agent"] == "human_escalation"
    assert result["escalation_required"] is True

@pytest.mark.asyncio
async def test_supervisor_routes_to_media(mock_llm_provider):
    """Test that supervisor routes image analysis correctly."""
    mock_llm_provider.complete_json.return_value = ({"intent": "media_analysis"}, AsyncMock(prompt_tokens=10, completion_tokens=10))
    state = {
        "raw_text": "What is this?",
        "effective_text": "What is this?",
        "image_analysis": "<IMAGE_DESCRIPTION>A picture of a dog</IMAGE_DESCRIPTION>",
        "conversation_history": [],
    }
    
    result = await supervisor_node(state)
    assert result["routed_to_agent"] == "media"


@pytest.mark.asyncio
async def test_supervisor_routes_lead_capture_to_crm(mock_llm_provider):
    """Test that supervisor routes project development / lead capture to CRM agent."""
    mock_llm_provider.complete_json.return_value = ({"intent": "lead_capture"}, AsyncMock(prompt_tokens=10, completion_tokens=10))
    state = {
        "raw_text": "I want to build an eCommerce app and custom CRM for my retail store.",
        "effective_text": "I want to build an eCommerce app and custom CRM for my retail store.",
        "conversation_history": [],
    }

    result = await supervisor_node(state)
    assert result["routed_to_agent"] == "crm"


@pytest.mark.asyncio
async def test_supervisor_continuity_scheduling_confirmation(mock_llm_provider):
    """Test that supervisor preserves scheduling intent on follow-up confirmation like 'yes'."""
    mock_llm_provider.complete_json.return_value = ({"intent": "scheduling"}, AsyncMock(prompt_tokens=10, completion_tokens=10))
    state = {
        "raw_text": "yes",
        "effective_text": "yes",
        "conversation_history": [
            {"role": "user", "content": "can you book my appointment tomarow 1 pm"},
            {"role": "assistant", "content": "Could you please confirm the date for the appointment? Would you like to schedule it for tomorrow, October 15, 2026?"}
        ],
    }

    result = await supervisor_node(state)
    assert result["routed_to_agent"] == "scheduling"
    assert result["intent"] == "scheduling"

