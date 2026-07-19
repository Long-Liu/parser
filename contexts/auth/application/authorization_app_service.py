from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import jwt

from contexts.auth.application.security import TokenService
from contexts.auth.domain.repositories import TokenRevocationRepository, UserRepository
from contexts.shared.domain.exceptions import AuthenticationError
from contexts.shared.domain.identifiers import UserId


@dataclass(frozen=True)
class AuthContext:
    user_id: int
    username: str
    permissions: set[str]
    # Raw verified JWT claims (jti/iat/exp), stashed on request.ctx by
    # require_auth so logout / change-password can revoke the presented token.
    claims: dict = field(default_factory=dict)


def _claim_epoch(value) -> float | None:
    """Normalise a JWT time claim (int after decode) to epoch seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        return value.timestamp()
    return None


class AuthorizationApplicationService:
    def __init__(self, user_repo: UserRepository, jwt_service: TokenService,
                 token_revocations: TokenRevocationRepository | None = None) -> None:
        self._users = user_repo
        self._jwt = jwt_service
        self._revocations = token_revocations

    async def authenticate(self, token: str) -> AuthContext:
        try:
            payload = self._jwt.verify(token)
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("token expired")
        except jwt.InvalidTokenError:
            raise AuthenticationError("invalid token")
        user_id = UserId(payload["user_id"])
        if self._revocations is not None and await self._revocations.is_revoked(
            jti=payload.get("jti"),
            user_id=user_id,
            issued_at=_claim_epoch(payload.get("iat")),
        ):
            raise AuthenticationError("token revoked")
        return AuthContext(
            user_id=user_id.value,
            username=payload["username"],
            permissions=await self._users.get_permissions(user_id),
            claims=payload,
        )
