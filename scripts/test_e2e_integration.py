import asyncio
import sys
import httpx
from apps.api.main import app
from whatsapp_agent.database.engine import init_db, close_db

async def run_e2e_tests():
    print("=== STARTING FULL BACKEND INTEGRATION TEST VIA ASGI ===", flush=True)
    await init_db()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            # 1. Health check
            print("\n1. Testing /health...", flush=True)
            r = await client.get("/health")
            print(f"Status: {r.status_code}, Body: {r.json()}", flush=True)
            assert r.status_code == 200

            # 2. Login
            print("\n2. Testing /api/v1/auth/login...", flush=True)
            r = await client.post("/api/v1/auth/login", json={
                "email": "admin@example.com",
                "password": "Admin@123"
            })
            print(f"Status: {r.status_code}", flush=True)
            data = r.json()
            print(f"User: {data.get('user', {}).get('email')}, Workspace: {data.get('workspace', {}).get('name')}", flush=True)
            assert r.status_code == 200
            token = data["access_token"]
            workspace_id = data["workspace"]["id"]
            headers = {"Authorization": f"Bearer {token}"}

            # 3. /me
            print("\n3. Testing /api/v1/auth/me...", flush=True)
            r = await client.get("/api/v1/auth/me", headers=headers)
            print(f"Status: {r.status_code}, Email: {r.json().get('email')}", flush=True)
            assert r.status_code == 200

            # 4. Conversations stats
            print("\n4. Testing /api/v1/conversations/stats...", flush=True)
            r = await client.get("/api/v1/conversations/stats", headers=headers)
            print(f"Status: {r.status_code}, Stats: {r.json()}", flush=True)
            assert r.status_code == 200

            # 5. Conversations list
            print("\n5. Testing /api/v1/conversations...", flush=True)
            r = await client.get("/api/v1/conversations", headers=headers)
            conversations = r.json()
            count = len(conversations) if isinstance(conversations, list) else conversations.get('total', 0)
            print(f"Status: {r.status_code}, Total count: {count}", flush=True)
            assert r.status_code == 200

            # 6. Knowledge sources list
            print("\n6. Testing /api/v1/knowledge/sources...", flush=True)
            r = await client.get("/api/v1/knowledge/sources", headers=headers)
            print(f"Status: {r.status_code}, Sources count: {len(r.json())}", flush=True)
            assert r.status_code == 200

            # 7. Workspace Settings GET
            print(f"\n7. Testing GET /api/v1/workspaces/{workspace_id}...", flush=True)
            r = await client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers)
            print(f"Status: {r.status_code}, Name: {r.json().get('name')}", flush=True)
            assert r.status_code == 200

            # 8. Workspace Settings PATCH
            print(f"\n8. Testing PATCH /api/v1/workspaces/{workspace_id}/business-profile...", flush=True)
            r = await client.patch(f"/api/v1/workspaces/{workspace_id}/business-profile", headers=headers, json={
                "ai_persona_tone": "friendly",
                "business_description": "Premier full stack IT solutions & algorithmic trading software provider."
            })
            print(f"Status: {r.status_code}, Response: {r.json()}", flush=True)
            assert r.status_code == 200

            # 9. Playground Chat
            print(f"\n9. Testing POST /api/v1/workspaces/{workspace_id}/playground/chat...", flush=True)
            r = await client.post(f"/api/v1/workspaces/{workspace_id}/playground/chat", headers=headers, json={
                "message": "Hi, what software development services do you offer?"
            })
            print(f"Status: {r.status_code}", flush=True)
            res_data = r.json()
            print(f"AI Agent Response: {res_data.get('response')[:150]}...", flush=True)
            print(f"Latency: {res_data.get('latency_ms')}ms", flush=True)
            assert r.status_code == 200

        print("\n=======================================================", flush=True)
        print("ALL 9 E2E BACKEND ENDPOINTS PASSED SUCCESSFULLY!", flush=True)
        print("=======================================================", flush=True)
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(run_e2e_tests())
