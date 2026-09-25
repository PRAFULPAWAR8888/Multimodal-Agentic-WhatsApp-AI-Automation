import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from whatsapp_agent.database.session import get_db_session
from whatsapp_agent.database.models.workspaces import Workspace, BusinessProfile
from whatsapp_agent.database.models.users import User
from whatsapp_agent.security.dependencies import get_current_user

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

class BusinessProfileUpdate(BaseModel):
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    ai_persona_name: Optional[str] = None
    ai_persona_role: Optional[str] = None
    ai_persona_tone: Optional[str] = None
    ai_response_language: Optional[str] = None
    ai_use_emoji: Optional[bool] = None
    ai_custom_instructions: Optional[str] = None
    ai_restrictions: Optional[str] = None

@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get workspace details including business profile."""
    # Check if user is member (simplified for this demo)
    stmt = (
        select(Workspace)
        .options(selectinload(Workspace.business_profile))
        .where(Workspace.id == workspace_id)
    )
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return {
        "id": workspace.id,
        "name": workspace.name,
        "slug": workspace.slug,
        "business_profile": {
            "business_name": workspace.business_profile.business_name if workspace.business_profile else None,
            "ai_persona_name": workspace.business_profile.ai_persona_name if workspace.business_profile else None,
            "ai_persona_tone": workspace.business_profile.ai_persona_tone if workspace.business_profile else None,
            "ai_use_emoji": workspace.business_profile.ai_use_emoji if workspace.business_profile else None,
            "ai_custom_instructions": workspace.business_profile.ai_custom_instructions if workspace.business_profile else None,
        } if workspace.business_profile else None
    }

@router.patch("/{workspace_id}/business-profile")
async def update_business_profile(
    workspace_id: uuid.UUID,
    profile_update: BusinessProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update a workspace's business profile and AI persona settings."""
    stmt = (
        select(Workspace)
        .options(selectinload(Workspace.business_profile))
        .where(Workspace.id == workspace_id)
    )
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    profile = workspace.business_profile
    if not profile:
        profile = BusinessProfile(
            workspace_id=workspace.id,
            business_name=workspace.name
        )
        db.add(profile)

    update_data = profile_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    await db.commit()
    return {"status": "success"}
