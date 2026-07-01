from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from contexts.shared.domain.identifiers import UserId

JWT_ALGORITHM = "HS256"


class JwtService:
    def __init__(self, secret: str, expiry_hours: int = 24) -> None:
        self.secret = secret
        self.expiry_hours = expiry_hours

    def generate(self, user_id: UserId, username: str) -> str:
        exp = datetime.now(tz=timezone.utc) + timedelta(hours=self.expiry_hours)
        payload = {"user_id": user_id.value, "username": username, "exp": exp}
        return jwt.encode(payload, self.secret, algorithm=JWT_ALGORITHM)

    def verify(self, token: str) -> dict:
        return jwt.decode(token, self.secret, algorithms=[JWT_ALGORITHM])


def _demo():
    svc = JwtService("test-secret")
    token = svc.generate(UserId(1), "alice")
    payload = svc.verify(token)
    assert payload["user_id"] == 1
    print("jwt_service: OK")


if __name__ == "__main__":
    _demo()
