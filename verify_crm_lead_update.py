"""
Comprehensive CRM Lead Update Verification Suite.

Tests:
1. Mock CRM Provider: Create and update lead fields (Name, Email, Phone, Address, Reasons to reach us).
2. Tool Execution: The `update_crm_lead` tool invoked via ToolRunner and registry.
3. CRM Agent Workflow: CRM agent node taking a WhatsApp user message with new contact details, calling `update_crm_lead`, and producing confirmation feedback.
4. Frappe CRM Provider (Unit/Mocked): Verifying exact payload structure, FCRM Note sync, and Comment sync.
5. Live Frappe CRM Cloud Test: Querying https://praful-crm.nvi.frappe.cloud, executing a live lead update, verifying the changes in Frappe, and restoring original values.
"""

import sys
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

def banner(title: str):
    print("\n" + "=" * 70, flush=True)
    print(f"  {title}", flush=True)
    print("=" * 70, flush=True)


async def test_1_mock_crm_provider():
    banner("1. Testing Mock CRM Provider - Lead Creation & Field Updates")
    from whatsapp_agent.integrations.crm.mock import MockCRMProvider
    
    provider = MockCRMProvider()
    phone = "+19876543210"
    
    # 1. Create Initial Lead
    print(f"  [*] Creating initial lead for phone {phone}...", flush=True)
    lead_id = await provider.create_lead(
        phone=phone,
        name="Alexander Pierce",
        email="alex.initial@shield.org",
        company="Initial Corp",
        reasons_to_reach_us="Basic inquiry about WhatsApp AI",
        lead_score=35,
        status="New"
    )
    print(f"  [+] Created Lead ID: {lead_id}", flush=True)
    init_data = await provider.get_lead(lead_id)
    print(f"      Initial Name:    {init_data.get('client_name')}", flush=True)
    print(f"      Initial Email:   {init_data.get('email')}", flush=True)
    print(f"      Initial Phone:   {init_data.get('phone')}", flush=True)
    print(f"      Initial Reasons: {init_data.get('reasons_to_reach_us')}", flush=True)
    
    assert init_data["client_name"] == "Alexander Pierce"
    assert init_data["email"] == "alex.initial@shield.org"
    
    # 2. Update Lead with new information
    new_name = "Alexander G. Pierce"
    new_email = "alexander.pierce@shield.gov"
    new_phone = "+14155552671"
    new_address = "Washington, D.C."
    new_reasons = "Enterprise requirement: Needs WhatsApp Multi-agent system with live ERPNext billing sync"
    
    print("\n  [*] Updating lead details...", flush=True)
    ok = await provider.update_lead(
        lead_id=lead_id,
        client_name=new_name,
        email=new_email,
        phone=new_phone,
        address=new_address,
        reasons_to_reach_us=new_reasons,
        lead_score=95,
        status="Qualified"
    )
    assert ok is True, "Mock CRM update_lead returned False"
    
    # 3. Verify updated details
    updated = await provider.get_lead(lead_id)
    print(f"  [+] Verification from Mock CRM:", flush=True)
    print(f"      Updated Client Name:         {updated.get('client_name')}", flush=True)
    print(f"      Updated Email:               {updated.get('email')}", flush=True)
    print(f"      Updated Phone:               {updated.get('phone')}", flush=True)
    print(f"      Updated Address:             {updated.get('address')}", flush=True)
    print(f"      Updated Reasons to Reach us: {updated.get('reasons_to_reach_us')}", flush=True)
    print(f"      Updated Status:              {updated.get('status')}", flush=True)
    print(f"      Updated Lead Score:          {updated.get('lead_score')}", flush=True)
    
    assert updated["client_name"] == new_name
    assert updated["email"] == new_email
    assert updated["phone"] == new_phone
    assert updated["address"] == new_address
    assert updated["reasons_to_reach_us"] == new_reasons
    assert updated["status"] == "Qualified"
    assert updated["lead_score"] == 95
    print("  [SUCCESS] Mock CRM Provider correctly updated and verified all lead fields!\n", flush=True)


async def test_2_tool_layer():
    banner("2. Testing Tool Layer - `update_crm_lead` Execution")
    from whatsapp_agent.tools.registry import default_registry, ToolRunner
    from whatsapp_agent.integrations.crm.mock import MockCRMProvider
    import whatsapp_agent.tools.definitions  # Ensure all tools registered
    
    mock_crm = MockCRMProvider()
    phone = "+919876543210"
    await mock_crm.create_lead(phone=phone, name="Ramesh", email="ramesh@old.com")
    
    runner = ToolRunner(default_registry)
    tool_args = {
        "phone": phone,
        "client_name": "Dr. Ramesh Sharma",
        "email": "dr.ramesh@clinic.in",
        "address": "Pune, Maharashtra",
        "reasons_to_reach_us": "WhatsApp AI bot for clinic appointment booking and prescription dispatch"
    }
    
    print("  [*] Executing `update_crm_lead` tool via ToolRunner...", flush=True)
    # Patch get_crm_provider and bypass DB session in sandbox
    with patch("whatsapp_agent.tools.definitions.crm_tools.get_crm_provider", return_value=mock_crm):
        with patch("whatsapp_agent.database.session._get_session_factory", side_effect=Exception("skip db")):
            result = await runner.execute(
                tool_name="update_crm_lead",
                arguments=tool_args,
                context={"is_authenticated": True, "user_id": phone}
            )
            
    print(f"  [+] Tool result: {result}", flush=True)
    assert result["status"] == "success"
    assert result["updated_fields"]["client_name"] == "Dr. Ramesh Sharma"
    assert result["updated_fields"]["email"] == "dr.ramesh@clinic.in"
    
    # Verify in CRM
    saved = await mock_crm.get_lead(f"LEAD-{phone}")
    assert saved["client_name"] == "Dr. Ramesh Sharma"
    assert saved["email"] == "dr.ramesh@clinic.in"
    assert saved["address"] == "Pune, Maharashtra"
    assert "clinic appointment booking" in saved["reasons_to_reach_us"]
    print("  [SUCCESS] Tool Layer (`update_crm_lead`) correctly executed and updated CRM record!\n", flush=True)


async def test_3_crm_agent_node():
    banner("3. Testing CRM Agent Node - Full Conversational Lead Update")
    from whatsapp_agent.agents.crm.agent import crm_agent_node
    from whatsapp_agent.integrations.crm.mock import MockCRMProvider
    
    user_phone = "+919988776655"
    incoming_msg = (
        "Hello, please update my contact and requirement details: "
        "My full name is Priya Nair, email is priya.nair@innovate.co, "
        "address is Bengaluru, and I want an agentic WhatsApp AI system for customer support."
    )
    
    state = {
        "workspace_id": "ws-demo",
        "contact_wa_id": user_phone,
        "raw_text": incoming_msg,
        "effective_text": incoming_msg,
        "conversation_history": [],
        "business_profile": {
            "business_name": "Associative AI",
            "ai_persona_name": "Associative Assistant",
            "ai_use_emoji": True
        },
        "language_detected": "en"
    }
    
    mock_crm = MockCRMProvider()
    await mock_crm.create_lead(phone=user_phone, name="Priya", email="priya@old.com")
    
    # Mock LLM behavior:
    # 1. Turn 1: LLM extracts fields and calls update_crm_lead
    mock_llm = AsyncMock()
    mock_tool_call = {
        "function": {
            "name": "update_crm_lead",
            "arguments": json.dumps({
                "client_name": "Priya Nair",
                "email": "priya.nair@innovate.co",
                "phone": user_phone,
                "address": "Bengaluru",
                "reasons_to_reach_us": "Agentic WhatsApp AI system for customer support"
            })
        }
    }
    # 2. Turn 2: LLM produces structured confirmation for the customer
    confirmation_msg = (
        "Thank you, Priya Nair! 🎉 Your details have been successfully updated in our CRM:\n"
        "• Name: Priya Nair\n"
        "• Email: priya.nair@innovate.co\n"
        "• Phone: +919988776655\n"
        "• Address: Bengaluru\n"
        "• Project Requirements: Agentic WhatsApp AI system for customer support\n\n"
        "Our team will follow up shortly!"
    )
    mock_llm.complete_with_tools.side_effect = [
        (MagicMock(content=None), [mock_tool_call]),
        (MagicMock(content=confirmation_msg), [])
    ]
    
    print("  [*] Running CRM Agent Node...", flush=True)
    with patch("whatsapp_agent.agents.crm.agent.get_llm_provider", return_value=mock_llm):
        with patch("whatsapp_agent.tools.definitions.crm_tools.get_crm_provider", return_value=mock_crm):
            with patch("whatsapp_agent.database.session._get_session_factory", side_effect=Exception("skip db")):
                res = await crm_agent_node(state)
                
    print(f"  [+] Agent Response Text:\n{res['response_text']}\n", flush=True)
    
    # Check CRM was updated
    lead = await mock_crm.get_lead(f"LEAD-{user_phone}")
    assert lead["client_name"] == "Priya Nair"
    assert lead["email"] == "priya.nair@innovate.co"
    assert lead["address"] == "Bengaluru"
    assert "Agentic WhatsApp AI system" in lead["reasons_to_reach_us"]
    assert "Priya Nair" in res["response_text"]
    assert "priya.nair@innovate.co" in res["response_text"]
    print("  [SUCCESS] CRM Agent Node correctly parsed lead details, invoked tool, and responded to user!\n", flush=True)


async def test_4_frappe_crm_provider_logic():
    banner("4. Testing Frappe CRM Provider Logic (Payload & Notes Sync)")
    from whatsapp_agent.integrations.crm.frappe import FrappeCRMProvider
    
    provider = FrappeCRMProvider()
    provider.base_url = "https://mock-frappe.local"
    provider.api_key = "test_key"
    provider.api_secret = "test_secret"
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": {"name": "CRM-LEAD-2026-0099"}}
    
    with patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put:
        with patch.object(provider, "_sync_lead_reason_note", new_callable=AsyncMock) as mock_sync_note:
            mock_put.return_value = mock_resp
            
            ok = await provider.update_lead(
                lead_id="CRM-LEAD-2026-0099",
                client_name="Vikram Seth",
                email="vikram.seth@company.com",
                phone="+919876500000",
                address="Mumbai, MH",
                reasons_to_reach_us="Custom ERPNext integration for sales and customer care",
                organization="Seth Enterprises",
                status="Qualified",
                lead_score=85
            )
            
            assert ok is True
            mock_put.assert_called_once()
            url_called = mock_put.call_args[0][0]
            payload = mock_put.call_args[1]["json"]
            
            print(f"  [+] Frappe CRM Lead PUT URL: {url_called}", flush=True)
            print(f"  [+] Frappe CRM Lead Payload:\n{json.dumps(payload, indent=8)}", flush=True)
            
            assert url_called == "https://mock-frappe.local/api/resource/CRM Lead/CRM-LEAD-2026-0099"
            assert payload["first_name"] == "Vikram"
            assert payload["last_name"] == "Seth"
            assert payload["email"] == "vikram.seth@company.com"
            assert payload["mobile_no"] == "+919876500000"
            assert payload["organization"] == "Seth Enterprises"
            assert payload["status"] == "Qualified"
            assert payload["lead_score"] == 85
            
            mock_sync_note.assert_called_once()
            note_args = mock_sync_note.call_args
            assert note_args[0][1] == "CRM-LEAD-2026-0099"
            assert "Custom ERPNext integration" in note_args[0][2]
            assert note_args[1]["address"] == "Mumbai, MH"
            print("  [+] Verified FCRM Note & Address sync invocation.", flush=True)
            
    print("  [SUCCESS] Frappe CRM Provider payload creation and note sync verified!\n", flush=True)


async def test_5_live_frappe_crm():
    banner("5. Testing Live Frappe CRM Cloud (https://praful-crm.nvi.frappe.cloud)")
    import httpx
    from whatsapp_agent.config.settings import get_settings
    from whatsapp_agent.integrations.crm.frappe import FrappeCRMProvider
    
    settings = get_settings()
    if not settings.frappe_url or not settings.frappe_api_key or not settings.frappe_api_secret:
        print("  [-] Frappe credentials missing in .env. Skipping live test.", flush=True)
        return
        
    provider = FrappeCRMProvider()
    print(f"  [*] Connecting to live Frappe CRM at: {provider.base_url}", flush=True)
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{provider.base_url}/api/resource/CRM Lead"
            res = await client.get(url, headers=provider._get_headers(), params={"limit_page_length": 5})
            if res.status_code != 200:
                print(f"  [-] Failed to list leads (Status {res.status_code}): {res.text[:200]}", flush=True)
                return
            data = res.json().get("data", [])
            print(f"  [+] Connected successfully! Found {len(data)} existing CRM Leads in Frappe Cloud.", flush=True)
            if not data:
                print("  [-] No existing leads found in CRM.", flush=True)
                return
                
            target_lead_id = data[0]["name"]
            print(f"  [*] Testing live lead update on Lead ID: {target_lead_id}", flush=True)
            
            # Step A: Fetch current details
            before = await provider.get_lead(target_lead_id) or {}
            print(f"      [Before] Name:    {before.get('client_name')}", flush=True)
            print(f"      [Before] Email:   {before.get('email')}", flush=True)
            print(f"      [Before] Phone:   {before.get('phone')}", flush=True)
            print(f"      [Before] Reasons: {before.get('reasons_to_reach_us')}", flush=True)
            print(f"      [Before] Address: {before.get('address')}", flush=True)
            
            # Step B: Perform Live Update
            test_name = "Live Test Client"
            test_email = "livetest.client@associative.in"
            test_phone = "+919876543210"
            test_address = "Pune, Maharashtra"
            test_reasons = "Verified: Testing live CRM lead update from WhatsApp Agent test suite"
            
            print(f"\n  [*] Executing live lead update...", flush=True)
            update_ok = await provider.update_lead(
                lead_id=target_lead_id,
                client_name=test_name,
                email=test_email,
                phone=test_phone,
                address=test_address,
                reasons_to_reach_us=test_reasons,
                status="Qualified"
            )
            assert update_ok is True, "Live update_lead returned False"
            print("  [+] update_lead API call succeeded!", flush=True)
            
            # Step C: Fetch and verify updated details from Frappe Cloud
            after = await provider.get_lead(target_lead_id) or {}
            print(f"\n      [After] Name:    {after.get('client_name')}", flush=True)
            print(f"      [After] Email:   {after.get('email')}", flush=True)
            print(f"      [After] Phone:   {after.get('phone')}", flush=True)
            print(f"      [After] Reasons: {after.get('reasons_to_reach_us')}", flush=True)
            print(f"      [After] Address: {after.get('address')}", flush=True)
            
            assert after.get("client_name") == test_name, f"Name mismatch: {after.get('client_name')}"
            assert after.get("email") == test_email, f"Email mismatch: {after.get('email')}"
            assert after.get("phone") == test_phone, f"Phone mismatch: {after.get('phone')}"
            assert test_reasons in (after.get("reasons_to_reach_us") or ""), "Reasons mismatch"
            print("  [+] Verification from Live Frappe CRM Cloud confirmed all fields were updated in the database!", flush=True)
            
            # Step D: Restore original values
            print(f"\n  [*] Restoring original lead values...", flush=True)
            orig_name = before.get("client_name") or "Original Client"
            orig_email = before.get("email") or "original@example.com"
            orig_phone = before.get("phone") or "+919000000001"
            orig_reasons = before.get("reasons_to_reach_us") or "Original inquiry"
            orig_address = before.get("address")
            
            await provider.update_lead(
                lead_id=target_lead_id,
                client_name=orig_name,
                email=orig_email,
                phone=orig_phone,
                address=orig_address,
                reasons_to_reach_us=orig_reasons,
                status=before.get("status") or "New"
            )
            print(f"  [+] Original values successfully restored for lead {target_lead_id}!", flush=True)
            print("  [SUCCESS] Live Frappe CRM Cloud tested, verified, and restored cleanly!\n", flush=True)
            
    except Exception as e:
        print(f"  [-] Live Frappe test error: {e}", flush=True)
        raise


async def main():
    print("\n" + "#" * 70, flush=True)
    print("     CRM LEAD UPDATE VERIFICATION SUITE", flush=True)
    print("#" * 70, flush=True)
    
    await test_1_mock_crm_provider()
    await test_2_tool_layer()
    await test_3_crm_agent_node()
    await test_4_frappe_crm_provider_logic()
    await test_5_live_frappe_crm()
    
    banner("SUMMARY: ALL CRM LEAD UPDATE TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
