import asyncio
from whatsapp_agent.database.session import _get_session_factory
from whatsapp_agent.database.models.whatsapp import WhatsAppMessage
from sqlalchemy import select

from whatsapp_agent.database.engine import init_db

async def main():
    await init_db()
    factory = _get_session_factory()
    from whatsapp_agent.database.engine import get_engine
    from whatsapp_agent.database.models.agents import AgentRun
    from whatsapp_agent.database.models.whatsapp import WhatsAppMessage
    from sqlalchemy import select
    
    async with factory() as db:
        result = await db.execute(select(AgentRun).order_by(AgentRun.started_at.desc()).limit(5))
        runs = result.scalars().all()
        print("--- AGENT RUNS ---")
        for run in runs:
            print(f"Run {run.id} | Status: {run.status} | Error: {run.error_message}")
            
        result = await db.execute(select(WhatsAppMessage).order_by(WhatsAppMessage.timestamp.desc()).limit(5))
        messages = result.scalars().all()
        print("--- WHATSAPP MESSAGES ---")
        for msg in messages:
            print(f"Msg {msg.id} | Status: {msg.status} | Body: {msg.body}")

if __name__ == "__main__":
    asyncio.run(main())
