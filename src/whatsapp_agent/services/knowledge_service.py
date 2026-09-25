import os
import uuid
import aiofiles
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from arq import ArqRedis

from whatsapp_agent.database.models.knowledge import KnowledgeSource, KnowledgeSourceType, KnowledgeSourceStatus

class KnowledgeService:
    def __init__(self, db: AsyncSession, redis_pool: ArqRedis) -> None:
        self.db = db
        self.redis_pool = redis_pool

    async def ingest_url(self, url: str, title: str | None, workspace_id: uuid.UUID) -> KnowledgeSource:
        source_id = uuid.uuid4()
        source = KnowledgeSource(
            id=source_id,
            workspace_id=workspace_id,
            source_type=KnowledgeSourceType.WEBSITE,
            title=title or url,
            source_uri=url,
            status=KnowledgeSourceStatus.PENDING
        )
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        
        await self.redis_pool.enqueue_job("ingest_knowledge_source", {}, str(source_id))
        return source

    async def upload_document(self, file: UploadFile, title: str | None, workspace_id: uuid.UUID) -> KnowledgeSource:
        source_type = KnowledgeSourceType.PDF
        if file.content_type == "text/plain":
            source_type = KnowledgeSourceType.TEXT

        os.makedirs("media/knowledge_sources", exist_ok=True)
        source_id = uuid.uuid4()
        
        # Sanitize filename to prevent path traversal
        safe_filename = os.path.basename(file.filename.replace('\\', '/')) if file.filename else "upload.bin"
        file_path = f"media/knowledge_sources/{source_id}_{safe_filename}"
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):
                await out_file.write(content)
                
        source = KnowledgeSource(
            id=source_id,
            workspace_id=workspace_id,
            source_type=source_type,
            title=title or safe_filename,
            source_uri=file_path,
            status=KnowledgeSourceStatus.PENDING
        )
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        
        await self.redis_pool.enqueue_job("ingest_knowledge_source", {}, str(source_id))
        return source
