"""Доменная модель пользователя."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime


@dataclass
class User:
    """Пользователь маркетплейса."""
    
    email: str
    name: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self) -> None:
        """Валидация email после инициализации."""
        if not self._is_valid_email(self.email):
            raise ValueError(f"Invalid email format: {self.email}")
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Проверка формата email."""
        pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        return bool(re.match(pattern, email))