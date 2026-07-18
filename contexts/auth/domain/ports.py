"""Auth domain ports — protocols implemented by outer layers.

These live in the domain layer so domain services (e.g. AuthenticationService)
and application services depend inward, never on application/infrastructure
modules.
"""

from __future__ import annotations

from typing import Protocol

from contexts.shared.domain.identifiers import UserId


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(Protocol):
    """Issues and verifies auth tokens.

    Implementations must raise AuthenticationError (never library-specific
    exceptions) from verify() when the token is expired or invalid.
    """

    def generate(self, user_id: UserId, username: str) -> str: ...

    def verify(self, token: str) -> dict: ...
