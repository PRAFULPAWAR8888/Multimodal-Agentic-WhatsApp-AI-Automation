"""
Workspace repository — all database operations for Workspace and WorkspaceMember models.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from whatsapp_agent.database.models import Workspace, WorkspaceMember, WorkspaceRole
from typing import Any
import uuid

class WorkspaceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, workspace_id: uuid.UUID) -> Workspace | None:
        """Get workspace by ID."""
        result = await self.db.execute(select(Workspace).where(Workspace.id == workspace_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Workspace | None:
        """Get workspace by slug."""
        result = await self.db.execute(select(Workspace).where(Workspace.slug == slug))
        return result.scalar_one_or_none()

    async def create(self, name: str, slug: str, owner_id: uuid.UUID) -> Workspace:
        """Create a new workspace."""
        workspace = Workspace(
            name=name,
            slug=slug,
            owner_id=owner_id
        )
        self.db.add(workspace)
        await self.db.flush()
        return workspace

    async def get_member(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceMember | None:
        """Get a workspace member record."""
        result = await self.db.execute(
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .where(WorkspaceMember.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def add_member(self, workspace_id: uuid.UUID, user_id: uuid.UUID, role: WorkspaceRole) -> WorkspaceMember:
        """Add a user to a workspace with a specific role."""
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role
        )
        self.db.add(member)
        await self.db.flush()
        return member

    async def get_user_workspaces(self, user_id: uuid.UUID) -> list[Workspace]:
        """Get all workspaces a user is a member of."""
        result = await self.db.execute(
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user_id)
        )
        return list(result.scalars().all())

    async def slug_exists(self, slug: str) -> bool:
        """Check if a workspace exists with the given slug."""
        workspace = await self.get_by_slug(slug)
        return workspace is not None

    async def get_business_profile(self, workspace_id: uuid.UUID) -> dict[str, Any] | None:
        """Get the business profile for a workspace as a dictionary."""
        from whatsapp_agent.database.models import BusinessProfile
        result = await self.db.execute(
            select(BusinessProfile).where(BusinessProfile.workspace_id == workspace_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None
            
        return {
            "business_name": profile.business_name,
            "business_description": profile.business_description,
            "ai_persona_name": profile.ai_persona_name,
            "ai_persona_role": profile.ai_persona_role,
            "ai_persona_tone": profile.ai_persona_tone,
            "ai_response_language": profile.ai_response_language,
            "ai_max_response_length": profile.ai_max_response_length,
            "ai_use_emoji": profile.ai_use_emoji,
            "ai_custom_instructions": profile.ai_custom_instructions,
            "ai_restrictions": profile.ai_restrictions,
            "business_hours_json": profile.business_hours_json,
            "escalation_keywords_json": profile.escalation_keywords_json,
        }
