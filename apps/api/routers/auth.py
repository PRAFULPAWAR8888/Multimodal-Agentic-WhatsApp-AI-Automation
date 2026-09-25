"""
FastAPI router for Authentication and Authorization API.
"""
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field, field_validator
import re
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from whatsapp_agent.database.session import get_db_session
from whatsapp_agent.services.auth_service import AuthService
from whatsapp_agent.security.dependencies import get_current_user
from whatsapp_agent.database.models import User
from whatsapp_agent.database.repositories.workspaces import WorkspaceRepository

router = APIRouter(prefix="/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)
    workspace_name: str = Field(..., min_length=2, max_length=100)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r'[A-Za-z]', v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r'\d', v):
            raise ValueError("Password must contain at least one digit")
        return v

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime
    
class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str

class RegisterResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserResponse
    workspace: WorkspaceResponse

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED, summary="Register a new user")
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Register a new user and create their initial workspace.
    """
    auth_service = AuthService(db)
    result = await auth_service.register(
        email=request.email,
        password=request.password,
        full_name=request.full_name,
        workspace_name=request.workspace_name
    )
    
    # We need to fetch the newly created user and workspace to return them
    user = await auth_service.user_repo.get_by_email(request.email)
    workspace = await auth_service.workspace_repo.get_by_id(result.workspace_id)
    
    return RegisterResponse(
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        token_type=result.tokens.token_type,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at
        ),
        workspace=WorkspaceResponse(
            id=str(workspace.id),
            name=workspace.name,
            slug=workspace.slug
        )
    )

@router.post("/login", response_model=TokenResponse, summary="Log in user")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Authenticate user and return access and refresh tokens.
    """
    auth_service = AuthService(db)
    tokens = await auth_service.login(request.email, request.password)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type
    )

@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh_tokens(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Obtain a new pair of access and refresh tokens using a valid refresh token.
    """
    auth_service = AuthService(db)
    tokens = await auth_service.refresh_tokens(request.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type
    )

@router.get("/me", response_model=UserResponse, summary="Get current user profile")
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get profile information for the currently authenticated user.
    """
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )

@router.post("/logout", summary="Log out user")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Log out the current user (client-side clears tokens, we could implement token blacklisting here).
    """
    return {"message": "Logged out successfully"}
