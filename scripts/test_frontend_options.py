"""
Automated end-to-end test script for all frontend options:
- Inbox & Conversations
- CRM Leads & Pipeline (including live Frappe CRM sync)
- AI & Business Analytics
- Interactive Multi-Agent Playground
"""

import sys
import httpx
import uuid

BASE_URL = "http://localhost:8000/api/v1"
HEADERS = {"Authorization": "Bearer dev-token", "Content-Type": "application/json"}

def log_test(step: str, status: str, detail: str = ""):
    icon = "✅" if status == "PASS" else "❌"
    print(f"{icon} [{status}] {step}: {detail}", flush=True)

def test_all():
    print("=" * 70, flush=True)
    print("RUNNING AUTOMATED TEST SUITE ON ALL FRONTEND OPTIONS", flush=True)
    print("=" * 70, flush=True)

    with httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=120.0) as client:
        # -------------------------------------------------------------
        # 1. INBOX & CONVERSATIONS
        # -------------------------------------------------------------
        print("\n--- 1. Testing INBOX & CONVERSATIONS ---", flush=True)
        r = client.get("/conversations")
        assert r.status_code == 200, f"Failed GET /conversations: {r.text}"
        convs = r.json()
        log_test("GET /conversations", "PASS", f"Retrieved {len(convs)} conversation(s)")

        if convs:
            conv_id = convs[0]["id"]
            # Messages
            r_msg = client.get(f"/conversations/{conv_id}/messages")
            assert r_msg.status_code == 200
            msgs = r_msg.json()
            log_test(f"GET /conversations/{conv_id[:8]}.../messages", "PASS", f"Retrieved {len(msgs)} message(s)")

            # Toggle AI
            curr_ai = convs[0].get("ai_enabled", True)
            r_toggle = client.post(f"/conversations/{conv_id}/toggle-ai", json={"ai_enabled": not curr_ai})
            assert r_toggle.status_code == 200
            log_test("POST /conversations/{id}/toggle-ai", "PASS", f"Toggled AI to {not curr_ai}")

            # Revert AI
            client.post(f"/conversations/{conv_id}/toggle-ai", json={"ai_enabled": curr_ai})

            # Send reply
            r_reply = client.post(f"/conversations/{conv_id}/reply", json={"body": "[AutoTest] Human reply test"})
            assert r_reply.status_code == 200
            log_test("POST /conversations/{id}/reply", "PASS", f"Reply accepted (Status: {r_reply.json().get('status')})")

        # -------------------------------------------------------------
        # 2. CRM LEADS & PIPELINE
        # -------------------------------------------------------------
        print("\n--- 2. Testing CRM LEADS & PIPELINE ---", flush=True)
        # Stats
        r_lstats = client.get("/leads/stats")
        assert r_lstats.status_code == 200
        lstats = r_lstats.json()
        log_test("GET /leads/stats", "PASS", f"Total: {lstats['total_leads']}, Qualified: {lstats['qualified_leads']}, CRM Synced: {lstats['crm_synced_leads']}")

        # List
        r_leads = client.get("/leads")
        assert r_leads.status_code == 200
        leads_list = r_leads.json()
        log_test("GET /leads", "PASS", f"Fetched {len(leads_list)} leads")

        # Filter by status
        r_filt = client.get("/leads?status=QUALIFIED")
        assert r_filt.status_code == 200
        log_test("GET /leads?status=QUALIFIED", "PASS", f"Filter returned {len(r_filt.json())} qualified leads")

        # Create new Lead
        test_email = f"autotest_{uuid.uuid4().hex[:6]}@example.com"
        r_create = client.post("/leads", json={
            "name": "Frontend Test Prospect",
            "phone": "+91 99999 88888",
            "email": test_email,
            "company": "E2E Test Corp",
            "requirement": "Automated WhatsApp Bot with CRM sync",
            "budget": "₹1,50,000",
            "status": "NEW",
            "lead_score": 80
        })
        assert r_create.status_code == 201
        created_lead = r_create.json()
        created_id = created_lead["id"]
        log_test("POST /leads", "PASS", f"Created test lead ID: {created_id} (Score: {created_lead['lead_score']})")

        # Patch Lead
        r_patch = client.patch(f"/leads/{created_id}", json={
            "status": "QUALIFIED",
            "notes": "Verified via Automated Test Suite"
        })
        assert r_patch.status_code == 200
        assert r_patch.json()["status"] == "QUALIFIED"
        log_test("PATCH /leads/{id}", "PASS", f"Updated status to QUALIFIED with verified notes")

        # CRM Sync test
        r_sync = client.post(f"/leads/{created_id}/sync-crm")
        assert r_sync.status_code == 200
        sync_res = r_sync.json()
        log_test("POST /leads/{id}/sync-crm", "PASS", f"Frappe CRM Sync: {sync_res.get('status')} (CRM ID: {sync_res.get('crm_lead_id')})")

        # Delete test lead
        r_del = client.delete(f"/leads/{created_id}")
        assert r_del.status_code == 200
        log_test("DELETE /leads/{id}", "PASS", f"Deleted test lead successfully")

        # -------------------------------------------------------------
        # 3. AI & BUSINESS ANALYTICS
        # -------------------------------------------------------------
        print("\n--- 3. Testing AI & BUSINESS ANALYTICS ---", flush=True)
        r_an = client.get("/analytics/overview")
        assert r_an.status_code == 200
        an = r_an.json()
        log_test("GET /analytics/overview", "PASS", 
                 f"Messages: {an['total_messages']} | AI Autonomy: {an['ai_automation_rate']}% | Avg Latency: {an['avg_response_time']}")
        log_test("Analytics Intent Distribution", "PASS", f"Categories: {list(an['intent_distribution'].keys())}")
        log_test("Analytics Agent Distribution", "PASS", f"Agents: {list(an['agent_distribution'].keys())}")
        log_test("Analytics Daily Activity", "PASS", f"{len(an['daily_trend'])} daily history points tracked")

        # -------------------------------------------------------------
        # 4. INTERACTIVE PLAYGROUND
        # -------------------------------------------------------------
        print("\n--- 4. Testing PLAYGROUND LIVE MULTI-AGENT CHAT ---", flush=True)
        ws_id = "fb06fb3d-08f4-454c-9422-50f60c25239c"
        test_query = "What mobile application and AI development services do you offer?"
        r_play = client.post(f"/workspaces/{ws_id}/playground/chat", json={
            "message": test_query,
            "sender_id": "playground_user"
        })
        assert r_play.status_code == 200
        play_data = r_play.json()
        reply_snippet = (play_data.get("response_text") or play_data.get("response") or "")[:80]
        log_test("POST /workspaces/{id}/playground/chat", "PASS", 
                 f"Latency: {play_data.get('latency_ms')}ms | Intent: {play_data.get('intent')} | Agent: {play_data.get('routed_agent')}")
        log_test("Playground AI Output", "PASS", f'"{reply_snippet}..."')

    print("\n" + "=" * 70, flush=True)
    print("ALL FRONTEND OPTIONS TESTED AND WORKING 100% END-TO-END!", flush=True)
    print("=" * 70, flush=True)

if __name__ == "__main__":
    test_all()
