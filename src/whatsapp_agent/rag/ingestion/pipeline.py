"""
Knowledge ingestion pipeline.

Orchestrates the full document → chunks → embeddings → pgvector flow.

Pipeline steps:
1. Load document (PDF/text/CSV)
2. Split into chunks (RecursiveTextSplitter)
3. Compute content hashes (for deduplication)
4. Generate embeddings (sentence-transformers)
5. Store chunks in document_chunks table
6. Update KnowledgeSource status → ACTIVE
"""
from __future__ import annotations
import hashlib
import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from whatsapp_agent.database.models.knowledge import KnowledgeSource, KnowledgeSourceStatus, DocumentChunk
from whatsapp_agent.rag.chunking.text_splitter import RecursiveTextSplitter
from whatsapp_agent.rag.ingestion.document_loader import get_loader_for_mime_type
from whatsapp_agent.rag.embedding.sentence_transformers import get_embedding_provider
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

class IngestionPipeline:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.splitter = RecursiveTextSplitter(chunk_size=512, chunk_overlap=64)
        self.embedding = get_embedding_provider()
    
    async def ingest_document(
        self,
        source_id: uuid.UUID,
        workspace_id: uuid.UUID,
        document_bytes: bytes,
        mime_type: str,
        source_title: str,
        source_uri: str,
    ) -> dict[str, Any]:
        """
        Full ingestion pipeline for a document.
        
        Returns: {"chunks_created": int, "total_tokens_estimated": int, "source_id": str}
        """
        try:
            # 1. Update source status to PROCESSING
            stmt = update(KnowledgeSource).where(
                KnowledgeSource.id == source_id,
                KnowledgeSource.workspace_id == workspace_id
            ).values(status=KnowledgeSourceStatus.PROCESSING)
            await self.db.execute(stmt)
            await self.db.commit()
            
            # 2. Load document text
            loader = get_loader_for_mime_type(mime_type)
            loaded_doc = await loader.load_bytes(document_bytes, source_uri)
            
            # 3. Split into chunks
            chunks = self.splitter.split_text(
                loaded_doc.content, 
                metadata={"source_title": source_title, "source_uri": source_uri}
            )
            
            if not chunks:
                logger.warning("no_chunks_extracted", source_id=str(source_id))
                await self._update_status(source_id, workspace_id, KnowledgeSourceStatus.FAILED)
                return {"chunks_created": 0, "total_tokens_estimated": 0, "source_id": str(source_id)}
            
            # 4. Deduplicate by content hash (calculating it)
            db_chunks = []
            total_tokens = 0
            
            # 5. Embed all chunks in batches
            texts = [c.content for c in chunks]
            embeddings = await self.embedding.embed_texts(texts)
            
            # 6. Store in document_chunks table
            for i, chunk in enumerate(chunks):
                content_hash = self._content_hash(chunk.content)
                total_tokens += self.splitter._token_count(chunk.content)
                db_chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    source_id=source_id,
                    content=chunk.content,
                    content_hash=content_hash,
                    chunk_index=chunk.chunk_index,
                    metadata_json=chunk.metadata,
                    embedding=embeddings[i]
                )
                db_chunks.append(db_chunk)
                self.db.add(db_chunk)
            
            # 7. Update source: status=ACTIVE, chunk_count=N
            stmt = update(KnowledgeSource).where(
                KnowledgeSource.id == source_id,
                KnowledgeSource.workspace_id == workspace_id
            ).values(
                status=KnowledgeSourceStatus.ACTIVE,
                chunk_count=len(db_chunks)
            )
            await self.db.execute(stmt)
            await self.db.commit()
            
            logger.info("document_ingested", source_id=str(source_id), chunks=len(db_chunks))
            return {
                "chunks_created": len(db_chunks),
                "total_tokens_estimated": total_tokens,
                "source_id": str(source_id)
            }
            
        except Exception as e:
            logger.exception("ingestion_failed", source_id=str(source_id), error=str(e))
            await self.db.rollback()
            await self._update_status(source_id, workspace_id, KnowledgeSourceStatus.FAILED)
            raise
    
    async def _update_status(self, source_id: uuid.UUID, workspace_id: uuid.UUID, status: KnowledgeSourceStatus):
        stmt = update(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.workspace_id == workspace_id
        ).values(status=status)
        await self.db.execute(stmt)
        await self.db.commit()
    
    @staticmethod
    def _content_hash(content: str) -> str:
        """SHA-256 hash of chunk content for deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()
