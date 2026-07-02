from __future__ import annotations

from dataclasses import dataclass

import jwt

from contexts.auth.application.security import TokenService
from contexts.auth.domain.repositories import UserRepository
from contexts.shared.domain.exceptions import AuthenticationError
from contexts.shared.domain.identifiers import UserId


@dataclass(frozen=True)
class AuthContext:
    user_id: int
    username: str
    permissions: set[str]


class AuthorizationApplicationService:
    def __init__(self, user_repo: UserRepository, jwt_service: TokenService) -> None:
        self._users = user_repo
        self._jwt = jwt_service

    async def authenticate(self, token: str) -> AuthContext:
        try:
            payload = self._jwt.verify(token)
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("token expired")
        except jwt.InvalidTokenError:
            raise AuthenticationError("invalid token")
        user_id = UserId(payload["user_id"])
        return AuthContext(
            user_id=user_id.value,
            username=payload["username"],
            permissions=await self._users.get_permissions(user_id),
        )
