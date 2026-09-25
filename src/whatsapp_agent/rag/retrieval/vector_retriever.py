"""
Vector store retriever using pgvector cosine similarity.

Retrieves the top-k most relevant document chunks for a query.
Uses IVFFlat index for efficient approximate nearest neighbor search.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Assuming imports match the required structure
from whatsapp_agent.database.models.knowledge import DocumentChunk
from whatsapp_agent.rag.embedding.sentence_transformers import get_embedding_provider
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

@dataclass
class RetrievedChunk:
    chunk_id: str
    source_id: str
    content: str
    source_title: str
    score: float  # Cosine similarity (0.0 to 1.0, higher = more relevant)
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

class VectorRetriever:
    """
    Retrieves relevant document chunks using pgvector cosine similarity.
    
    Uses the IVFFlat index created in migration 0001_initial_schema for efficiency.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_provider = get_embedding_provider()
    
    async def retrieve(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[RetrievedChunk]:
        """
        Retrieve top-k most relevant chunks for a query within a workspace.
        
        Args:
            query: The user's question or search query.
            workspace_id: Tenant workspace ID (MANDATORY for isolation).
            top_k: Number of chunks to retrieve.
            min_score: Minimum cosine similarity threshold.
        
        Returns:
            List of RetrievedChunk ordered by relevance score (highest first).
        
        Security:
            workspace_id filter is MANDATORY. Never retrieve across workspaces.
        """
        start = time.monotonic()
        
        # 1. Embed the query
        query_embedding = await self.embedding_provider.embed_text(query)
        embedding_list = "[" + ",".join(map(str, query_embedding)) + "]"
        
        # 2. Query pgvector using cosine similarity
        sql = text("""
            SELECT c.id, c.source_id, c.content, c.metadata_json, c.chunk_index,
                   1 - (c.embedding <=> :query_vector::vector) AS score,
                   s.title AS source_title
            FROM document_chunks c
            JOIN knowledge_sources s ON c.source_id = s.id
            WHERE c.workspace_id = :workspace_id
              AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> :query_vector::vector
            LIMIT :top_k
        """)
        
        result = await self.db.execute(
            sql, 
            {
                "query_vector": embedding_list, 
                "workspace_id": workspace_id, 
                "top_k": top_k
            }
        )
        
        rows = result.fetchall()
        
        chunks = []
        for row in rows:
            score = float(row.score) if row.score is not None else 0.0
            if score >= min_score:
                chunks.append(RetrievedChunk(
                    chunk_id=str(row.id),
                    source_id=str(row.source_id),
                    content=row.content,
                    source_title=row.source_title,
                    score=score,
                    chunk_index=row.chunk_index,
                    metadata=row.metadata_json or {}
                ))
        
        duration = time.monotonic() - start
        logger.info("retrieved_chunks", count=len(chunks), duration=duration, top_k=top_k)
        
        return chunks
    
    async def retrieve_for_agent(self, query: str, workspace_id: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Convenience method that returns chunks as plain dicts for AgentState.rag_context.
        
        Returns:
            List of dicts: [{"content": str, "source": str, "score": float}]
        """
        chunks = await self.retrieve(query, workspace_id, top_k=top_k)
        return [
            {
                "content": chunk.content,
                "source": chunk.source_title,
                "score": round(chunk.score, 4),
                "chunk_index": chunk.chunk_index,
            }
            for chunk in chunks
        ]
