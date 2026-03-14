"""User domain model."""
import uuid
import re
from dataclasses import dataclass, field
from datetime import datetime
from .exceptions import InvalidEmailError


@dataclass
class User:
    """User entity with email validation."""

    email: str
    name: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate email format after initialization."""
        if not self._is_valid_email(self.email):
            raise InvalidEmailError(self.email)

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Check email format with regex."""
        pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._%-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
