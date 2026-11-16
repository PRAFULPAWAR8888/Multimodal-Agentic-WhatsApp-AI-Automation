import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from whatsapp_agent.integrations.crm.mock import MockCRMProvider
from whatsapp_agent.integrations.crm.frappe import FrappeCRMProvider
from whatsapp_agent.integrations.crm.hubspot import HubSpotCRMProvider
from whatsapp_agent.database.models.leads import Lead, LeadStatus, LeadIntent
from whatsapp_agent.tools.definitions.lead_tools import upsert_lead_record
from apps.worker.main import sync_lead_to_crm


@pytest.mark.asyncio
async def test_mock_crm_create_and_update_all_lead_fields():
    """Verify MockCRMProvider updates Client Name, Email, Phone, and Reasons to Reach us."""
    provider = MockCRMProvider()
    phone = "+12345678901"
    
    # 1. Create initial lead
    lead_id = await provider.create_lead(
        phone=phone,
        name="John Doe",
        email="john@example.com",
        reasons_to_reach_us="Initial inquiry"
    )
    assert lead_id == f"LEAD-{phone}"
    
    lead_data = await provider.get_lead(lead_id)
    assert lead_data is not None
    assert lead_data["client_name"] == "John Doe"
    assert lead_data["email"] == "john@example.com"
    assert lead_data["phone"] == phone
    assert lead_data["reasons_to_reach_us"] == "Initial inquiry"
    
    # 2. Automatically update all 4 fields
    update_success = await provider.update_lead(
        lead_id=lead_id,
        client_name="Jonathan Edward Doe",
        email="john.updated@company.com",
        phone="+19876543210",
        reasons_to_reach_us="Looking for multimodal WhatsApp bot with CRM automation and calendar booking",
        lead_score=92,
        status="Qualified"
    )
    assert update_success is True
    
    # 3. Verify all 4 fields updated
    updated_lead = await provider.get_lead(lead_id)
    assert updated_lead["client_name"] == "Jonathan Edward Doe"
    assert updated_lead["email"] == "john.updated@company.com"
    assert updated_lead["phone"] == "+19876543210"
    assert updated_lead["reasons_to_reach_us"] == "Looking for multimodal WhatsApp bot with CRM automation and calendar booking"
    assert updated_lead["lead_score"] == 92
    assert updated_lead["status"] == "Qualified"


@pytest.mark.asyncio
async def test_frappe_crm_update_lead_request():
    """Verify FrappeCRMProvider updates Client Name, Email, Phone, and Reasons to Reach us."""
    provider = FrappeCRMProvider()
    provider.base_url = "https://mock-frappe.local"
    provider.api_key = "test_key"
    provider.api_secret = "test_secret"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": {"name": "CRM-LEAD-001", "organization": "Tech Corp"}}

    with patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put:
        with patch.object(provider, "_sync_lead_reason_note", new_callable=AsyncMock) as mock_sync_note:
            mock_put.return_value = mock_response

            success = await provider.update_lead(
                lead_id="CRM-LEAD-001",
                client_name="Alice M. Smith",
                email="alice.smith@techcorp.com",
                phone="+919876543210",
                reasons_to_reach_us="Requires automated lead qualification and ERPNext support ticketing",
                company="Tech Corp",
                lead_score=90,
                status="Qualified"
            )

            assert success is True
            mock_put.assert_called_once()
            args, kwargs = mock_put.call_args
            assert args[0] == "https://mock-frappe.local/api/resource/CRM Lead/CRM-LEAD-001"
            payload = kwargs["json"]
            # Verify Client Name
            assert payload["first_name"] == "Alice"
            assert payload["last_name"] == "M. Smith"
            # Verify Email
            assert payload["email"] == "alice.smith@techcorp.com"
            # Verify Phone
            assert payload["mobile_no"] == "+919876543210"
            assert payload["phone"] == "+919876543210"
            # Verify Reasons to Reach us synced via FCRM Note
            mock_sync_note.assert_called_once()
            assert "Requires automated lead qualification" in mock_sync_note.call_args[0][2]


@pytest.mark.asyncio
async def test_hubspot_crm_update_lead_request():
    """Verify HubSpotCRMProvider updates Client Name, Email, Phone, and Reasons to Reach us."""
    provider = HubSpotCRMProvider()
    provider.base_url = "https://api.hubapi.com"
    provider.access_token = "fake_token"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.patch", new_callable=AsyncMock) as mock_patch:
        mock_patch.return_value = mock_response

        success = await provider.update_lead(
            lead_id="HS-12345",
            client_name="Bob A. Brown",
            email="bob.brown@example.com",
            phone="+14155552671",
            reasons_to_reach_us="Interested in WhatsApp AI bot for sales team",
            company="Global Inc"
        )

        assert success is True
        mock_patch.assert_called_once()
        args, kwargs = mock_patch.call_args
        assert args[0] == "https://api.hubapi.com/crm/v3/objects/contacts/HS-12345"
        properties = kwargs["json"]["properties"]
        # Verify Client Name
        assert properties["firstname"] == "Bob"
        assert properties["lastname"] == "A. Brown"
        # Verify Email
        assert properties["email"] == "bob.brown@example.com"
        # Verify Phone
        assert properties["phone"] == "+14155552671"
        # Verify Reasons to Reach us
        assert properties["message"] == "Interested in WhatsApp AI bot for sales team"


@pytest.mark.asyncio
async def test_upsert_lead_record_updates_existing_lead():
    """Verify upsert_lead_record tool updates existing lead record and enqueues CRM sync."""
    ws_id = str(uuid.uuid4())
    phone = "+15550009999"

    # Mock DB Session & Factory
    existing_lead = None

    class MockSession:
        def __init__(self):
            self.added = []
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def add(self, obj):
            nonlocal existing_lead
            self.added.append(obj)
            existing_lead = obj

        async def commit(self):
            self.committed = True

        async def execute(self, stmt):
            result = MagicMock()
            result.scalars.return_value.first.return_value = existing_lead
            return result

    mock_session = MockSession()
    mock_factory = MagicMock(return_value=mock_session)

    mock_arq_pool = AsyncMock()

    with patch("whatsapp_agent.tools.definitions.lead_tools._get_session_factory", return_value=mock_factory):
        with patch("arq.create_pool", return_value=mock_arq_pool):
            # 1. First call: Inserts new lead
            ok1 = await upsert_lead_record(
                workspace_id=ws_id,
                phone=phone,
                customer_name="Jane Doe",
                qualification_score=40,
                requirement="Looking for WhatsApp AI bot"
            )
            assert ok1 is True
            assert existing_lead is not None
            assert existing_lead.name == "Jane Doe"
            assert existing_lead.lead_score == 40
            assert existing_lead.status == LeadStatus.NEW
            mock_arq_pool.enqueue_job.assert_called_with("sync_lead_to_crm", str(existing_lead.id))

            # 2. Second call: Updates existing lead with new details and higher score
            ok2 = await upsert_lead_record(
                workspace_id=ws_id,
                phone=phone,
                customer_name="Jane Doe",
                email="jane@doe.com",
                company="Doe Enterprises",
                budget="$5,000",
                requirement="Updated: WhatsApp customer care chatbot",
                qualification_score=85
            )
            assert ok2 is True
            assert existing_lead.email == "jane@doe.com"
            assert existing_lead.company == "Doe Enterprises"
            assert existing_lead.budget == "$5,000"
            assert existing_lead.requirement == "Updated: WhatsApp customer care chatbot"
            assert existing_lead.lead_score == 85
            assert existing_lead.status == LeadStatus.QUALIFIED
            # Enqueued sync_lead_to_crm for the same lead ID
            mock_arq_pool.enqueue_job.assert_called_with("sync_lead_to_crm", str(existing_lead.id))


@pytest.mark.asyncio
async def test_worker_sync_lead_to_crm_automatic_update():
    """Verify worker sync_lead_to_crm passes Client Name, Email, Phone, and Reasons to Reach us."""
    lead_uuid = uuid.uuid4()
    mock_lead = Lead(
        id=lead_uuid,
        workspace_id=uuid.uuid4(),
        phone="+12025550188",
        name="Charlie Vance",
        email="charlie@vance.io",
        company="Vance Refrigeration",
        requirement="HVAC maintenance AI bot for WhatsApp",
        lead_score=80,
        status=LeadStatus.QUALIFIED,
        crm_contact_id="CRM-LEAD-2026-00099"  # Already exists in CRM!
    )

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_lead
    mock_session.execute.return_value = result_mock

    mock_factory = MagicMock(return_value=mock_session)
    mock_crm = AsyncMock()
    mock_crm.update_lead.return_value = True

    mock_marketo = AsyncMock()
    mock_marketo.push_lead.return_value = True

    with patch("whatsapp_agent.database.session._get_session_factory", return_value=mock_factory):
        with patch("whatsapp_agent.integrations.crm.factory.get_crm_provider", return_value=mock_crm):
            with patch("whatsapp_agent.integrations.crm.marketo.get_marketo_provider", return_value=mock_marketo):
                await sync_lead_to_crm({}, str(lead_uuid))

                # Verify crm.update_lead was called with all target fields
                mock_crm.update_lead.assert_called_once_with(
                    lead_id="CRM-LEAD-2026-00099",
                    name="Charlie Vance",
                    client_name="Charlie Vance",
                    email="charlie@vance.io",
                    phone="+12025550188",
                    company="Vance Refrigeration",
                    reasons_to_reach_us="HVAC maintenance AI bot for WhatsApp",
                    requirement="HVAC maintenance AI bot for WhatsApp",
                    lead_score=80,
                    status="Qualified"
                )
                mock_crm.create_lead.assert_not_called()

                # Verify timestamps and commit
                assert mock_lead.crm_synced_at is not None
                mock_session.commit.assert_called_once()

                # Verify Marketo score sync
                mock_marketo.push_lead.assert_called_once_with(
                    email="charlie@vance.io",
                    first_name="Charlie Vance",
                    phone="+12025550188",
                    behavior_score=80
                )


@pytest.mark.asyncio
async def test_lead_agent_triggers_lead_auto_update():
    """Verify lead agent analyzes conversational update, extracts info, and triggers upsert."""
    from whatsapp_agent.agents.lead.agent import lead_agent_node
    from whatsapp_agent.agents.llm_provider import LLMUsage

    mock_llm = AsyncMock()
    mock_llm.complete_json.return_value = (
        {
            "customer_name": "Sarah Connor",
            "company": "Cyberdyne Systems",
            "email": "sarah@cyberdyne.com",
            "budget": "$50,000",
            "requirement": "Enterprise security AI integration",
            "qualification_score": 95,
            "is_lead": True,
            "response_message": "Thank you Sarah, our enterprise team will reach out to Cyberdyne Systems shortly."
        },
        LLMUsage(prompt_tokens=45, completion_tokens=30, total_tokens=75)
    )

    ws_id = str(uuid.uuid4())
    state = {
        "workspace_id": ws_id,
        "contact_wa_id": "+13105550199",
        "raw_text": "Hi, I am Sarah from Cyberdyne Systems. My email is sarah@cyberdyne.com and budget is $50k.",
        "effective_text": "Hi, I am Sarah from Cyberdyne Systems. My email is sarah@cyberdyne.com and budget is $50k.",
        "conversation_history": [],
        "business_profile": {"ai_persona_name": "SalesBot", "business_name": "Tech Corp"}
    }

    with patch("whatsapp_agent.agents.lead.agent.get_llm_provider", return_value=mock_llm):
        with patch("whatsapp_agent.tools.registry.ToolRunner.execute", new_callable=AsyncMock) as mock_execute:
            res = await lead_agent_node(state)
            
            assert "Thank you Sarah" in res["response_text"]
            mock_execute.assert_called_once()
            call_kwargs = mock_execute.call_args.kwargs
            assert call_kwargs["tool_name"] == "upsert_lead_record"
            args = call_kwargs["arguments"]
            assert args["workspace_id"] == ws_id
            assert args["phone"] == "+13105550199"
            assert args["customer_name"] == "Sarah Connor"
            assert args["company"] == "Cyberdyne Systems"
            assert args["email"] == "sarah@cyberdyne.com"
            assert args["budget"] == "$50,000"
            assert args["requirement"] == "Enterprise security AI integration"
            assert args["qualification_score"] == 95
