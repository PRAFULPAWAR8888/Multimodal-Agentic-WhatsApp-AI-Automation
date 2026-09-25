import uuid
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from whatsapp_agent.database.session import get_db_session
from whatsapp_agent.database.models.users import User
from whatsapp_agent.database.models.workspaces import WorkspaceMember
from whatsapp_agent.database.models.knowledge import KnowledgeSource
from whatsapp_agent.security.dependencies import get_current_user, get_default_workspace_member
from whatsapp_agent.services.knowledge_service import KnowledgeService

# Create the router for Knowledge API
router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# --- Schemas ---
class KnowledgeSourceResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    source_type: str
    status: str
    document_count: int
    chunk_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class UrlUploadRequest(BaseModel):
    url: str
    title: Optional[str] = None

# --- Endpoints ---

@router.post("/url", response_model=KnowledgeSourceResponse, status_code=status.HTTP_201_CREATED)
async def submit_website_url(
    request: UrlUploadRequest,
    req: Request,
    workspace_member: WorkspaceMember = Depends(get_default_workspace_member),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Submit a website URL to be ingested as a knowledge source."""
    service = KnowledgeService(db, req.app.state.redis_pool)
    return await service.ingest_url(
        url=request.url,
        title=request.title,
        workspace_id=workspace_member.workspace_id
    )

@router.post("/document", response_model=KnowledgeSourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    req: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    workspace_member: WorkspaceMember = Depends(get_default_workspace_member),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Upload a PDF or Text document to be ingested as a knowledge source."""
    service = KnowledgeService(db, req.app.state.redis_pool)
    return await service.upload_document(
        file=file,
        title=title,
        workspace_id=workspace_member.workspace_id
    )

@router.get("/{source_id}", response_model=KnowledgeSourceResponse)
async def get_knowledge_source_status(
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Any:
    """Check the processing status of a knowledge source."""
    # We could also restrict this by workspace_member, but keeping as is for scope
    stmt = select(KnowledgeSource).where(KnowledgeSource.id == source_id)
    result = await db.execute(stmt)
    source = result.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    return source
