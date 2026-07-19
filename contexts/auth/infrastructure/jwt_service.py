from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from contexts.auth.domain.ports import TokenService
from contexts.shared.domain.exceptions import AuthenticationError
from contexts.shared.domain.identifiers import UserId

JWT_ALGORITHM = "HS256"


class JwtService(TokenService):
    def __init__(self, secret: str, expiry_hours: int = 24) -> None:
        self.secret = secret
        self.expiry_hours = expiry_hours

    def max_lifetime(self) -> timedelta:
        """Upper bound of a token's valid lifetime (drives blacklist retention)."""
        return timedelta(hours=self.expiry_hours)

    def generate(self, user_id: UserId, username: str) -> str:
        now = datetime.now(tz=timezone.utc)
        exp = now + timedelta(hours=self.expiry_hours)
        # jti enables single-token revocation (logout); iat enables the
        # user-wide "revoke all tokens issued before T" rule (password change).
        payload = {
            "user_id": user_id.value,
            "username": username,
            "iat": now,
            "jti": uuid.uuid4().hex,
            "exp": exp,
        }
        return jwt.encode(payload, self.secret, algorithm=JWT_ALGORITHM)

    def verify(self, token: str) -> dict:
        try:
            return jwt.decode(token, self.secret, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("token expired") from None
        except jwt.InvalidTokenError:
            raise AuthenticationError("invalid token") from None

