import pytest

from whatsapp_agent.workflows.main_workflow import get_workflow
from whatsapp_agent.config.settings import get_settings, LLMProvider
from whatsapp_agent.agents.state import AgentState

@pytest.fixture(autouse=True)
def setup_mock_env():
    settings = get_settings()
    settings.llm_provider = "mock"  # Forces MockLLMProvider
    
    # Also we don't want send_response_node to actually call WhatsApp API.
    # It uses WhatsAppProvider.MOCK by default in tests due to settings,
    # but we can just let it run. Mock provider will just log.
    settings.whatsapp_provider = "mock"

@pytest.mark.asyncio
async def test_knowledge_qa_flow():
    """
    E2E Scenario 1: Knowledge Q&A
    Tests that a webhook input is routed by the Supervisor to the Knowledge Agent,
    which generates a grounded response.
    """
    workflow = get_workflow()
    
    initial_state: AgentState = {
        "workspace_id": "test-workspace-123",
        "message_id": "msg-123",
        "contact_wa_id": "1234567890",
        "raw_text": "What are your business hours?",
        "effective_text": "What are your business hours?",
        "input_modality": "text",
        "conversation_history": [],
    }
    
    # Run the compiled LangGraph workflow
    result = await workflow.ainvoke(initial_state)
    
    # 1. Verify routing correctly identified 'inquiry' intent
    assert result["intent"] == "inquiry"
    assert result["routed_to_agent"] == "knowledge"
    assert result["escalation_required"] is False
    
    # 2. Verify Knowledge Agent generated a response
    assert "mock text response" in result["response_text"].lower()
    
    # 3. Verify the language was detected
    assert result["language_detected"] == "en"
