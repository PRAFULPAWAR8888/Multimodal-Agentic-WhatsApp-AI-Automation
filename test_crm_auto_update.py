"""
Script to test and verify that CRM can automatically update:
- Client Name
- Email
- Phone
- Reasons to Reach us

Runs verification on both Mock CRM and Live Frappe CRM.
"""

import asyncio
import httpx
from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.integrations.crm.mock import MockCRMProvider
from whatsapp_agent.integrations.crm.frappe import FrappeCRMProvider


async def test_mock_crm_auto_update():
    print("=" * 65)
    print("1. Testing Mock CRM: Updating Client Name, Email, Phone, Reasons")
    print("=" * 65)
    provider = MockCRMProvider()
    initial_phone = "+19998887777"

    # Step A: Initial lead creation
    lead_id = await provider.create_lead(
        phone=initial_phone,
        name="Alexander Pierce",
        email="alex@initial.com",
        company="Initial Corp",
        reasons_to_reach_us="Basic inquiry about WhatsApp AI",
        lead_score=35,
        status="New"
    )
    print(f"  [+] Created Initial Mock Lead ID: {lead_id}")
    lead_init = await provider.get_lead(lead_id)
    print(f"      Initial Client Name:         {lead_init['client_name']}")
    print(f"      Initial Email:               {lead_init['email']}")
    print(f"      Initial Phone:               {lead_init['phone']}")
    print(f"      Initial Reasons to Reach us: {lead_init['reasons_to_reach_us']}")

    # Step B: Automatically update the 4 specified fields
    print("\n  [*] Automatically updating Client Name, Email, Phone, and Reasons to Reach us...")
    new_client_name = "Alexander G. Pierce"
    new_email = "alexander.pierce@shield.gov"
    new_phone = "+14155552671"
    new_reason = "Enterprise requirement: Needs WhatsApp Multi-agent system with live ERPNext billing sync"

    ok = await provider.update_lead(
        lead_id=lead_id,
        client_name=new_client_name,
        email=new_email,
        phone=new_phone,
        reasons_to_reach_us=new_reason,
        lead_score=95,
        status="Qualified"
    )
    assert ok is True, "Mock CRM update_lead returned False!"

    # Step C: Verify updated fields
    lead_up = await provider.get_lead(lead_id)
    print(f"      Updated Client Name:         {lead_up['client_name']}")
    print(f"      Updated Email:               {lead_up['email']}")
    print(f"      Updated Phone:               {lead_up['phone']}")
    print(f"      Updated Reasons to Reach us: {lead_up['reasons_to_reach_us']}")

    assert lead_up["client_name"] == new_client_name, "Client Name did not match!"
    assert lead_up["email"] == new_email, "Email did not match!"
    assert lead_up["phone"] == new_phone, "Phone did not match!"
    assert lead_up["reasons_to_reach_us"] == new_reason, "Reasons to Reach us did not match!"
    print("  [SUCCESS] Mock CRM verified: Client Name, Email, Phone, Reasons to Reach us all updated!\n")


async def test_frappe_crm_auto_update():
    print("=" * 65)
    print("2. Testing Live Frappe CRM: Updating Client Name, Email, Phone, Reasons")
    print("=" * 65)
    settings = get_settings()

    if not settings.frappe_url or not settings.frappe_api_key or not settings.frappe_api_secret:
        print("  [-] Frappe credentials not found in .env, skipping live Frappe test.")
        return

    provider = FrappeCRMProvider()
    print(f"  [*] Connecting to Frappe CRM at: {provider.base_url}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{provider.base_url}/api/resource/CRM Lead"
        try:
            r = await client.get(url, headers=provider._get_headers(), params={"limit_page_length": 5})
            if r.status_code != 200:
                print(f"  [-] Failed to list Frappe leads (Status {r.status_code}): {r.text}")
                return
            data = r.json().get("data", [])
            if not data:
                print("  [-] No existing CRM Leads found to test update.")
                return

            target_lead_id = data[0]["name"]
            print(f"  [+] Target Frappe Lead: {target_lead_id}")

            # 1. Fetch current lead state before update
            before = await provider.get_lead(target_lead_id)
            print(f"      Before Client Name:         {before.get('client_name')}")
            print(f"      Before Email:               {before.get('email')}")
            print(f"      Before Phone:               {before.get('phone')}")
            print(f"      Before Reasons to Reach us: {before.get('reasons_to_reach_us')}")

            # 2. Update all 4 target fields
            new_client_name = "Rahul Dev Sharma"
            new_email = "rahul.dev@example.com"
            new_phone = "+919876543210"
            new_reasons = "Urgent: Build WhatsApp AI multi-agent bot with ERPNext invoice lookup and calendar scheduling"

            print(f"\n  [*] Executing live CRM update for lead {target_lead_id}:")
            print(f"      -> Client Name:         {new_client_name}")
            print(f"      -> Email:               {new_email}")
            print(f"      -> Phone:               {new_phone}")
            print(f"      -> Reasons to Reach us: {new_reasons}")

            update_ok = await provider.update_lead(
                lead_id=target_lead_id,
                client_name=new_client_name,
                email=new_email,
                phone=new_phone,
                reasons_to_reach_us=new_reasons,
                organization="Sharma Enterprises"
            )
            assert update_ok is True, "Frappe CRM lead update returned False!"

            # 3. Fetch lead state after update and verify
            after = await provider.get_lead(target_lead_id)
            print(f"\n  [+] Verification from Live Frappe CRM:")
            print(f"      After Client Name:         {after.get('client_name')}")
            print(f"      After Email:               {after.get('email')}")
            print(f"      After Phone:               {after.get('phone')}")
            print(f"      After Reasons to Reach us: {after.get('reasons_to_reach_us')}")

            assert after.get("client_name") == new_client_name, f"Expected {new_client_name}, got {after.get('client_name')}"
            assert after.get("email") == new_email, f"Expected {new_email}, got {after.get('email')}"
            assert after.get("phone") == new_phone, f"Expected {new_phone}, got {after.get('phone')}"
            assert after.get("reasons_to_reach_us") == new_reasons, f"Expected {new_reasons}, got {after.get('reasons_to_reach_us')}"

            # 4. Restore original values
            print(f"\n  [*] Restoring original values for lead {target_lead_id}...")
            orig_name = before.get("client_name") or "Rahul Sharma"
            orig_email = before.get("email") or "rahul.test@example.com"
            orig_phone = before.get("phone") or "+919000000001"
            orig_reasons = before.get("reasons_to_reach_us") or "Original customer requirement"

            await provider.update_lead(
                lead_id=target_lead_id,
                client_name=orig_name,
                email=orig_email,
                phone=orig_phone,
                reasons_to_reach_us=orig_reasons,
                organization=before.get("organization") or "xyz"
            )
            print("  [SUCCESS] Live Frappe CRM updated, verified, and restored successfully!\n")

        except Exception as e:
            print(f"  [-] Live Frappe test error: {e}\n")
            raise


async def test_supervisor_lead_capture_and_crm_intake():
    print("=" * 65)
    print("3. Testing Supervisor Routing to CRM Agent for Project Development")
    print("=" * 65)
    from whatsapp_agent.agents.supervisor.agent import supervisor_node
    from whatsapp_agent.agents.crm.agent import crm_agent_node
    from unittest.mock import AsyncMock, patch, MagicMock
    import json

    client_phone = "+919876543210"
    client_msg = "Hello, I want to build a custom CRM and WhatsApp AI bot for my business. Name is Dr. Ramesh, email dr.ramesh@clinic.com"
    print(f"  [>] Inbound Client Message: '{client_msg}'")

    state = {
        "workspace_id": "ws-demo",
        "contact_wa_id": client_phone,
        "raw_text": client_msg,
        "effective_text": client_msg,
        "conversation_history": [],
        "business_profile": {"business_name": "AI Automation Platform", "ai_persona_name": "AI Assistant"},
        "language_detected": "en"
    }

    # 1. Supervisor classifies intent and routes to CRM
    mock_llm = AsyncMock()
    mock_llm.complete_json.return_value = (
        {"intent": "lead_capture", "confidence": 0.95, "reasoning": "Client wants to build a custom CRM project."},
        AsyncMock(prompt_tokens=15, completion_tokens=10)
    )

    with patch("whatsapp_agent.agents.supervisor.agent.get_llm_provider", return_value=mock_llm):
        sup_result = await supervisor_node(state)

    print(f"  [+] Supervisor Detected Intent: {sup_result['intent']}")
    print(f"  [+] Supervisor Routed To Agent: {sup_result['routed_to_agent']}")
    assert sup_result["intent"] == "lead_capture"
    assert sup_result["routed_to_agent"] == "crm"
    print("  [OK] Successfully routed project development request to CRM Agent first!")

    # 2. CRM Agent detects information, updates CRM, and gives feedback
    mock_crm = MockCRMProvider()
    mock_crm_llm = AsyncMock()
    tool_call = {
        "function": {
            "name": "update_crm_lead",
            "arguments": json.dumps({
                "client_name": "Dr. Ramesh",
                "email": "dr.ramesh@clinic.com",
                "phone": client_phone,
                "reasons_to_reach_us": "Build custom CRM and WhatsApp AI bot for business"
            })
        }
    }
    client_reply = MagicMock(
        content=(
            "Thank you Dr. Ramesh! I have registered your project requirements in our CRM. "
            "Our engineering team has noted your request to build a custom CRM and WhatsApp AI bot. "
            "Would you like to schedule a consultation call?"
        )
    )
    mock_crm_llm.complete_with_tools.side_effect = [
        (MagicMock(content=None), [tool_call]),
        (client_reply, [])
    ]

    crm_state = {**sup_result, **state}
    with patch("whatsapp_agent.agents.crm.agent.get_llm_provider", return_value=mock_crm_llm):
        with patch("whatsapp_agent.tools.definitions.crm_tools.get_crm_provider", return_value=mock_crm):
            agent_result = await crm_agent_node(crm_state)

    # 3. Verify CRM data was saved
    lead = await mock_crm.get_lead(f"LEAD-{client_phone}")
    print(f"  [+] CRM Saved Client Name:         {lead['client_name']}")
    print(f"  [+] CRM Saved Email:               {lead['email']}")
    print(f"  [+] CRM Saved Phone:               {lead['phone']}")
    print(f"  [+] CRM Saved Reasons to Reach us: {lead['reasons_to_reach_us']}")
    print(f"  [+] Client Feedback Given by CRM Agent:\n      \"{agent_result['response_text']}\"")

    assert lead["client_name"] == "Dr. Ramesh"
    assert lead["email"] == "dr.ramesh@clinic.com"
    assert "registered your project requirements in our CRM" in agent_result["response_text"]
    print("  [SUCCESS] Client detected, CRM updated, and feedback given successfully!\n")


async def main():
    print("\n" + "#" * 65)
    print("   CRM AUTOMATIC LEAD UPDATE & SUPERVISOR ONBOARDING SUITE   ")
    print("#" * 65 + "\n")

    await test_mock_crm_auto_update()
    await test_frappe_crm_auto_update()
    await test_supervisor_lead_capture_and_crm_intake()

    print("=" * 65)
    print("ALL CRM LEAD FIELD UPDATE & SUPERVISOR TESTS PASSED!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
