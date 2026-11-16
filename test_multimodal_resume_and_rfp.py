import asyncio
import base64
import uuid
import httpx
import pymupdf
from sqlalchemy import select
from whatsapp_agent.database.session import _get_session_factory
from whatsapp_agent.database.models import Workspace, BusinessProfile, Lead, User

async def main():
    print("=== MULTIMODAL RESUME & RFP AUTOMATED VERIFICATION ===")
    from whatsapp_agent.database.engine import init_db
    await init_db()
    factory = _get_session_factory()

    # 1. Fetch default workspace and configure Anand Kumar @ Associative
    async with factory() as db:
        ws = (await db.execute(select(Workspace).limit(1))).scalar_one()
        ws_id = str(ws.id)
        
        bp = (await db.execute(select(BusinessProfile).where(BusinessProfile.workspace_id == ws.id))).scalar_one_or_none()
        if not bp:
            bp = BusinessProfile(workspace_id=ws.id)
            db.add(bp)
            
        bp.business_name = "Associative"
        bp.business_description = "Associative is a premier digital technology & software solutions company delivering end-to-end cloud engineering, AI automation, custom software development, and hiring top-tier tech talent."
        bp.ai_persona_name = "Anand Kumar"
        bp.ai_persona_role = "Client & Talent Relations Coordinator"
        bp.ai_persona_tone = "Professional, courteous, and concise"
        bp.ai_custom_instructions = (
            "You are Anand Kumar representing Associative. Assist prospective clients and job seekers efficiently.\n"
            "Keep responses concise (2-3 sentences max).\n"
            "Path A: Clients -> Understand project requirements, save lead, offer discovery call.\n"
            "Path B: Job Seekers -> Welcome candidate, acknowledge resume details, confirm application logged, offer screening interview."
        )
        bp.ai_restrictions = "Never guarantee hiring decisions or fixed pricing without scope review."
        bp.ai_max_response_length = 150
        bp.ai_use_emoji = True
        await db.commit()
        print(f"Configured Workspace {ws_id} with Persona: {bp.ai_persona_name} @ {bp.business_name}")

        user = (await db.execute(select(User).limit(1))).scalar_one()
        from whatsapp_agent.security.jwt import create_access_token
        token = create_access_token(subject=str(user.id))
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Authenticated as User {user.email}")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "RAHUL SHARMA\n"
        "Email: rahul.sharma@techassociates.io\n"
        "Phone: +91 9876543210\n"
        "Role: Senior Python Backend Developer\n"
        "Experience: 4 years building scalable FastAPI APIs, Docker, Redis, and LangChain workflows.\n"
        "Education: Bachelor of Technology in Computer Science (2022)\n"
        "Objective: Applying for Senior Backend Developer opening at Associative."
    )
    pdf_bytes = doc.write()
    b64_pdf = f"data:application/pdf;base64,{base64.b64encode(pdf_bytes).decode('utf-8')}"

    # 3. Call Playground Chat with the Resume
    print("\n--- Sending Candidate Resume PDF ---")
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {
            "message": "Hi Anand, I am applying for the Python Developer position at Associative. Please find my resume attached.",
            "file_data": b64_pdf,
            "file_name": "Rahul_Sharma_Resume.pdf",
            "file_type": "application/pdf",
            "modality": "document",
            "sender_id": "+919876543210"
        }
        res = await client.post(
            f"http://localhost:8000/api/v1/workspaces/{ws_id}/playground/chat",
            json=payload,
            headers=headers
        )
        assert res.status_code == 200, f"Error: {res.text}"
        data = res.json()
        print(f"Status: {res.status_code}")
        print(f"Routed Agent: {data.get('routed_agent')}")
        print(f"AI Response:\n{data.get('response_text')}\n")

    # 4. Check CRM Lead in Database
    async with factory() as db:
        lead = (await db.execute(
            select(Lead).where(
                Lead.workspace_id == uuid.UUID(ws_id),
                Lead.email == "rahul.sharma@techassociates.io"
            )
        )).scalars().first()
        if lead:
            print(f"✅ CRM Verification SUCCESS: Found Lead for {lead.name}")
            print(f"   Email: {lead.email}, Phone: {lead.phone}")
            print(f"   Requirement: {lead.requirement}")
            print(f"   Lead Score: {lead.lead_score}, Status: {lead.status}")
        else:
            print("❌ Lead not found in DB!")

    print("\n=== MULTIMODAL VERIFICATION COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(main())
