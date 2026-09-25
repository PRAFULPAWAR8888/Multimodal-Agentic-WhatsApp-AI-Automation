"""
User repository — all database operations for User model.
Business logic belongs in services, not repositories.
"""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from whatsapp_agent.database.models import User
import uuid

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, email: str, hashed_password: str, full_name: str) -> User:
        """Create a new user."""
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_active=True
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        """Update last login timestamp for a user."""
        user = await self.get_by_id(user_id)
        if user:
            user.last_login_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def exists_by_email(self, email: str) -> bool:
        """Check if a user exists with the given email."""
        user = await self.get_by_email(email)
        return user is not None
