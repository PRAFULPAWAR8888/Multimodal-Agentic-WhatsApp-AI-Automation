import pytest

from whatsapp_agent.agents.supervisor.agent import supervisor_router


@pytest.mark.asyncio
async def test_supervisor_routes_to_sales():
    """Test that supervisor routes sales queries correctly."""
    state = {
        "raw_text": "I want to buy your premium plan, how much is it?",
        "effective_text": "I want to buy your premium plan, how much is it?",
        "conversation_history": [],
    }
    
    result = await supervisor_router(state)
    assert result["next_agent"] == "sales_agent"


@pytest.mark.asyncio
async def test_supervisor_routes_to_scheduling():
    """Test that supervisor routes scheduling queries correctly."""
    state = {
        "raw_text": "Can I book an appointment for tomorrow at 2pm?",
        "effective_text": "Can I book an appointment for tomorrow at 2pm?",
        "conversation_history": [],
    }
    
    result = await supervisor_router(state)
    assert result["next_agent"] == "scheduling_agent"


@pytest.mark.asyncio
async def test_supervisor_routes_to_crm():
    """Test that supervisor routes support/crm queries correctly."""
    state = {
        "raw_text": "My recent order hasn't arrived. Where is it?",
        "effective_text": "My recent order hasn't arrived. Where is it?",
        "conversation_history": [],
    }
    
    result = await supervisor_router(state)
    # Could route to support or crm, depending on the LLM's interpretation
    assert result["next_agent"] in ["support_agent", "crm_agent"]


@pytest.mark.asyncio
async def test_supervisor_routes_to_human_escalation():
    """Test that supervisor routes human handoff requests correctly."""
    state = {
        "raw_text": "I want to talk to a human manager right now!!",
        "effective_text": "I want to talk to a human manager right now!!",
        "conversation_history": [],
    }
    
    result = await supervisor_router(state)
    assert result["next_agent"] == "human_escalation_agent"


@pytest.mark.asyncio
async def test_supervisor_routes_to_media():
    """Test that supervisor routes image analysis correctly."""
    state = {
        "raw_text": "What is this?",
        "effective_text": "What is this?",
        "image_analysis": "<IMAGE_DESCRIPTION>A picture of a dog</IMAGE_DESCRIPTION>",
        "conversation_history": [],
    }
    
    result = await supervisor_router(state)
    assert result["next_agent"] == "media_agent"
