import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from whatsapp_agent.config.settings import get_settings

async def main():
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async with engine.connect() as conn:
        await conn.execute(text("UPDATE whatsapp_conversations SET ai_enabled = true, status = 'ACTIVE' WHERE status = 'ESCALATED' OR ai_enabled = false;"))
        await conn.commit()
        print('SUCCESS: AI Unpaused for all conversations')

asyncio.run(main())
