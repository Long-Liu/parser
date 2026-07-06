from __future__ import annotations

from typing import TYPE_CHECKING

from contexts.auth.application.security import PasswordHasher
from contexts.shared.domain.exceptions import AuthenticationError

if TYPE_CHECKING:
    from contexts.auth.domain.user import User


class AuthenticationService:
    def __init__(self, password_hasher: PasswordHasher) -> None:
        self._password_hasher = password_hasher

    def verify_credentials(self, user: User, password: str) -> None:
        # Verify password FIRST to prevent account-state probing via timing.
        if not self._password_hasher.verify(password, user.password_hash):
            raise AuthenticationError("invalid credentials")
        if not user.is_active:
            raise AuthenticationError("account disabled")
