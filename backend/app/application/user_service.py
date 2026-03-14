"""User service for registration and management."""
import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.user import User
from app.domain.exceptions import EmailAlreadyExistsError, UserNotFoundError
from app.infrastructure.repositories import UserRepository


class UserService:
    """Service for user operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRepository(session)

    async def register(self, email: str, name: str) -> User:
        """Register new user."""
        # Check email exists
        existing = await self.repo.find_by_email(email)
        if existing:
            raise EmailAlreadyExistsError(email)

        user = User(email=email, name=name)
        await self.repo.save(user)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        """Get user by ID."""
        user = await self.repo.find_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return await self.repo.find_by_email(email)

    async def list_users(self) -> List[User]:
        """List all users."""
        return await self.repo.find_all()
