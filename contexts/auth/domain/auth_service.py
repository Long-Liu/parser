from __future__ import annotations

from typing import Protocol

from contexts.shared.domain.exceptions import AuthenticationError


class PasswordVerifier(Protocol):
    def verify(self, password: str, password_hash: str) -> bool: ...


class AuthenticationService:
    def __init__(self, password_verifier: PasswordVerifier) -> None:
        self._password_verifier = password_verifier

    def verify_credentials(self, user, password: str) -> None:
        if not user.is_active:
            raise AuthenticationError("account disabled")
        if not self._password_verifier.verify(password, user.password_hash):
            raise AuthenticationError("invalid credentials")
