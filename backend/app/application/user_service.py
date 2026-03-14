"""Сервис для работы с пользователями."""
from __future__ import annotations

from uuid import UUID
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user import User
from app.infrastructure.repositories import UserRepository


class UserService:
    """Сервис для управления пользователями."""
    
    def __init__(self, session: AsyncSession) -> None:
        """Инициализация сервиса."""
        self.session = session
        self.repo = UserRepository(session)
    
    async def register(self, email: str, name: str) -> User:
        """Регистрация нового пользователя."""
        user = User(email=email, name=name)
        await self.repo.save(user)
        return user
    
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Получить пользователя по ID."""
        return await self.repo.find_by_id(user_id)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Получить пользователя по email."""
        return await self.repo.find_by_email(email)
    
    async def list_users(self) -> List[User]:
        """Получить список всех пользователей."""
        return await self.repo.find_all()