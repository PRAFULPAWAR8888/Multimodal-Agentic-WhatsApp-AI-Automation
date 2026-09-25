"""
FastAPI security dependencies for JWT-based authentication.
"""
from typing import Tuple
from fastapi import Depends, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from whatsapp_agent.database.session import get_db_session
from whatsapp_agent.security.jwt import decode_token
from whatsapp_agent.core.exceptions import AuthenticationError, AuthorizationError, TokenExpiredError, InvalidTokenError
from whatsapp_agent.database.models import User, WorkspaceMember
from whatsapp_agent.database.repositories.users import UserRepository
from whatsapp_agent.database.repositories.workspaces import WorkspaceRepository

bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Dependency that validates the Bearer JWT token and returns the current user.
    Raises AuthenticationError if token is missing, expired, or invalid.
    """
    if not credentials:
        raise AuthenticationError("Not authenticated")
    
    try:
        payload = decode_token(credentials.credentials)
    except TokenExpiredError:
        raise AuthenticationError("Token has expired")
    except InvalidTokenError:
        raise AuthenticationError("Invalid token")
    
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Invalid token: missing subject")
        
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationError("Invalid token: invalid subject format")
    
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise AuthenticationError("User not found")
        
    if not user.is_active:
        raise AuthenticationError("User is inactive")
        
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that requires an active (non-deleted, non-suspended) user."""
    # is_active check is already in get_current_user but doing it again just to be safe
    if not current_user.is_active:
        raise AuthenticationError("Inactive user")
    return current_user

async def get_current_workspace_member(
    workspace_id: str = Path(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> Tuple[User, WorkspaceMember]:
    """Dependency that validates workspace membership and returns (user, member)."""
    try:
        ws_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise AuthorizationError("Invalid workspace ID format")
        
    workspace_repo = WorkspaceRepository(db)
    member = await workspace_repo.get_member(ws_uuid, current_user.id)
    
    if not member:
        raise AuthorizationError("Not a member of this workspace")
        
    return current_user, member

async def get_default_workspace_member(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> WorkspaceMember:
    """Dependency that returns the user's default/first workspace member record."""
    from sqlalchemy import select
    
    stmt = select(WorkspaceMember).where(WorkspaceMember.user_id == current_user.id)
    result = await db.execute(stmt)
    member = result.scalars().first()
    
    if not member:
        raise AuthorizationError("User has no workspace")
        
    return member
