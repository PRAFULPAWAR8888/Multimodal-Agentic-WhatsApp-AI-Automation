import asyncio
import sys
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.database.models.knowledge import KnowledgeSource, KnowledgeSourceType, KnowledgeSourceStatus
from whatsapp_agent.database.models.workspaces import Workspace
from sqlalchemy import select
from arq import create_pool
from arq.connections import RedisSettings

async def add_website(url: str):
    print(f"Adding website to AI Knowledge Base: {url}")
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    redis_pool = await create_pool(RedisSettings(host='localhost', port=6379, database=0))

    async with SessionLocal() as db:
        # Get the default workspace
        workspace = (await db.execute(select(Workspace).limit(1))).scalar_one_or_none()
        if not workspace:
            print("Error: No workspace found. Please send a message on WhatsApp first to create a default workspace.")
            return

        source_id = uuid.uuid4()
        source = KnowledgeSource(
            id=source_id,
            workspace_id=workspace.id,
            source_type=KnowledgeSourceType.WEBSITE,
            title=url,
            source_uri=url,
            status=KnowledgeSourceStatus.PENDING
        )
        db.add(source)
        await db.commit()
        
        # ARQ automatically injects the ctx dict, so we only pass the source_id
        await redis_pool.enqueue_job("ingest_knowledge_source", str(source_id))
        
        print("Success! The website has been added.")
        print("The background worker is reading it now. In a few seconds, you can ask questions about it on WhatsApp!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python add_website.py <URL>")
        sys.exit(1)
        
    asyncio.run(add_website(sys.argv[1]))
