from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from contexts.shared.domain.identifiers import UserId


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(Protocol):
    def generate(self, user_id: UserId, username: str) -> str: ...

    def verify(self, token: str) -> dict: ...

    def max_lifetime(self) -> timedelta: ...

