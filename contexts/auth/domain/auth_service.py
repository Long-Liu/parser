from __future__ import annotations

import bcrypt

from contexts.shared.domain.exceptions import AuthenticationError


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


class AuthenticationService:
    def verify_credentials(self, user, password: str) -> None:
        if not user.is_active:
            raise AuthenticationError("account disabled")
        if not verify_password(password, user.password_hash):
            raise AuthenticationError("invalid credentials")


def _demo():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)
    print("auth_service: OK")


if __name__ == "__main__":
    _demo()
