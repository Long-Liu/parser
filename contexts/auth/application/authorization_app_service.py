from __future__ import annotations

from dataclasses import dataclass

import jwt

from contexts.auth.domain.jwt_service import JwtService
from contexts.auth.domain.repositories import UserRepository
from contexts.shared.domain.identifiers import UserId


@dataclass(frozen=True)
class AuthContext:
    user_id: int
    username: str
    permissions: set[str]


class AuthorizationApplicationService:
    def __init__(self, user_repo: UserRepository, jwt_service: JwtService) -> None:
        self._users = user_repo
        self._jwt = jwt_service

    async def authenticate(self, token: str) -> AuthContext:
        payload = self._jwt.verify(token)
        user_id = UserId(payload["user_id"])
        return AuthContext(
            user_id=user_id.value,
            username=payload["username"],
            permissions=await self._users.get_permissions(user_id),
        )


ExpiredSignatureError = jwt.ExpiredSignatureError
InvalidTokenError = jwt.InvalidTokenError
