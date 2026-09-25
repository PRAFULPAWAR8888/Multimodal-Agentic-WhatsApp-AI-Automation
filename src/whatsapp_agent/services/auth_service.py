"""
Authentication service — business logic for registration, login, token refresh.
"""
from dataclasses import dataclass
import uuid
import re
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp_agent.security.passwords import hash_password, verify_password
from whatsapp_agent.security.jwt import create_token_pair, decode_token
from whatsapp_agent.database.repositories.users import UserRepository
from whatsapp_agent.database.repositories.workspaces import WorkspaceRepository
from whatsapp_agent.core.exceptions import AuthenticationError, ConflictError, ValidationError, InvalidTokenError
from whatsapp_agent.database.models import WorkspaceRole
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

@dataclass
class RegisterResult:
    user_id: str
    workspace_id: str
    tokens: AuthTokens

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.workspace_repo = WorkspaceRepository(db)

    async def register(
        self,
        email: str,
        password: str,
        full_name: str,
        workspace_name: str,
    ) -> RegisterResult:
        """
        Register a new user and create their workspace.
        """
        logger.info("Registering new user", email=email)
        
        # Check email uniqueness
        if await self.user_repo.exists_by_email(email):
            logger.warning("Registration failed: Email already exists", email=email)
            raise ConflictError("A user with this email already exists")

        # Hash password and create user
        hashed = hash_password(password)
        user = await self.user_repo.create(email=email, hashed_password=hashed, full_name=full_name)

        # Generate unique workspace slug
        base_slug = self._make_slug(workspace_name)
        slug = base_slug
        counter = 1
        while await self.workspace_repo.slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Create workspace and membership
        workspace = await self.workspace_repo.create(
            name=workspace_name,
            slug=slug,
            owner_id=user.id
        )
        await self.workspace_repo.add_member(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER
        )

        # Generate tokens
        access_token, refresh_token = create_token_pair(str(user.id), str(workspace.id))
        
        logger.info("User registered successfully", user_id=str(user.id), workspace_id=str(workspace.id))
        
        return RegisterResult(
            user_id=str(user.id),
            workspace_id=str(workspace.id),
            tokens=AuthTokens(access_token=access_token, refresh_token=refresh_token)
        )

    async def login(self, email: str, password: str) -> AuthTokens:
        """
        Authenticate a user with email + password.
        Raises AuthenticationError on invalid credentials.
        """
        logger.info("User login attempt", email=email)
        user = await self.user_repo.get_by_email(email)
        
        # We always use the same error message for security (prevent email enumeration)
        invalid_creds_err = AuthenticationError("Invalid email or password")
        
        if not user:
            logger.warning("Login failed: user not found", email=email)
            raise invalid_creds_err
            
        if not verify_password(password, user.hashed_password):
            logger.warning("Login failed: invalid password", user_id=str(user.id))
            raise invalid_creds_err
            
        if not user.is_active:
            logger.warning("Login failed: inactive user", user_id=str(user.id))
            raise AuthenticationError("User is inactive")
            
        await self.user_repo.update_last_login(user.id)
        
        # Get user workspaces to embed the default one in the token (optional, taking first one for simplicity)
        workspaces = await self.workspace_repo.get_user_workspaces(user.id)
        default_workspace_id = str(workspaces[0].id) if workspaces else None
        
        access_token, refresh_token = create_token_pair(str(user.id), default_workspace_id)
        logger.info("User logged in successfully", user_id=str(user.id))
        
        return AuthTokens(access_token=access_token, refresh_token=refresh_token)

    async def refresh_tokens(self, refresh_token: str) -> AuthTokens:
        """
        Issue new access + refresh tokens using a valid refresh token.
        """
        try:
            payload = decode_token(refresh_token)
        except Exception as e:
            raise AuthenticationError(f"Invalid or expired refresh token: {str(e)}")
            
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")
            
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise AuthenticationError("Invalid token payload")
            
        user = await self.user_repo.get_by_id(uuid.UUID(user_id_str))
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")
            
        workspaces = await self.workspace_repo.get_user_workspaces(user.id)
        default_workspace_id = str(workspaces[0].id) if workspaces else None
        
        new_access_token, new_refresh_token = create_token_pair(str(user.id), default_workspace_id)
        
        return AuthTokens(access_token=new_access_token, refresh_token=new_refresh_token)

    @staticmethod
    def _make_slug(name: str) -> str:
        """Convert workspace name to URL-safe slug."""
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip()).strip('-')
        if not slug:
            slug = "workspace"
        return slug[:50]  # Max 50 chars
