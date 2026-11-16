import asyncio
from whatsapp_agent.database.session import _get_session_factory
from apps.worker.main import run_agent
from whatsapp_agent.database.models.agents import AgentRun
from sqlalchemy import select
from whatsapp_agent.database.engine import init_db

async def main():
    await init_db()
    ctx = {"redis": None}
    
    # get the agent run we just created (or rather, we need to create one if it wasn't)
    factory = _get_session_factory()
    async with factory() as db:
        run = (await db.execute(select(AgentRun).limit(1))).scalar_one_or_none()
        if not run:
            from whatsapp_agent.database.models.whatsapp import WhatsAppMessage
            msg = (await db.execute(select(WhatsAppMessage).limit(1))).scalar_one_or_none()
            import uuid
            from whatsapp_agent.database.models.agents import AgentRunStatus
            from whatsapp_agent.database.models.agents import AgentType
            run = AgentRun(id=uuid.uuid4(), workspace_id=msg.workspace_id, conversation_id=msg.conversation_id, message_id=msg.id, agent_type=AgentType.SUPERVISOR, input_modality="TEXT", status=AgentRunStatus.PENDING)
            db.add(run)
            await db.commit()
            
    print(f"Running run_agent for {run.id}...")
    try:
        await run_agent(ctx, str(run.id))
        print("Successfully completed run_agent!")
    except Exception as e:
        print(f"Exception during processing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
