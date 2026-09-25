import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

from whatsapp_agent.database.models.agents import AgentRun, AgentRunStatus
from whatsapp_agent.database.models.whatsapp import WhatsAppMessage, WhatsAppContact, Modality
from apps.worker.main import run_agent

@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    factory = MagicMock(return_value=session)
    # Support async with
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session, factory

@pytest.mark.asyncio
async def test_run_agent_success():
    """Test that run_agent correctly updates AgentRun status and telemetry on success."""
    run_uuid = uuid.uuid4()
    msg_uuid = uuid.uuid4()
    contact_uuid = uuid.uuid4()
    
    # Mock models
    mock_agent_run = AgentRun(
        id=run_uuid,
        workspace_id=uuid.uuid4(),
        message_id=msg_uuid,
        status=AgentRunStatus.PENDING
    )
    
    mock_message = WhatsAppMessage(
        id=msg_uuid,
        contact_id=contact_uuid,
        body="Hello world",
        modality=Modality.TEXT,
    )
    
    mock_contact = WhatsAppContact(
        id=contact_uuid,
        wa_id="1234567890",
    )
    
    # We need to mock the db.execute to return these models sequentially
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    
    def mock_execute_side_effect(stmt):
        result_mock = MagicMock()
        # Very rough mocking based on string representation of the statement
        stmt_str = str(stmt).lower()
        if "agent_runs" in stmt_str:
            result_mock.scalar_one_or_none.return_value = mock_agent_run
        elif "whatsapp_messages" in stmt_str:
            result_mock.scalar_one_or_none.return_value = mock_message
        elif "whatsapp_contacts" in stmt_str:
            result_mock.scalar_one_or_none.return_value = mock_contact
        else:
            result_mock.scalar_one_or_none.return_value = None
        return result_mock

    session.execute.side_effect = mock_execute_side_effect

    factory_mock = MagicMock(return_value=session)

    # Patch the factory and workflow
    with patch("apps.worker.main._get_session_factory", return_value=factory_mock):
        with patch("apps.worker.main.get_workflow") as mock_get_workflow:
            mock_workflow = AsyncMock()
            mock_workflow.ainvoke.return_value = {
                "intent": "inquiry",
                "confidence_score": 0.95,
                "escalation_required": False,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "model_latency_ms": 150
            }
            mock_get_workflow.return_value = mock_workflow
            
            # Execute
            await run_agent({}, str(run_uuid))
            
            # Verify Workflow was called
            mock_workflow.ainvoke.assert_called_once()
            
            # Verify AgentRun was updated
            assert mock_agent_run.status == AgentRunStatus.COMPLETED
            assert mock_agent_run.intent_detected == "inquiry"
            assert mock_agent_run.confidence_score == 0.95
            assert mock_agent_run.prompt_tokens == 100
            assert mock_agent_run.completion_tokens == 50
            assert mock_agent_run.model_latency_ms == 150
            assert mock_agent_run.total_latency_ms > 0
            assert mock_agent_run.completed_at is not None

@pytest.mark.asyncio
async def test_run_agent_failure():
    """Test that run_agent correctly handles and records failures."""
    run_uuid = uuid.uuid4()
    msg_uuid = uuid.uuid4()
    
    # Mock models
    mock_agent_run = AgentRun(
        id=run_uuid,
        workspace_id=uuid.uuid4(),
        message_id=msg_uuid,
        status=AgentRunStatus.PENDING
    )
    
    mock_message = WhatsAppMessage(
        id=msg_uuid,
        contact_id=uuid.uuid4(),
        body="Fail me",
        modality=Modality.TEXT,
    )
    
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    
    def mock_execute_side_effect(stmt):
        result_mock = MagicMock()
        stmt_str = str(stmt).lower()
        if "agent_runs" in stmt_str:
            result_mock.scalar_one_or_none.return_value = mock_agent_run
        elif "whatsapp_messages" in stmt_str:
            result_mock.scalar_one_or_none.return_value = mock_message
        else:
            result_mock.scalar_one_or_none.return_value = None
        return result_mock

    session.execute.side_effect = mock_execute_side_effect
    factory_mock = MagicMock(return_value=session)

    with patch("apps.worker.main._get_session_factory", return_value=factory_mock):
        with patch("apps.worker.main.get_workflow") as mock_get_workflow:
            mock_workflow = AsyncMock()
            mock_workflow.ainvoke.side_effect = ValueError("Graph execution failed")
            mock_get_workflow.return_value = mock_workflow
            
            # Execute
            await run_agent({}, str(run_uuid))
            
            # Verify AgentRun was updated to FAILED
            assert mock_agent_run.status == AgentRunStatus.FAILED
            assert mock_agent_run.error_message == "Graph execution failed"
            assert mock_agent_run.completed_at is not None
